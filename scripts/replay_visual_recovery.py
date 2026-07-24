"""Mechanical screenshot-recovery replay — NO model, NO new verdicts.

Re-executes the recorded action sequence of an existing trajectory JSONL
against a freshly reset gym (same task_id / seed / ui_variant) and captures
the step_XXX.png filmstrip into the trajectory's ORIGINAL screenshot dir
(the Windows-style path recorded in the traj, normalized to forward slashes).

Also captures the seed_initial / seed_final screenshot+JSON pairing from
this week's infra (eval/run.py), and writes a REPLAY_RECOVERY.json
provenance file per episode dir.

HISTORICAL DISPOSITIONS ARE GROUND TRUTH. The verifier still runs during
replay (the harness probes it after every step), but its output is stored
ONLY as a non-authoritative QA signal in REPLAY_RECOVERY.json. Source
trajectory files are never modified.

Usage (one worker; spins its own uvicorn on --port):
    .venv/bin/python scripts/replay_visual_recovery.py \
        --manifest /tmp/replay_manifest_0.json --port 8071
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.auth import ensure_harness_token, harness_headers  # noqa: E402
from harness.runner import (  # noqa: E402
    BrowserCtx, Trajectory, open_browser, reset_gym,
)

import httpx  # noqa: E402

EPISODE_TIMEOUT_S = 20 * 60


@dataclass
class FakeMark:
    """Stand-in for som.Mark: replay resolves recorded coords, not live marks."""
    mark_id: int
    role: str
    name: str
    center: tuple[int, int]


def _port_open(port: int) -> bool:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/_harness/world", headers=harness_headers())
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def start_server(port: int):
    env = {**os.environ, "AGENT_EVAL_MODE": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app",
         "--port", str(port), "--log-level", "warning"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if _port_open(port):
            print(f"[replay] server up on :{port} (pid {proc.pid})", flush=True)
            return proc
        time.sleep(1)
    proc.kill()
    raise RuntimeError(f"server on :{port} failed to come up")


def _url_path(url: str) -> str:
    """Strip scheme+host so historical (other port) and replay URLs compare."""
    if not url:
        return ""
    if "://" in url:
        url = url.split("://", 1)[1]
        url = "/" + url.split("/", 1)[1] if "/" in url else "/"
    return url


async def _dispatch(ctx: BrowserCtx, kind: str, args: dict) -> None:
    if kind == "click_mark":
        mark = FakeMark(args["mark_id"], args.get("role", ""),
                        args.get("name", ""), tuple(args["coord"]))
        await ctx.click_mark(mark.mark_id, [mark])
    elif kind == "type_into_mark":
        mark = FakeMark(args["mark_id"], args.get("role", ""),
                        args.get("name", ""), tuple(args["coord"]))
        await ctx.type_into_mark(mark.mark_id, [mark], args.get("value", ""))
    elif kind == "key_press":
        await ctx.key_press(args.get("key", ""))
    elif kind == "scroll_by":
        await ctx.scroll_by(args.get("direction", "down"),
                            int(args.get("amount_px", 400)))
    elif kind == "open_tab":
        await ctx.open_tab(args.get("url", "/"))
    elif kind == "switch_tab":
        await ctx.switch_tab(int(args.get("tab_index", 0)))
    elif kind == "close_tab":
        await ctx.close_tab(int(args.get("tab_index", 0)))
    elif kind == "wait":
        await ctx.wait()
    elif kind == "navigate":
        await ctx.goto(args.get("url", "/"))
    elif kind == "click_xy":
        await ctx.click_xy(int(args["x"]), int(args["y"]))
    elif kind == "type_xy":
        await ctx.type_xy(int(args["x"]), int(args["y"]), args.get("value", ""))
    else:
        raise ValueError(f"unknown recorded action_kind: {kind}")


async def replay_episode(traj_path: Path, server_url: str) -> dict:
    src = json.loads(traj_path.read_text(encoding="utf-8"))
    task_id = src["task_id"]
    seed = int(src["seed"])
    ui = src.get("ui_variant") or "normal"
    steps = src.get("steps") or []
    if not steps:
        return {"traj": str(traj_path), "status": "no_steps"}

    shots_dir = Path(steps[0]["screenshot_path"].replace("\\", "/")).parent
    marker = shots_dir / "REPLAY_RECOVERY.json"
    if marker.exists():
        return {"traj": str(traj_path), "status": "already_done"}
    shots_dir.mkdir(parents=True, exist_ok=True)

    reset = await reset_gym(server_url, task_id, seed, ui=ui)
    pw, browser, ctx_browser, page = await open_browser(
        server_url=server_url, headless=True, record_video=False)

    replay_traj = Trajectory(
        episode_id=src["episode_id"], task_id=task_id, seed=seed,
        agent_name=f"replay[{src.get('agent_name', '?')}]",
        started_at=time.time(),
        task_brief=reset.get("task_brief", ""),
        ui_variant=reset.get("ui_variant", ui),
    )
    ctx = BrowserCtx(page=page, server_url=server_url,
                     trajectory=replay_traj, screenshot_dir=shots_dir)

    result: dict = {
        "traj": str(traj_path), "status": "ok", "task_id": task_id,
        "seed": seed, "n_steps_recorded": len(steps),
    }
    try:
        start_path = reset.get("start_path", "/")
        try:
            await page.goto(f"{server_url}{start_path}", wait_until="load")
        except Exception as e:
            print(f"[replay] WARN pre-load {start_path}: {e}", flush=True)

        # seed_initial pair (this week's infra: eval/run.py behavior)
        async with httpx.AsyncClient(headers=harness_headers()) as c:
            snap0 = (await c.get(f"{server_url}/_harness/snapshot")).json()
            try:
                world0 = (await c.get(f"{server_url}/_harness/world")).json()
            except Exception:
                world0 = {"snapshot": snap0}
        (shots_dir / "seed_initial.json").write_text(json.dumps({
            "schema_version": 1, "snapshot_kind": "seed_initial",
            "task_id": task_id, "seed": seed, "url": page.url,
            "compact_snapshot": snap0, "world": world0,
            "provenance": "visual-recovery replay 2026-07-24 (no model)",
        }, indent=2, default=str), encoding="utf-8")
        await page.screenshot(path=str(shots_dir / "seed_initial.png"),
                              full_page=False)

        url_matches = 0
        step_report = []
        for rec in steps:
            await ctx.tick()  # mirror agent-loop turn-start tick
            kind, args = rec["action_kind"], rec.get("action_args") or {}
            try:
                await _dispatch(ctx, kind, args)
            except Exception as e:
                # keep filmstrip indices aligned: record a stub step
                print(f"[replay] step {rec['step_idx']} dispatch error: {e}",
                      flush=True)
                await ctx._record(kind, args, error=f"replay_dispatch: {e}")
            new = replay_traj.steps[-1]
            match = _url_path(new.url_after) == _url_path(rec.get("url_after", ""))
            url_matches += int(match)
            step_report.append({
                "step_idx": rec["step_idx"], "kind": kind,
                "url_recorded": _url_path(rec.get("url_after", "")),
                "url_replayed": _url_path(new.url_after),
                "url_match": match,
                "replay_action_error": new.action_error,
                "recorded_action_error": rec.get("action_error"),
            })

        # final verify — QA ONLY, never authoritative
        async with httpx.AsyncClient(headers=harness_headers()) as c:
            snap_f = (await c.get(f"{server_url}/_harness/snapshot")).json()
            try:
                world_f = (await c.get(f"{server_url}/_harness/world")).json()
            except Exception:
                world_f = {"snapshot": snap_f}
            replay_verify = (await c.post(
                f"{server_url}/_harness/verify",
                json={"url": page.url, "step": len(steps)})).json()

        (shots_dir / "seed_final.json").write_text(json.dumps({
            "schema_version": 1, "snapshot_kind": "seed_final",
            "task_id": task_id, "seed": seed, "url": page.url,
            "compact_snapshot": snap_f, "world": world_f,
            "provenance": "visual-recovery replay 2026-07-24 (no model); "
                          "verifier output here is NON-AUTHORITATIVE — "
                          "historical trajectory verdict is ground truth",
            "replay_verifier_result_non_authoritative": replay_verify,
        }, indent=2, default=str), encoding="utf-8")
        await page.screenshot(path=str(shots_dir / "seed_final.png"),
                              full_page=False)

        hist_v = src.get("verifier_result") or {}
        n = len(steps)
        result.update({
            "url_match_ratio": round(url_matches / max(n, 1), 3),
            "historical_success": hist_v.get("success"),
            "replay_success_discarded": replay_verify.get("success"),
            "verdict_agreement_qa_only":
                hist_v.get("success") == replay_verify.get("success"),
        })
        marker.write_text(json.dumps({
            "kind": "visual-recovery-replay",
            "replayed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source_trajectory": str(traj_path.relative_to(ROOT)
                                     if traj_path.is_absolute() else traj_path),
            "task_id": task_id, "seed": seed,
            "agent_name_historical": src.get("agent_name"),
            "note": ("Screenshots regenerated by mechanical replay of the "
                     "recorded action sequence (no model, $0 API). The "
                     "HISTORICAL verifier disposition in the source "
                     "trajectory remains ground truth; the replay verifier "
                     "output below is recorded for QA only and MUST NOT be "
                     "used as a disposition."),
            "historical_verifier_result": hist_v,
            "replay_verifier_result_non_authoritative": replay_verify,
            "url_match_ratio": result["url_match_ratio"],
            "n_steps": n,
            "steps": step_report,
        }, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        result.update({"status": "error", "error": f"{type(e).__name__}: {e}"})
    finally:
        try:
            await ctx_browser.close()
            await browser.close()
            await pw.stop()
        except Exception:
            pass
    return result


async def amain(manifest: list[str], server_url: str, log_path: Path) -> None:
    done = 0
    with log_path.open("a", encoding="utf-8") as log:
        for i, rel in enumerate(manifest):
            t0 = time.time()
            try:
                res = await asyncio.wait_for(
                    replay_episode(Path(rel), server_url),
                    timeout=EPISODE_TIMEOUT_S)
            except asyncio.TimeoutError:
                res = {"traj": rel, "status": "timeout"}
            except Exception as e:
                res = {"traj": rel, "status": "error",
                       "error": f"{type(e).__name__}: {e}"}
            res["elapsed_s"] = round(time.time() - t0, 1)
            log.write(json.dumps(res) + "\n")
            log.flush()
            done += 1
            print(f"[replay] {done}/{len(manifest)} {rel} -> "
                  f"{res['status']} ({res['elapsed_s']}s "
                  f"match={res.get('url_match_ratio', '-')})", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True,
                    help="JSON file: list of trajectory jsonl paths")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    ensure_harness_token()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    log_path = Path(args.log or f"logs/replay_recovery_{args.port}.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    os.chdir(ROOT)
    proc = start_server(args.port)
    try:
        asyncio.run(amain(manifest, f"http://127.0.0.1:{args.port}", log_path))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    print("[replay] worker finished", flush=True)


if __name__ == "__main__":
    main()
