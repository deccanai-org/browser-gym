"""Episode runner — launch browser, drive the agent, collect rewards.

CLI:
    # Hand-coded oracle (no API key needed) — verifier sanity check
    python -m eval.run --agent oracle --tasks all --seeds 0

    # LLM browser agent (Anthropic)
    python -m eval.run --agent llm --tasks A1/buy_wireless_mouse --seeds 0

    # All 9 tasks, headed, recording video
    python -m eval.run --agent llm --tasks all --seeds 0

Output:
    trajectories/<agent>/<task>__<seed>__<id>.jsonl
    videos/*.webm                                       (Playwright video)
    screenshots/<task>__<seed>__<id>/step_NNN.png

Requires the gym server running first:
    uvicorn server.main:app --reload
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

import httpx

from agents.oracle_agent import SOLVERS as ORACLE_SOLVERS
from harness.auth import ensure_harness_token, harness_headers
from harness.facts import get_fact_extractor
from harness.runner import (
    BrowserCtx, Trajectory, open_browser, reset_gym, save_trajectory,
)


ALL_TASKS = list(ORACLE_SOLVERS.keys())


def _parse_seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def _parse_tasks(spec: str) -> list[str]:
    if spec == "all":
        return ALL_TASKS
    return [t.strip() for t in spec.split(",") if t.strip()]


def _detect_loop(steps: list) -> bool:
    """True if the agent repeated the same (kind, args) 3x in a row.

    Used to feed the universal failure classifier a 'repeated_failed_actions'
    behavioural hint (the server can't see the agent's StepRecords)."""
    last_sig, run = None, 0
    for s in steps:
        sig = (getattr(s, "action_kind", None), repr(getattr(s, "action_args", None)))
        if sig == last_sig:
            run += 1
            if run >= 2:
                return True
        else:
            run, last_sig = 0, sig
    return False


def _agent_name(agent_kind: str, llm_model: str | None) -> str:
    import os
    # OpenAI agents read their model from $OPENAI_MODEL (not the Anthropic --model
    # flag), so record THAT — otherwise the trajectory mislabels e.g. a gpt-5.5 run
    # as the gpt-4o-mini default.
    _oai = llm_model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    if agent_kind == "oracle":
        return "oracle"
    if agent_kind == "pixel":
        return f"pixel[{llm_model or 'default'}]"
    if agent_kind == "pixel_coord":
        return f"pixel_coord[{llm_model or 'default'}]"
    if agent_kind == "openai":
        return f"openai[{_oai}]"
    if agent_kind == "openai_pixel":
        return f"openai_pixel[{_oai}]"
    if agent_kind == "openai_coord":
        return f"openai_coord[{_oai}]"
    if agent_kind == "qwen":
        return f"qwen[{llm_model or 'qwen-vl-plus'}]"
    return f"llm[{llm_model or 'default'}]"


def _invalid_stub_traj(
    *,
    task_id: str,
    seed: int,
    agent_kind: str,
    llm_model: str | None,
    ui: str,
    invalid_reason: str,
    err: str,
) -> Trajectory:
    """Minimal traj for infra failures before a full episode can start."""
    from harness.runner import image_settings_for_agent

    traj = Trajectory(
        episode_id=uuid.uuid4().hex[:8],
        task_id=task_id,
        seed=seed,
        agent_name=_agent_name(agent_kind, llm_model),
        started_at=time.time(),
        task_brief="",
        task_difficulty="",
        task_category="",
        ui_variant=ui,
        image_settings=image_settings_for_agent(agent_kind),
        error=err,
        invalid_reason=invalid_reason,
        invalid_detail=err[:500],
        verifier_result={},
    )
    traj.finished_at = time.time()
    return traj


async def _run_one(*, agent_kind: str, task_id: str, seed: int,
                   server_url: str, headless: bool, record_video: bool,
                   out_traj_dir: Path, out_screens_dir: Path,
                   llm_model: str | None,
                   ui: str = "normal",
                   use_llm_judge: bool = False,
                   resume_state: dict | None = None,
                   resume_step: int | None = None,
                   resume_url: str | None = None,
                   brief_override: str | None = None,
                   correction: str = "",
                   app_origins: dict | None = None,
                   bridge_url: str | None = None) -> Trajectory:
    from harness.invalid_episode import INVALID_BROWSER_CRASH, INVALID_RESET
    from harness.runner import image_settings_for_agent

    # START the episode. Normally reset-to-seed; on RESUME, load a corrected
    # mid-episode world onto SESSION (no reset wipe) and drive FORWARD from it.
    try:
        if resume_state is not None:
            from urllib.parse import urlparse
            async with httpx.AsyncClient(headers=harness_headers()) as c:
                r = await c.post(f"{server_url}/_harness/load_state", json={
                    "task_id": task_id, "seed": seed, "ui": ui,
                    "state": resume_state, "step": resume_step,
                })
                r.raise_for_status()
                st = (await c.get(f"{server_url}/_harness/state")).json()
            reset = {
                "task_brief": st.get("task_brief", ""),
                "task_difficulty": st.get("task_difficulty", "easy"),
                "task_category": st.get("task_category", "A"),
                "ui_variant": ui,
                # navigate to the mid-episode page (a PATH; the goto prefixes host)
                "start_path": (urlparse(resume_url).path or "/") if resume_url else "/",
            }
        else:
            # brief override also updates the SERVER state so the in-page banner +
            # every screenshot render the new instruction (not just the agent).
            reset = await reset_gym(server_url, task_id, seed, ui=ui, brief=brief_override)
        # Belt-and-suspenders (and the resume path, which has no reset_gym): the
        # agent + persisted trajectory record the overridden brief.
        if brief_override:
            reset["task_brief"] = brief_override
        # A drive-forward CORRECTION is the reviewer's instruction for the agent to
        # apply as it continues from the corrected step. Inject it into the brief so
        # the re-run is actually steered by the human's guidance (not a blind re-run).
        if correction.strip():
            reset["task_brief"] = (reset.get("task_brief") or "") + (
                "\n\n[REVIEWER CORRECTION — a human reviewer paused the run at this step "
                f"and instructs you to: {correction.strip()} Follow this guidance as you continue.]"
            )
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        traj = _invalid_stub_traj(
            task_id=task_id, seed=seed, agent_kind=agent_kind,
            llm_model=llm_model, ui=ui,
            invalid_reason=INVALID_RESET, err=err,
        )
        save_trajectory(traj, out_traj_dir)
        return traj

    try:
        pw, browser, ctx_browser, page = await open_browser(
            server_url=server_url, headless=headless,
            record_video=record_video,
            videos_dir=Path("videos") / agent_kind,
        )
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        traj = _invalid_stub_traj(
            task_id=task_id, seed=seed, agent_kind=agent_kind,
            llm_model=llm_model, ui=ui,
            invalid_reason=INVALID_BROWSER_CRASH, err=err,
        )
        save_trajectory(traj, out_traj_dir)
        return traj

    episode_id = uuid.uuid4().hex[:8]
    shots_dir = out_screens_dir / f"{task_id.replace('/', '_')}__{seed}__{episode_id}"
    shots_dir.mkdir(parents=True, exist_ok=True)

    traj = Trajectory(
        episode_id=episode_id, task_id=task_id, seed=seed,
        agent_name=_agent_name(agent_kind, llm_model),
        started_at=time.time(),
        task_brief=reset["task_brief"],
        task_difficulty=reset["task_difficulty"],
        task_category=reset["task_category"],
        ui_variant=reset.get("ui_variant", ui),
        image_settings=image_settings_for_agent(agent_kind),
    )
    bctx = BrowserCtx(
        page=page, server_url=server_url, trajectory=traj,
        screenshot_dir=shots_dir,
        app_origins=app_origins, bridge_url=bridge_url,
    )
    # Cross-app tasks record per-step facts (the substrate for the failure-
    # mode signature builder). Single-app tasks get None -> no facts, no
    # extra world fetch.
    bctx.extract_facts = get_fact_extractor(task_id)

    # Pre-navigate to the gym home page so the agent starts on the
    # rendered site, not about:blank. This simulates "user opens the
    # website in their browser" — the website loading is NOT an agent
    # action, the agent just begins interacting from a loaded page.
    #
    # Without this, the pixel agent (which has no navigate() tool by
    # design — see PIXEL_VS_JSON.md) gets stuck on about:blank with
    # zero interactable marks and bounces uselessly through scrolls
    # and keyboard presses. The DOM agent has navigate() and would
    # emit navigate("/") as its first action anyway — pre-loading
    # just saves it that step.
    start_path = reset.get("start_path", "/")
    if app_origins and bridge_url:
        # Realistic-UI mode: open one tab per mock app (bridged), landing on the
        # task's primary app. The agent drives these SPAs; scoring stays on the gym.
        from harness.runner import _seg_to_app
        primary = _seg_to_app(start_path)
        if primary not in app_origins:
            primary = next(iter(app_origins))
        try:
            await bctx.open_app_tabs(list(app_origins), primary)
        except Exception as e:
            print(f"[runner] WARNING: failed to open bridged app tabs: {e}")
    else:
        try:
            await page.goto(f"{server_url}{start_path}", wait_until="load")
        except Exception as e:
            print(f"[runner] WARNING: failed to pre-load {server_url}{start_path}: {e}")

    # Initial snapshot — captured AFTER pre-navigation so initial_url
    # reflects the actual starting page (typically /), not about:blank.
    traj.initial_url = page.url
    async with httpx.AsyncClient(headers=harness_headers()) as c:
        snap = (await c.get(f"{server_url}/_harness/snapshot")).json()
    traj.initial_snapshot = snap

    # Drive the agent
    try:
        if agent_kind == "oracle":
            solver = ORACLE_SOLVERS[task_id]
            await solver(bctx)
        elif agent_kind == "pixel":
            # Pixel/SoM agent — sees annotated screenshots, acts via mark IDs.
            # No DOM/JSON to the agent. See agents/pixel_agent.py.
            from agents.pixel_agent import PixelBrowserAgent
            agent = PixelBrowserAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
        elif agent_kind == "pixel_coord":
            # Raw pixel-COORDINATE agent — plain screenshot, no Set-of-Mark.
            # Acts via click_at(x, y); the agent must judge the location.
            from agents.pixel_coord_agent import PixelCoordAgent
            agent = PixelCoordAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
        elif agent_kind == "openai":
            # GPT-backed DOM agent (function-calling). Default gpt-4o-mini —
            # the small/cheap model we harvest cross-app failures from.
            from agents.openai_agent import OpenAIBrowserAgent
            agent = OpenAIBrowserAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
        elif agent_kind == "openai_pixel":
            # GPT pixel/SoM agent + multi-tab. Sees annotated screenshots,
            # acts via mark IDs. The hardest setting — visual grounding on a
            # cross-app journey. Default gpt-4o-mini.
            from agents.openai_pixel_agent import OpenAIPixelAgent
            agent = OpenAIPixelAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
        elif agent_kind == "openai_coord":
            # GPT RAW-coordinate agent + multi-tab — plain screenshot, no SoM,
            # acts via click_at(x, y). The OpenAI twin of pixel_coord, for a
            # cross-model leaderboard on the SAME (raw grounding) modality.
            from agents.openai_coord_agent import OpenAICoordAgent
            agent = OpenAICoordAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
        elif agent_kind == "qwen":
            # Qwen-VL (cheap, widely-used) via an OpenAI-compatible endpoint —
            # SoM + multi-tab + async. Needs QWEN_BASE_URL + QWEN_API_KEY.
            from agents.qwen_agent import QwenAgent
            agent = QwenAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
        else:
            from agents.llm_agent import LLMBrowserAgent
            agent = LLMBrowserAgent(model=llm_model)
            await agent.run(bctx, task_brief=reset["task_brief"])
    except Exception as e:
        traj.error = f"{type(e).__name__}: {e}"
        # Protocol §3A: map infra exceptions to machine-readable invalid reasons
        # so classify never counts credit/browser crashes as resist/incomplete.
        from harness.invalid_episode import reason_from_error
        reason = reason_from_error(traj.error)
        if reason and not traj.invalid_reason:
            traj.invalid_reason = reason
            traj.invalid_detail = (traj.error or "")[:500]

    # Final probe — use the ACTIVE tab (bctx.page), which the agent may have
    # switched away from the primary (matters for the multi-tab bridged flow).
    active_url = bctx.page.url
    traj.final_url = active_url
    async with httpx.AsyncClient(headers=harness_headers()) as c:
        try:
            traj.final_snapshot = (await c.get(
                f"{server_url}/_harness/snapshot",
            )).json()
            traj.verifier_result = (await c.post(
                f"{server_url}/_harness/verify",
                json={"url": active_url, "step": len(traj.steps)},
            )).json()
        except Exception as e:
            from harness.invalid_episode import (
                INVALID_VERIFIER_UNAVAILABLE,
                reason_from_error,
            )
            err = f"{type(e).__name__}: {e}"
            traj.error = traj.error or err
            if not traj.invalid_reason:
                traj.invalid_reason = (
                    reason_from_error(err) or INVALID_VERIFIER_UNAVAILABLE
                )
                traj.invalid_detail = err[:500]
            traj.verifier_result = traj.verifier_result or {}
        # Universal failure classification (task-agnostic). Server runs
        # the rule-based classifier against the real GymState; we pass
        # the behavioural hints it can't see (loop detection, step count).
        if not traj.verifier_result.get("success"):
            try:
                cls = (await c.post(
                    f"{server_url}/_harness/classify_failure",
                    json={
                        "url": active_url,
                        "success": traj.verifier_result.get("success", False),
                        "score": traj.verifier_result.get("score", 0.0),
                        "n_steps": len(traj.steps),
                        "had_repeated_actions": _detect_loop(traj.steps),
                        "hit_max_steps": False,
                        "use_llm_fallback": use_llm_judge,
                    },
                )).json()
                traj.agent_failure_class = cls.get("agent_failure_class")
            except Exception as e:
                print(f"[runner] failure classification skipped: {e}")
    # Two-field sellable label (Phase 4): vein (canonical tagger) +
    # specific_failure (fired forbidden milestone). Runs for success AND
    # failure — vein is a task property; specific_failure is None unless a
    # forbidden trap fired. Centralized on the Trajectory object.
    traj.finalize_labels()
    traj.finished_at = time.time()

    # Close browser BEFORE asking for video path — Playwright finalizes
    # the file on close, so a path requested before close may not exist yet.
    await ctx_browser.close()
    await browser.close()
    await pw.stop()

    # Capture video path after close. page.video.path() is async in
    # modern Playwright — must await.
    if record_video and page.video is not None:
        try:
            video_path = await page.video.path()
            traj.video_path = str(video_path) if video_path else ""
        except Exception:
            traj.video_path = ""
    else:
        traj.video_path = ""

    save_trajectory(traj, out_traj_dir)
    return traj


def _print_scorecard(rows: list[Trajectory]) -> None:
    if not rows:
        print("No episodes ran.")
        return
    print()
    print("=" * 96)
    print(f"{'task':<32} {'cat':>4} {'diff':>6} {'seed':>5} {'score':>7} {'success':>8}")
    print("-" * 96)
    for t in rows:
        print(f"{t.task_id:<32} {t.task_category:>4} {t.task_difficulty:>6} "
              f"{t.seed:>5} {t.verifier_result.get('score', 0.0):>7.2f} "
              f"{str(t.verifier_result.get('success', False)):>8}")
    print("-" * 96)
    overall = sum(t.verifier_result.get("score", 0.0) for t in rows) / len(rows)
    succ = sum(1 for t in rows if t.verifier_result.get("success", False)) / len(rows)
    print(f"{'OVERALL':<32} {'':>4} {'':>6} {'':>5} {overall:>7.2f} {succ*100:>7.1f}%")
    print("=" * 96)


def main() -> None:
    # Agents can emit non-cp1252 characters (★, emoji) in their reasoning;
    # make stdout tolerant so a debug print never crashes a step on Windows.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--agent",
        choices=["oracle", "llm", "pixel", "pixel_coord", "openai",
                 "openai_pixel", "openai_coord", "qwen"],
        required=True,
        help="oracle = hand-coded reference; llm = Anthropic DOM/JSON agent; "
             "openai = GPT DOM/JSON agent (default gpt-4o-mini); "
             "pixel = Anthropic SoM screenshots; "
             "pixel_coord = Anthropic RAW-coordinate screenshots (no SoM); "
             "openai_pixel = GPT SoM screenshots + multi-tab (gpt-4o-mini); "
             "openai_coord = GPT RAW-coordinate (no SoM) + multi-tab",
    )
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--headless", action="store_true",
                    help="Hide the browser window. Default: SHOW it.")
    ap.add_argument("--no-video", action="store_true",
                    help="Disable Playwright video recording.")
    ap.add_argument("--model", default=None,
                    help="LLM model id (Anthropic) — overrides default.")
    ap.add_argument("--ui", default="normal",
                    help="Named UI perturbation(s), comma-separated, applied to "
                         "every page (e.g. modal_interruption,low_contrast). "
                         "Default 'normal' = clean.")
    ap.add_argument("--llm-judge", action="store_true",
                    help="On failures the rules can't classify, call an LLM "
                         "judge (Haiku) to pick a universal failure label. "
                         "Costs a few cents per unclassified failure.")
    ap.add_argument("--out-traj", default=None)
    ap.add_argument("--out-screens", default=None)
    # Resume-from-corrected-state: load a world snapshot (too big for argv, so a
    # file) and drive the agent FORWARD from a mid-episode URL instead of reset.
    ap.add_argument("--resume-file", default=None, help="JSON world snapshot to load before driving")
    ap.add_argument("--resume-step", type=int, default=None)
    ap.add_argument("--resume-url", default=None, help="mid-episode URL to navigate to on resume")
    ap.add_argument("--brief-override", default=None, help="drive the agent under a replacement task brief (annotator prompt edit)")
    ap.add_argument("--correction", default="", help="reviewer's instruction injected into the agent's brief on drive-forward resume")
    # Realistic-UI (bridged) mode: drive the CUA-Gym-Hub mock SPAs instead of the
    # gym's own HTML. Browser navigation targets the mock origins (+ ?bridge=);
    # scoring still uses --server (the gym). Requires the bridge service running
    # against the same gym, and each mock served. Same agents/models as usual.
    ap.add_argument("--app-origins", default=None,
                    help="realistic-UI mode: comma map app=origin, e.g. "
                         "shop=http://127.0.0.1:5203,mail=http://127.0.0.1:5401,"
                         "market=http://127.0.0.1:5301,calendar=http://127.0.0.1:5402,"
                         "food=http://127.0.0.1:5403")
    ap.add_argument("--bridge-url", default=None,
                    help="realistic-UI mode: the bridge service URL (e.g. "
                         "http://127.0.0.1:8090). Run it with BRIDGE_TICK=0 so the "
                         "harness owns the scheduler clock.")
    args = ap.parse_args()
    ensure_harness_token()

    app_origins = None
    if args.app_origins:
        app_origins = {}
        for part in args.app_origins.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                app_origins[k.strip()] = v.strip()
    if app_origins and not args.bridge_url:
        print("ERROR: --app-origins requires --bridge-url", file=sys.stderr)
        sys.exit(2)
    # The DOM agents (openai/llm) are single-origin, gym-HTML-selector agents and
    # never tick the scheduler — in bridged mode (BRIDGE_TICK=0, harness owns the
    # clock) time-based cross-app events would never fire. Use a pixel/SoM agent.
    if app_origins and args.agent in ("openai", "llm"):
        print(f"ERROR: --agent {args.agent} can't drive the realistic UIs "
              "(gym-HTML selectors + no scheduler tick). Use pixel / openai_pixel / qwen.",
              file=sys.stderr)
        sys.exit(2)

    resume_state = json.loads(Path(args.resume_file).read_text()) if args.resume_file else None

    tasks = _parse_tasks(args.tasks)
    seeds = _parse_seeds(args.seeds)
    out_traj_dir = Path(args.out_traj or f"trajectories/{args.agent}")
    out_screens_dir = Path(args.out_screens
                           or f"screenshots/{args.agent}")
    out_screens_dir.mkdir(parents=True, exist_ok=True)

    # Quick reach check
    try:
        httpx.get(
            f"{args.server}/_harness/tasks",
            timeout=3.0,
            headers=harness_headers(),
        ).raise_for_status()
    except Exception as e:
        print(f"ERROR: cannot reach gym at {args.server}: {e}\n"
              "Start the server first: uvicorn server.main:app --reload",
              file=sys.stderr)
        sys.exit(2)

    trajectories: list[Trajectory] = []
    started = time.time()
    for task_id in tasks:
        for seed in seeds:
            print(f"\n>>> {args.agent} on {task_id} seed={seed}")
            traj = asyncio.run(_run_one(
                agent_kind=args.agent, task_id=task_id, seed=seed,
                server_url=args.server,
                headless=args.headless,
                record_video=(not args.no_video),
                out_traj_dir=out_traj_dir,
                out_screens_dir=out_screens_dir,
                llm_model=args.model,
                ui=args.ui,
                use_llm_judge=args.llm_judge,
                resume_state=resume_state,
                resume_step=args.resume_step,
                resume_url=args.resume_url,
                brief_override=args.brief_override,
                correction=args.correction,
                app_origins=app_origins,
                bridge_url=args.bridge_url,
            ))
            v = traj.verifier_result
            print(f"  -> score={v.get('score', 0):.2f} "
                  f"success={v.get('success', False)} "
                  f"steps={len(traj.steps)} "
                  f"failure={traj.agent_failure_class or '-'} "
                  f"video={traj.video_path or 'none'}")
            trajectories.append(traj)

    elapsed = time.time() - started
    print(f"\nRan {len(trajectories)} episodes in {elapsed:.1f}s")
    _print_scorecard(trajectories)

    # Save scorecard
    summary = {
        "agent": args.agent,
        "model": args.model,
        "n_episodes": len(trajectories),
        "overall_score": (
            sum(t.verifier_result.get("score", 0.0) for t in trajectories)
            / max(len(trajectories), 1)
        ),
        "overall_success_rate": (
            sum(1 for t in trajectories
                if t.verifier_result.get("success", False))
            / max(len(trajectories), 1)
        ),
        "by_task": {
            task: {
                "n": sum(1 for t in trajectories if t.task_id == task),
                "score": (
                    sum(t.verifier_result.get("score", 0.0)
                        for t in trajectories if t.task_id == task)
                    / max(1, sum(1 for t in trajectories
                                 if t.task_id == task))
                ),
            } for task in tasks
        },
    }
    (out_traj_dir / "_scorecard.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8",
    )
    print(f"Scorecard written to {out_traj_dir}/_scorecard.json")


if __name__ == "__main__":
    main()
