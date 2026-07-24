#!/usr/bin/env python3
"""Step 4 — mechanically replay selector-action trajs (no model).

Starts N uvicorn workers from the clean 312-task checkout, then Playwright-
replays oracle-style click/fill/navigate sequences. Pixel/mark trajs are
skipped (not mechanically replayable without SoM regeneration).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CHECKPOINT_DIR,
    CLEAN_ROOT,
    DIRTY_ROOT,
    INVENTORY_DIR,
    PYTHON,
    assert_sellable_untouched,
    disposition_from_verifier,
    load_task_ids,
    snapshot_paths,
    source_commit_meta,
    write_json,
    write_json_pretty,
)


def _start_server(port: int, token: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["HARNESS_TOKEN"] = token
    env["PYTHONPATH"] = str(CLEAN_ROOT)
    # Ensure clean imports
    cmd = [
        str(PYTHON),
        "-m",
        "uvicorn",
        "server.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(CLEAN_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


async def _wait_ready(base: str, token: str, timeout: float = 60.0) -> None:
    import httpx

    headers = {"X-Harness-Token": token}
    t0 = time.time()
    async with httpx.AsyncClient(timeout=5.0) as c:
        while time.time() - t0 < timeout:
            try:
                r = await c.get(f"{base}/_harness/snapshot", headers=headers)
                if r.status_code in (200, 409, 401, 403):
                    # 409 = no episode yet, but server is up
                    return
            except Exception:
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError(f"server not ready: {base}")


async def _replay_episode(
    *,
    base: str,
    token: str,
    task_id: str,
    seed: int,
    traj_path: str,
    meta: dict,
) -> dict:
    import httpx
    from playwright.async_api import async_playwright

    headers = {"X-Harness-Token": token}
    traj = json.loads(Path(traj_path).read_text())
    steps = traj.get("steps") or []
    historical = disposition_from_verifier(traj.get("verifier_result"))

    async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
        r = await client.post(
            f"{base}/_harness/reset",
            json={"task_id": task_id, "seed": seed, "ui": "normal"},
        )
        r.raise_for_status()
        reset = r.json()
        start_path = reset.get("start_path") or "/"

        action_errors: list[dict] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()
            # Multi-tab map (M2): keep real Playwright pages instead of
            # collapsing open_tab into same-page navigate.
            tabs: dict[str, object] = {"main": page}
            active_tab_id = "main"
            start_url = base.rstrip("/") + (
                start_path if start_path.startswith("/") else "/" + start_path
            )

            async def _goto(target_page, url: str, *, timeout_ms: int = 60000) -> None:
                """Goto with longer timeout + one retry (M249 seed1 infra)."""
                last_err: Exception | None = None
                for attempt in range(2):
                    try:
                        await target_page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=timeout_ms,
                        )
                        return
                    except Exception as e:  # noqa: BLE001 — replay best-effort
                        last_err = e
                        await target_page.wait_for_timeout(500 * (attempt + 1))
                assert last_err is not None
                raise last_err

            await _goto(page, start_url)

            vr = {"success": False, "score": 0.0}
            for i, step in enumerate(steps):
                page = tabs.get(active_tab_id) or page  # type: ignore[assignment]
                # Advance async scheduler like the harness (before observation).
                # Extra post-tick settle helps M372/M373/M120 races without
                # changing verifier semantics.
                try:
                    await client.post(
                        f"{base}/_harness/tick", json={"step": i}
                    )
                except Exception:
                    pass
                await page.wait_for_timeout(75)

                kind = step.get("action_kind") or ""
                args = step.get("action_args") or {}
                try:
                    if kind == "navigate":
                        url = args.get("url") or args.get("path") or "/"
                        if not url.startswith("http"):
                            url = base.rstrip("/") + url
                        await _goto(page, url)
                    elif kind == "click":
                        sel = args["selector"]
                        await page.click(sel, timeout=8000)
                    elif kind == "fill":
                        sel = args["selector"]
                        val = args.get("value", "")
                        await page.fill(sel, str(val), timeout=8000)
                    elif kind == "select":
                        sel = args["selector"]
                        val = args.get("value")
                        await page.select_option(sel, val, timeout=8000)
                    elif kind == "check":
                        await page.check(args["selector"], timeout=8000)
                    elif kind == "uncheck":
                        await page.uncheck(args["selector"], timeout=8000)
                    elif kind == "press":
                        key = args.get("key") or args.get("value")
                        sel = args.get("selector")
                        if sel:
                            await page.press(sel, key, timeout=8000)
                        else:
                            await page.keyboard.press(key)
                    elif kind == "type":
                        sel = args.get("selector")
                        text = args.get("text") or args.get("value") or ""
                        if sel:
                            await page.type(sel, text, timeout=8000)
                        else:
                            await page.keyboard.type(text)
                    elif kind == "submit":
                        sel = args.get("selector")
                        if sel:
                            await page.locator(sel).evaluate(
                                "el => el.closest('form')?.requestSubmit?.() "
                                "|| el.click()"
                            )
                        else:
                            await page.keyboard.press("Enter")
                    elif kind in ("wait", "noop"):
                        await page.wait_for_timeout(
                            int(args.get("ms", 200))
                        )
                    elif kind == "open_tab":
                        url = args.get("url") or "/"
                        if not url.startswith("http"):
                            url = base.rstrip("/") + url
                        tab_id = str(
                            args.get("tab_id")
                            or args.get("id")
                            or f"tab_{len(tabs)}"
                        )
                        new_page = await context.new_page()
                        await _goto(new_page, url)
                        tabs[tab_id] = new_page
                        active_tab_id = tab_id
                        page = new_page
                    elif kind == "switch_tab":
                        tab_id = str(
                            args.get("tab_id")
                            or args.get("id")
                            or args.get("target")
                            or ""
                        )
                        if tab_id in tabs:
                            active_tab_id = tab_id
                            page = tabs[tab_id]  # type: ignore[assignment]
                            await page.bring_to_front()
                        else:
                            action_errors.append(
                                {
                                    "step": i,
                                    "kind": kind,
                                    "error": f"unknown_tab:{tab_id}",
                                }
                            )
                    elif kind == "close_tab":
                        tab_id = str(
                            args.get("tab_id")
                            or args.get("id")
                            or active_tab_id
                        )
                        if tab_id in tabs and tab_id != "main":
                            await tabs[tab_id].close()  # type: ignore[union-attr]
                            del tabs[tab_id]
                            active_tab_id = "main"
                            page = tabs["main"]  # type: ignore[assignment]
                    else:
                        action_errors.append(
                            {
                                "step": i,
                                "kind": kind,
                                "error": f"unsupported_action:{kind}",
                            }
                        )
                except Exception as e:
                    action_errors.append(
                        {"step": i, "kind": kind, "error": str(e)[:300]}
                    )

                # Settle, then verify AFTER each action so URL-gated
                # milestones latch the same way the live harness does.
                await page.wait_for_timeout(50)
                try:
                    vr = (
                        await client.post(
                            f"{base}/_harness/verify",
                            json={"url": page.url, "step": i},
                        )
                    ).json()
                except Exception as e:
                    action_errors.append(
                        {
                            "step": i,
                            "kind": "verify",
                            "error": str(e)[:300],
                        }
                    )

            final_url = page.url
            await browser.close()

        # Full state dump
        try:
            world = (await client.get(f"{base}/_harness/world")).json()
        except Exception:
            world = None
        try:
            state = (await client.get(f"{base}/_harness/state")).json()
        except Exception:
            state = None

    replay_disp = disposition_from_verifier(vr)
    matched = replay_disp == historical
    # Also treat success-bool match as verification when both known
    hist_vr = traj.get("verifier_result") or {}
    if hist_vr.get("success") is not None and vr.get("success") is not None:
        matched = bool(vr.get("success")) == bool(hist_vr.get("success"))

    result = {
        "schema_version": 1,
        "task_id": task_id,
        "seed": seed,
        "traj_path": traj_path,
        "source_commit": meta["source_commit"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_steps_replayed": len(steps),
        "n_action_errors": len(action_errors),
        "action_errors_sample": action_errors[:8],
        "historical_disposition": historical,
        "replay_disposition": replay_disp,
        "historical_success": hist_vr.get("success"),
        "replay_success": vr.get("success"),
        "historical_score": hist_vr.get("score"),
        "replay_score": vr.get("score"),
        "replay_verified": matched,
        "replay_verifier_result": vr,
        "final_url": final_url,
    }

    paths = snapshot_paths(task_id, seed)
    # Augment final snapshot with full state from replay
    final_payload = {
        "schema_version": 1,
        "snapshot_kind": "final",
        "capture_source": "replay_harness",
        "task_id": task_id,
        "seed": seed,
        "source_commit": meta["source_commit"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "traj_path": traj_path,
        "historical_disposition": historical,
        "replay_disposition": replay_disp,
        "verifier_result": vr,
        "world": world,
        "state": state,
        "final_url": final_url,
    }
    write_json(paths["final"], final_payload)
    write_json(paths["replay"], result)
    return result


async def _worker(
    worker_id: int,
    port: int,
    token: str,
    jobs: list[dict],
    meta: dict,
) -> list[dict]:
    proc = _start_server(port, token)
    base = f"http://127.0.0.1:{port}"
    results = []
    try:
        await _wait_ready(base, token)
        for j, job in enumerate(jobs):
            key = f"{job['task_id']}|{job['seed']}"
            paths = snapshot_paths(job["task_id"], job["seed"])
            if paths["replay"].exists():
                existing = json.loads(paths["replay"].read_text())
                results.append(existing)
                continue
            try:
                res = await _replay_episode(
                    base=base,
                    token=token,
                    task_id=job["task_id"],
                    seed=job["seed"],
                    traj_path=job["traj_path"],
                    meta=meta,
                )
                results.append(res)
            except Exception as e:
                err = {
                    "task_id": job["task_id"],
                    "seed": job["seed"],
                    "traj_path": job["traj_path"],
                    "replay_verified": False,
                    "error": str(e),
                    "traceback": traceback.format_exc()[-800:],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                write_json(paths["replay"], err)
                results.append(err)
            if (j + 1) % 10 == 0:
                print(
                    f"[replay w{worker_id}] {j+1}/{len(jobs)}",
                    flush=True,
                )
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--base-port", type=int, default=8760)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    assert_sellable_untouched()
    meta = source_commit_meta()
    index = json.loads((INVENTORY_DIR / "best_traj_index.json").read_text())

    jobs = []
    skipped = {"pixel_only": 0, "no_evidence": 0, "other": 0}
    for tid in load_task_ids():
        for seed in (0, 1, 2):
            key = f"{tid}|{seed}"
            info = index.get(key) or {}
            best = info.get("best")
            cls = info.get("evidence_class")
            if cls == "selector_replayable" and best and not best.get("corrupt"):
                jobs.append(
                    {
                        "task_id": tid,
                        "seed": seed,
                        "traj_path": best["path"],
                    }
                )
            elif cls == "pixel_only":
                skipped["pixel_only"] += 1
            elif cls == "no_evidence":
                skipped["no_evidence"] += 1
            else:
                skipped["other"] += 1

    if args.limit:
        jobs = jobs[: args.limit]

    print(
        f"[replay] {len(jobs)} selector-replayable jobs; skipped={skipped}",
        flush=True,
    )
    if not jobs:
        write_json_pretty(
            CHECKPOINT_DIR / "replay_summary.json",
            {"n_jobs": 0, "skipped": skipped},
        )
        return

    # Split across workers
    n = args.workers
    chunks = [jobs[i::n] for i in range(n)]
    token = os.environ.get("HARNESS_TOKEN") or "seed-snapshot-backfill-token"
    os.environ["HARNESS_TOKEN"] = token

    async def run_all():
        tasks = []
        for i, chunk in enumerate(chunks):
            if not chunk:
                continue
            tasks.append(
                _worker(i, args.base_port + i, token, chunk, meta)
            )
        parts = await asyncio.gather(*tasks)
        out = []
        for p in parts:
            out.extend(p)
        return out

    results = asyncio.run(run_all())
    verified = sum(1 for r in results if r.get("replay_verified") is True)
    mismatched = sum(
        1
        for r in results
        if r.get("replay_verified") is False and "error" not in r
    )
    errors = sum(1 for r in results if "error" in r)
    summary = {
        "n_jobs": len(jobs),
        "n_results": len(results),
        "replay_verified_true": verified,
        "replay_mismatch": mismatched,
        "replay_errors": errors,
        "skipped": skipped,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": meta["source_commit"],
    }
    write_json_pretty(CHECKPOINT_DIR / "replay_summary.json", summary)
    print(json.dumps(summary, indent=2))
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
