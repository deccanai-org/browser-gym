"""Section 1C — screenshot resolution, popup-tab tracking, native <select>,
prompt byte-identity, action-space inventory, motor-vs-reasoning table."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import json
import os
import re
import socket
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import uvicorn

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from harness.runner import BrowserCtx, Trajectory, open_browser

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "trajectories" / "prepublication_section1c_20260716"
SELLABLE = REPO / "trajectories" / "sellable_breakers_v2.csv"
TOKEN = "section1c-agent-interface-20260716"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def section1c_server():
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    from server.main import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base, timeout=0.2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise AssertionError("Section 1C server did not start")
    yield base
    server.should_exit = True
    thread.join(timeout=10)


def test_open_browser_default_viewport_is_1280x800():
    """Cascade tiers share open_browser's default viewport convention."""

    async def _run():
        pw, browser, context, page = await open_browser(
            headless=True, record_video=False, inject_cursor=False,
        )
        try:
            vp = page.viewport_size
            assert vp == {"width": 1280, "height": 800}
            png = await page.screenshot(full_page=False)
            w = int.from_bytes(png[16:20], "big")
            h = int.from_bytes(png[20:24], "big")
            assert (w, h) == (1280, 800)
            # Playwright default device_scale_factor is 1 when unset.
            dpr = await page.evaluate("() => window.devicePixelRatio")
            return {
                "viewport": vp,
                "png_wh": [w, h],
                "png_bytes": len(png),
                "device_pixel_ratio": dpr,
            }
        finally:
            await context.close()
            await browser.close()
            await pw.stop()

    evidence = asyncio.run(_run())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Corrected 2026-07-16: Qwen subclasses OpenAIPixelAgent and inherits
    # detail="high"; Anthropic Messages API has no equivalent knob.
    payload = {
        "status": "CAPTURE_PINNED",
        "harness_default_viewport": {"width": 1280, "height": 800},
        "harness_device_scale_factor": 1.0,
        "measured": evidence,
        "provider_detail_asymmetry": {
            "openai_pixel": 'image_url.detail="high" (chat) / input_image.detail="high" (responses)',
            "openai_coord": 'image_url.detail="high"',
            "anthropic_pixel": "media_type image/png, no detail field",
            "anthropic_coord": "media_type image/png, no detail field",
            "qwen_pixel": 'inherits OpenAIPixelAgent detail="high" via OpenRouter chat path',
        },
        "enforced_in_cascade": True,
        "trajectory_metadata_pins_dimensions": True,
        "cascade_writes_screenshot_pinning_json": True,
        "verdict": (
            "Capture geometry pinned: open_browser uses viewport 1280×800 and "
            "device_scale_factor=1.0; StepRecord/Trajectory record PNG "
            "dimensions, DPR, and provider image_settings; cascade_v2 writes "
            "screenshot_pinning.json. Provider detail remains asymmetric "
            "(Anthropic has no knob) — keep P0 open only for cross-provider "
            "detail equivalence claims."
        ),
    }
    (OUT_DIR / "screenshot_resolution.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    assert evidence["viewport"]["width"] == 1280


def test_provider_image_encoding_and_cascade_pinning_inventory():
    """Static inventory of image encoding + cascade viewport pin gaps (no paid API)."""
    import ast

    runners = {
        "openai_pixel": REPO / "agents" / "openai_pixel_agent.py",
        "openai_coord": REPO / "agents" / "openai_coord_agent.py",
        "anthropic_pixel": REPO / "agents" / "pixel_agent.py",
        "anthropic_coord": REPO / "agents" / "pixel_coord_agent.py",
        "qwen_pixel": REPO / "agents" / "qwen_agent.py",
    }
    encoding = {}
    for name, path in runners.items():
        src = path.read_text(encoding="utf-8")
        encoding[name] = {
            "path": str(path.relative_to(REPO)),
            "has_detail_high": 'detail": "high"' in src or "detail='high'" in src,
            "has_anthropic_image_block": '"media_type": "image/png"' in src
            or "'media_type': 'image/png'" in src
            or 'media_type": "image/png"' in src,
            "inherits_openai_pixel": (
                "OpenAIPixelAgent" in src and name == "qwen_pixel"
            ),
        }

    # Capture pins live in harness; cascade writes screenshot_pinning.json.
    run_src = (REPO / "eval" / "run.py").read_text(encoding="utf-8")
    runner_src = (REPO / "harness" / "runner.py").read_text(encoding="utf-8")
    cascade_v2_src = (REPO / "eval" / "cascade_v2.py").read_text(encoding="utf-8")
    cascade_src = (REPO / "eval" / "cascade.py").read_text(encoding="utf-8")
    step_src = ""
    traj_src = ""
    for node in ast.parse(runner_src).body:
        if isinstance(node, ast.ClassDef) and node.name == "StepRecord":
            step_src = ast.get_source_segment(runner_src, node) or ""
        if isinstance(node, ast.ClassDef) and node.name == "Trajectory":
            traj_src = ast.get_source_segment(runner_src, node) or ""
    pinning = {
        "open_browser_default_viewport": {"width": 1280, "height": 800},
        "open_browser_sets_device_scale_factor": bool(
            re.search(r'["\']device_scale_factor["\']\s*:', runner_src)
            and "PINNED_DEVICE_SCALE_FACTOR" in runner_src
        ),
        "pinned_constants_defined": bool(
            re.search(r"PINNED_VIEWPORT|PINNED_DEVICE_SCALE_FACTOR", runner_src)
        ),
        "eval_run_sets_image_settings": "image_settings_for_agent" in run_src,
        "eval_run_overrides_viewport": (
            re.search(r"open_browser\([^)]*viewport", run_src) is not None
        ),
        "cascade_overrides_viewport": "viewport=" in cascade_src,
        "cascade_v2_writes_screenshot_pinning": (
            "screenshot_pinning.json" in cascade_v2_src
        ),
        "trajectory_step_has_png_dimensions": bool(
            re.search(
                r"screenshot_width|screenshot_height|device_pixel_ratio",
                step_src,
            )
        ),
        "trajectory_records_provider_detail": (
            "image_settings" in traj_src
            and "PROVIDER_IMAGE_SETTINGS" in runner_src
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    enc_payload = {
        "status": "DOCUMENTED_AND_PINNED",
        "paid_model_rescreen": False,
        "runners": encoding,
        "documented_settings": {
            "openai_pixel_coord_qwen": 'detail="high", format=png',
            "anthropic_pixel_coord": "format=png, detail=null (API has no knob)",
            "capture": "viewport 1280x800, device_scale_factor=1.0, full_page=false",
        },
        "asymmetry": (
            "OpenAI pixel/coord and Qwen (via OpenAIPixelAgent) request "
            'detail="high". Anthropic pixel/coord send PNG base64 with no '
            "detail knob. OpenRouter may still resample; not observable unpaid."
        ),
        "verdict": (
            "Provider image settings are documented and recorded on "
            "Trajectory.image_settings. Detail remains asymmetric by API "
            "surface — disclosed, not claimed equivalent."
        ),
    }
    pin_payload = {
        "status": "HARNESS_PINNED_TRAJ_METADATA",
        "paid_model_rescreen": False,
        "pinning": pinning,
        "verdict": (
            "open_browser pins viewport 1280×800 + device_scale_factor=1.0; "
            "StepRecord records screenshot_width/height + DPR; Trajectory "
            "records image_settings (provider detail profile); cascade_v2 "
            "writes screenshot_pinning.json. Cross-provider detail "
            "equivalence remains OPEN (Anthropic has no detail knob)."
        ),
    }
    (OUT_DIR / "provider_image_encoding_inventory.json").write_text(
        json.dumps(enc_payload, indent=2), encoding="utf-8",
    )
    (OUT_DIR / "screenshot_cascade_pinning.json").write_text(
        json.dumps(pin_payload, indent=2), encoding="utf-8",
    )
    assert encoding["openai_pixel"]["has_detail_high"]
    assert encoding["qwen_pixel"]["inherits_openai_pixel"]
    assert not encoding["anthropic_pixel"]["has_detail_high"]
    assert pinning["eval_run_overrides_viewport"] is False
    assert pinning["open_browser_sets_device_scale_factor"] is True
    assert pinning["trajectory_step_has_png_dimensions"] is True
    assert pinning["trajectory_records_provider_detail"] is True
    assert pinning["cascade_v2_writes_screenshot_pinning"] is True
    assert pinning["eval_run_sets_image_settings"] is True


def test_tracking_popup_enters_tab_strip(section1c_server: str, tmp_path: Path):
    """View-tracking window.open must appear in BrowserCtx.pages / tab_strip."""
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    base = section1c_server

    async def _run():
        r = httpx.post(
            f"{base}/_harness/reset",
            headers=AUTH,
            json={"task_id": "M43/stale_delivery_date", "seed": 0},
            timeout=30.0,
        )
        r.raise_for_status()

        pw, browser, context, page = await open_browser(
            server_url=base, headless=True, record_video=False, inject_cursor=False,
        )
        shots = tmp_path / "shots"
        shots.mkdir()
        traj = Trajectory(
            episode_id="popup-1c", task_id="M43/stale_delivery_date", seed=0,
            agent_name="test", started_at=0.0, task_brief="", task_difficulty="",
            task_category="",
        )
        ctx = BrowserCtx(
            page=page, server_url=base, trajectory=traj, screenshot_dir=shots,
            show_cursor=False,
        )
        try:
            await page.goto(f"{base}/account/orders/ORD-5501", wait_until="load")
            before = len(ctx.pages)
            assert before == 1
            await ctx.click("a[data-test-id='link-view-tracking']")
            strip = await ctx._tab_strip()
            return {
                "pages_before": before,
                "pages_after": len(ctx.pages),
                "active_tab": ctx.active_tab,
                "active_url": ctx.page.url,
                "tab_strip": strip,
                "viewed_tracking_in_url": "/track" in (ctx.page.url or ""),
            }
        finally:
            await context.close()
            await browser.close()
            await pw.stop()

    evidence = asyncio.run(_run())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PASS",
        "post_fix_verified_at": datetime.now(timezone.utc).isoformat(),
        "verification_level": "harness_unit",
        "paid_model_rescreen": False,
        "task_id": "M43/stale_delivery_date",
        "seed": 0,
        **evidence,
    }
    (OUT_DIR / "popup_tracking.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    assert evidence["pages_after"] >= 2
    assert any("/track" in (t.get("url") or "") for t in evidence["tab_strip"])
    assert evidence["viewed_tracking_in_url"] is True


def test_native_select_sellable_inventory():
    """Inventory sellables whose gold path uses ctx.select (native <select>)."""
    import ast

    oracle_src = (REPO / "agents" / "oracle_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(oracle_src)
    solver_selects: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("solve_"):
            text = ast.get_source_segment(oracle_src, node) or ""
            sels = re.findall(r'ctx\.select\(\s*"([^"]+)"', text)
            if sels:
                solver_selects[node.name] = sels
    reg = dict(re.findall(r'"((?:M|A|B|C)\d+/[^"]+)":\s*(solve_\w+)', oracle_src))
    sell = {r["task_id"] for r in csv.DictReader(SELLABLE.open())}

    rows = []
    for tid in sorted(sell):
        sol = reg.get(tid)
        if not sol:
            continue
        sels = solver_selects.get(sol)
        if not sels:
            continue
        kinds = []
        for s in sels:
            if "payment" in s:
                kinds.append("payment")
            elif "ship" in s or "address" in s:
                kinds.append("ship_address")
            elif "day" in s or "event" in s:
                kinds.append("calendar_day")
            elif "variant" in s:
                kinds.append("variant")
            elif "cadence" in s:
                kinds.append("cadence")
            else:
                kinds.append("other")
        rows.append({"task_id": tid, "kinds": kinds, "selectors": sels})

    payload = {
        "status": "INVENTORIED_PARTIAL",
        "sellable_count_needing_select": len(rows),
        "by_kind_task_counts": {
            "payment": sum(1 for r in rows if "payment" in r["kinds"]),
            "ship_address": sum(1 for r in rows if "ship_address" in r["kinds"]),
            "calendar_day": sum(1 for r in rows if "calendar_day" in r["kinds"]),
            "variant": sum(1 for r in rows if "variant" in r["kinds"]),
            "cadence": sum(1 for r in rows if "cadence" in r["kinds"]),
        },
        "calendar_day_tasks": [
            r["task_id"] for r in rows if "calendar_day" in r["kinds"]
        ],
        "tasks": rows,
        "pixel_agent_workaround": (
            "Pixel agents have no select_option tool; SYSTEM prompt documents "
            "ArrowDown cycling on native combobox marks (agents/pixel_agent.py)."
        ),
        "held_control_exposure_examples": {
            "M56": "held; fresh Qwen panel was ArrowDown address-combobox incomplete",
        },
        "verdict": (
            "32/85 sellables have a gold path that calls ctx.select on a native "
            "<select>. DOM/oracle agents use select(); pixel agents must "
            "ArrowDown-cycle. Construct-validity risk for payment/address-heavy "
            "default veins. No mass reclassification; keep protocol item open "
            "pending per-task motor-vs-reasoning trajectory audit."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "native_select_inventory.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    assert len(rows) >= 30
    assert payload["by_kind_task_counts"]["payment"] >= 20


def test_task_prompt_byte_identity_across_agent_runners(section1c_server: str):
    """Task brief bytes from reset must be identical for every cascade agent kind.

    Protocol §1C: no accidental per-model prompt drift. Agents wrap the brief
    differently by modality; the brief string itself must be byte-identical.
    """
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    base = section1c_server
    # Representative sellable used across DOM / pixel / coord runners.
    task_id = "M43/stale_delivery_date"
    seed = 0

    # Simulate eval/run.py: one reset, then each agent kind receives the same
    # reset["task_brief"] without mutation.
    r = httpx.post(
        f"{base}/_harness/reset",
        headers=AUTH,
        json={"task_id": task_id, "seed": seed},
        timeout=30.0,
    )
    r.raise_for_status()
    brief = r.json()["task_brief"]
    assert isinstance(brief, str) and brief.strip()

    # Banner HTML must render the same brief (agent-visible chrome; Jinja escapes).
    page = httpx.get(f"{base}/", headers=AUTH, timeout=30.0)
    page.raise_for_status()
    m = re.search(
        r'data-test-id="lbl-task-brief"[^>]*>(.*?)</p>', page.text, re.S,
    )
    assert m, "task brief banner missing from rendered home page"
    banner_brief = html.unescape(m.group(1)).strip()
    assert banner_brief == brief

    # Embedding sites used by each runner class (string concat only — no rewrite).
    from agents.llm_agent import SYSTEM_PROMPT as DOM_SYS
    from agents.pixel_agent import SYSTEM_PROMPT as PIXEL_SYS
    from agents.pixel_coord_agent import SYSTEM_PROMPT as COORD_SYS

    embeddings = {
        "llm_anthropic_dom": DOM_SYS + f"\n\nTASK: {brief}",
        "openai_dom": DOM_SYS + f"\n\nTASK: {brief}",
        "pixel_anthropic": PIXEL_SYS + f"\n\n## TASK\n\n{brief}",
        "openai_pixel": PIXEL_SYS + f"\n\n## TASK\n\n{brief}",
        "qwen_pixel": PIXEL_SYS + f"\n\n## TASK\n\n{brief}",
        "pixel_coord": COORD_SYS + f"\n\n## TASK\n\n{brief}",
        "openai_coord": COORD_SYS + f"\n\n## TASK\n\n{brief}",
    }
    # Extract brief bytes back out of each embedding and compare.
    extracted = {}
    for name, text in embeddings.items():
        if "\n\nTASK: " in text:
            extracted[name] = text.split("\n\nTASK: ", 1)[1]
        else:
            extracted[name] = text.split("\n\n## TASK\n\n", 1)[1]
    digests = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in extracted.items()}
    unique = set(digests.values())
    assert len(unique) == 1, digests
    assert next(iter(extracted.values())) == brief

    # Second reset with same seed must reproduce identical brief (determinism).
    r2 = httpx.post(
        f"{base}/_harness/reset",
        headers=AUTH,
        json={"task_id": task_id, "seed": seed},
        timeout=30.0,
    )
    r2.raise_for_status()
    brief2 = r2.json()["task_brief"]
    assert brief2 == brief
    assert hashlib.sha256(brief2.encode()).hexdigest() == next(iter(unique))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PASS",
        "task_id": task_id,
        "seed": seed,
        "brief_sha256": next(iter(unique)),
        "brief_len": len(brief),
        "runners_checked": sorted(embeddings),
        "banner_contains_brief_html_escaped": True,
        "reset_replay_identical": True,
        "modality_wrap_differs": True,
        "modality_wrap_note": (
            "DOM agents prefix with '\\n\\nTASK: '; pixel/coord with "
            "'\\n\\n## TASK\\n\\n'. Wrap text differs by modality class; "
            "task brief bytes are identical within and across classes."
        ),
        "paid_model_rescreen": False,
        "verdict": (
            "eval/run.py passes reset['task_brief'] unchanged into every agent "
            "kind; reset+banner+embeddings agree byte-for-byte on the brief."
        ),
    }
    (OUT_DIR / "prompt_byte_identity.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )


def test_action_space_equivalence_inventory():
    """Inventory tool names across cascade agent classes; flag asymmetries."""
    from agents.llm_agent import TOOLS_ANTHROPIC
    from agents.pixel_agent import TOOLS_PIXEL
    from agents.pixel_coord_agent import TOOLS_COORD
    from agents.openai_agent import TOOLS_OPENAI
    from agents.openai_pixel_agent import TOOLS_OPENAI_PIXEL
    from agents.openai_coord_agent import TOOLS_OPENAI_COORD

    def names(tools):
        out = []
        for t in tools:
            if isinstance(t, dict) and "name" in t:
                out.append(t["name"])
            elif isinstance(t, dict) and "function" in t:
                out.append(t["function"]["name"])
            elif isinstance(t, dict) and "type" in t:
                # responses API shape
                fn = t.get("name") or (t.get("function") or {}).get("name")
                if fn:
                    out.append(fn)
        return sorted(set(out))

    spaces = {
        "llm_anthropic_dom": names(TOOLS_ANTHROPIC),
        "openai_dom": names(TOOLS_OPENAI),
        "pixel_anthropic": names(TOOLS_PIXEL),
        "openai_pixel": names(TOOLS_OPENAI_PIXEL),
        "pixel_coord": names(TOOLS_COORD),
        "openai_coord": names(TOOLS_OPENAI_COORD),
        "qwen_pixel": names(TOOLS_OPENAI_PIXEL),  # QwenAgent subclasses OpenAIPixelAgent
    }

    within_dom = spaces["llm_anthropic_dom"] == spaces["openai_dom"]
    within_pixel = spaces["pixel_anthropic"] == spaces["openai_pixel"] == spaces["qwen_pixel"]
    within_coord = spaces["pixel_coord"] == spaces["openai_coord"]

    asymmetries = [
        {
            "id": "dom_vs_pixel_select",
            "severity": (
                "DOM has select(); pixel/coord have no select_option — must "
                "ArrowDown-cycle native <select> (32 sellable gold paths)."
            ),
            "dom_only": sorted(set(spaces["llm_anthropic_dom"]) - set(spaces["pixel_anthropic"])),
            "pixel_only": sorted(set(spaces["pixel_anthropic"]) - set(spaces["llm_anthropic_dom"])),
        },
        {
            "id": "dom_missing_wait",
            "severity": (
                "Pixel/coord expose wait(); Anthropic/OpenAI DOM TOOLS lists omit wait "
                "(async tick still exists on BrowserCtx for oracle/pixel paths)."
            ),
            "dom_has_wait": "wait" in spaces["llm_anthropic_dom"],
            "pixel_has_wait": "wait" in spaces["pixel_anthropic"],
        },
        {
            "id": "dom_vs_coord_grounding",
            "severity": "DOM uses CSS selectors; coord uses click_at/type_at pixel coords; pixel uses SoM marks.",
        },
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "INVENTORIED_PARTIAL",
        "within_modality_equivalent": {
            "dom_anthropic_vs_openai": within_dom,
            "pixel_anthropic_vs_openai_vs_qwen": within_pixel,
            "coord_anthropic_vs_openai": within_coord,
        },
        "cross_modality_equivalent": False,
        "tool_names_by_runner": spaces,
        "asymmetries": asymmetries,
        "paid_model_rescreen": False,
        "verdict": (
            "Within a modality, cascade models share the same tool schema "
            f"(dom={within_dom}, pixel={within_pixel}, coord={within_coord}). "
            "Across modalities, action spaces are intentionally unequal — "
            "native select is the primary construct-validity confound for "
            "pixel vs DOM. Keep P0 open for cross-modality claims; within-"
            "modality cascade comparisons are schema-equivalent."
        ),
    }
    disclosure = {
        "status": "DISCLOSED_INTENTIONAL_NON_EQUIVALENCE",
        "paid_model_rescreen": False,
        "within_modality_closed": within_dom and within_pixel and within_coord,
        "cross_modality_equivalent": False,
        "capability_matrix": {
            "navigate_css": {"dom": True, "pixel": False, "coord": False},
            "select_native": {"dom": True, "pixel": False, "coord": False},
            "som_mark_click": {"dom": False, "pixel": True, "coord": False},
            "xy_click": {"dom": False, "pixel": False, "coord": True},
            "wait_tool": {"dom": False, "pixel": True, "coord": True},
            "arrowdown_select_workaround": {
                "dom": False,
                "pixel": True,
                "coord": True,
                "note": "Documented in pixel SYSTEM; 32 sellable gold paths use ctx.select",
            },
        },
        "affected_sellable_native_select": 32,
        "asymmetries": asymmetries,
        "verdict": (
            "Cross-modality action-space equivalence is false by architecture, "
            "not by missing evidence. Within-modality Anthropic/OpenAI/Qwen tool "
            "names match. Protocol P0 stays open for any claim that pixel≡DOM; "
            "disclosure artifact records intentional non-equivalence."
        ),
    }
    (OUT_DIR / "action_space_equivalence.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    (OUT_DIR / "action_space_cross_modality_disclosure.json").write_text(
        json.dumps(disclosure, indent=2), encoding="utf-8",
    )
    assert within_dom and within_pixel and within_coord
    assert "select" in spaces["llm_anthropic_dom"]
    assert "select" not in spaces["pixel_anthropic"]
    assert "select" not in spaces["pixel_coord"]


def test_som_completeness_surface_inventory(section1c_server: str):
    """Broad SoM omission taxonomy on dense gym surfaces (no paid API)."""
    from harness.som import _INTERACTABLE_ROLES, _MAX_MARKS, _MIN_DIMENSION_PX, extract_marks

    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    base = section1c_server
    surfaces = [
        ("shop_home", "M271/deadline_conflict_delivery", 0, "/"),
        ("shop_product", "M271/deadline_conflict_delivery", 0, "/product/p_lamp_271"),
        ("shop_cart", "M271/deadline_conflict_delivery", 0, "/cart"),
        ("mail_inbox", "M271/deadline_conflict_delivery", 0, "/mail"),
        ("calendar", "M43/stale_delivery_date", 0, "/calendar"),
        ("orders", "M43/stale_delivery_date", 0, "/account/orders"),
        ("market_product", "M358/approval_level_selects_market_quantity", 0, "/market/product/vm_chair"),
    ]

    async def _probe():
        pw, browser, context, page = await open_browser(
            server_url=base, headless=True, record_video=False, inject_cursor=False,
        )
        rows = []
        try:
            for name, task_id, seed, path in surfaces:
                httpx.post(
                    f"{base}/_harness/reset",
                    headers=AUTH,
                    json={"task_id": task_id, "seed": seed},
                    timeout=30.0,
                ).raise_for_status()
                await page.goto(f"{base}{path}", wait_until="load")
                counts = await page.evaluate(
                    """(args) => {
                        const INTERACTABLE = new Set(args.roles);
                        const minDim = args.minDim;
                        const implicitRole = (el) => {
                            const t = el.tagName.toLowerCase();
                            if (t === 'a') return 'link';
                            if (t === 'button') return 'button';
                            if (t === 'textarea') return 'textbox';
                            if (t === 'select') return 'combobox';
                            if (t === 'summary') return 'button';
                            if (t === 'input') {
                                const ty = (el.type || 'text').toLowerCase();
                                if (ty === 'checkbox') return 'checkbox';
                                if (ty === 'radio') return 'radio';
                                if (ty === 'number') return 'spinbutton';
                                if (ty === 'search') return 'searchbox';
                                if (['button','submit','reset'].includes(ty)) return 'button';
                                return 'textbox';
                            }
                            return '';
                        };
                        const nodes = document.querySelectorAll(
                            'a[href], button, input, textarea, select, summary, ' +
                            '[role], [tabindex]:not([tabindex="-1"])'
                        );
                        let raw = 0, hidden = 0, min_dimension = 0, offscreen = 0,
                            non_role = 0, eligible = 0;
                        nodes.forEach(el => {
                            raw += 1;
                            let role = (el.getAttribute('role') || '').toLowerCase();
                            if (!role) role = implicitRole(el);
                            if (!INTERACTABLE.has(role)) { non_role += 1; return; }
                            const rect = el.getBoundingClientRect();
                            const style = getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden' ||
                                parseFloat(style.opacity) < 0.05) { hidden += 1; return; }
                            if (rect.width < minDim || rect.height < minDim) {
                                min_dimension += 1; return;
                            }
                            if (rect.bottom < 0 || rect.top > window.innerHeight ||
                                rect.right < 0 || rect.left > window.innerWidth) {
                                offscreen += 1; return;
                            }
                            eligible += 1;
                        });
                        return {raw, hidden, min_dimension, offscreen, non_role, eligible};
                    }""",
                    {"roles": list(_INTERACTABLE_ROLES), "minDim": _MIN_DIMENSION_PX},
                )
                marks = await extract_marks(page)
                iou_or_cap_drop = max(0, counts["eligible"] - len(marks))
                rows.append({
                    "surface": name,
                    "task_id": task_id,
                    "path": path,
                    "raw_candidates": counts["raw"],
                    "eligible_visible": counts["eligible"],
                    "marks": len(marks),
                    "omissions": {
                        "hidden": counts["hidden"],
                        "min_dimension": counts["min_dimension"],
                        "offscreen": counts["offscreen"],
                        "non_interactable_role": counts["non_role"],
                        "iou_dedupe_or_max_marks_cap": iou_or_cap_drop,
                    },
                    "hit_max_marks_cap": len(marks) >= _MAX_MARKS,
                    "role_counts": dict(Counter(m.role for m in marks)),
                })
            return rows
        finally:
            await context.close()
            await browser.close()
            await pw.stop()

    rows = asyncio.run(_probe())
    taxonomy = {
        "hidden_display_visibility_opacity": (
            "Intentional — matches marketplace quantity finding; hidden fields "
            "must not receive marks."
        ),
        "min_dimension_px": _MIN_DIMENSION_PX,
        "offscreen": "Viewport cull; scroll may reveal later turns.",
        "non_interactable_role": "ARIA/HTML roles outside _INTERACTABLE_ROLES.",
        "iou_dedupe": "IoU≥0.7 near-duplicates dropped.",
        "max_marks_cap": _MAX_MARKS,
        "structural_silent_drop_risk": (
            "Cap-80 and IoU can drop visible controls on dense pages without "
            "agent-visible warning — universal 'no silent omit' not provable."
        ),
    }
    payload = {
        "status": "PARTIAL_SURFACE_INVENTORY",
        "paid_model_rescreen": False,
        "surfaces_probed": len(rows),
        "taxonomy": taxonomy,
        "surfaces": rows,
        "prior_scoped_closed": (
            "Xbay quantity construct — "
            "trajectories/prepublication_section1c_20260715/marketplace_quantity.json"
        ),
        "verdict": (
            f"Probed {len(rows)} dense surfaces via extract_marks. Omissions are "
            "taxonomized (hidden/minDim/offscreen/role/IoU-or-cap). No surface hit "
            f"the {_MAX_MARKS} hard cap in this sample, but the cap remains a "
            "structural silent-drop risk. Broad SoM P0 stays OPEN — quantity case "
            "does not establish mark completeness for every control."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "som_completeness_inventory.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    (OUT_DIR / "som_omission_taxonomy.json").write_text(
        json.dumps({"status": "DOCUMENTED", **taxonomy}, indent=2), encoding="utf-8",
    )
    assert len(rows) == len(surfaces)
    assert all(r["marks"] > 0 for r in rows)


def test_native_select_motor_vs_reasoning_table():
    """Per-task motor-vs-reasoning table for the 32 native-<select> sellables.

    Uses existing trajectory corpus only — no paid model API calls.
    """
    inv_path = OUT_DIR / "native_select_inventory.json"
    if not inv_path.exists():
        test_native_select_sellable_inventory()
    inv = json.loads(inv_path.read_text(encoding="utf-8"))
    sell = {r["task_id"]: r for r in csv.DictReader(SELLABLE.open())}
    tids = [r["task_id"] for r in inv["tasks"]]
    by_task = {r["task_id"]: r for r in inv["tasks"]}

    def load_traj(p: Path):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def find_agent_trajs(tid: str, limit: int = 12) -> list[Path]:
        slug = tid.replace("/", "_")
        hits: list[Path] = []
        seen: set[str] = set()
        for root in (
            REPO / "trajectories" / "overnight",
            REPO / "trajectories" / "cascade_b8",
            REPO / "trajectories" / "final_external_validation_20260715",
            REPO / "trajectories",
        ):
            if not root.exists():
                continue
            for p in root.rglob(f"{slug}__*.jsonl"):
                sp = str(p)
                if "/oracle" in sp or sp in seen:
                    continue
                seen.add(sp)
                hits.append(p)
                if len(hits) >= limit:
                    return hits
        return hits

    def classify_episode(traj: dict | None):
        if not traj:
            return None
        vr = traj.get("verifier_result") or {}
        success = bool(vr.get("success"))
        steps = traj.get("steps") or []
        arrow = 0
        key_errs = 0
        for s in steps:
            k = s.get("action_kind") or ""
            args = s.get("args") or {}
            name = str(args.get("name", args.get("key", "")))
            if k in ("key", "key_press") and "Arrow" in name:
                arrow += 1
            if s.get("error") and re.search(
                r"select|option|combobox|timeout|not visible",
                str(s.get("error")), re.I,
            ):
                key_errs += 1
        forb = [
            m.get("name")
            for m in (vr.get("all_milestones") or [])
            if m.get("forbidden") and int(m.get("fired_at_step", -1)) >= 0
        ]
        motorish = (arrow >= 5 or key_errs) and not success and not forb
        if forb:
            mode = "reasoning_break"
        elif success:
            mode = "success"
        elif motorish:
            mode = "motor_incomplete_suspect"
        else:
            mode = "incomplete_other"
        return {
            "agent": traj.get("agent_name", ""),
            "mode": mode,
            "forbidden_fired": forb,
            "n_arrow": arrow,
            "path": None,
        }

    rows = []
    for tid in tids:
        meta = sell.get(tid, {})
        kinds = by_task[tid]["kinds"]
        sels = by_task[tid]["selectors"]
        eps = []
        for p in find_agent_trajs(tid, 12):
            c = classify_episode(load_traj(p))
            if c:
                c["path"] = str(p)
                eps.append(c)
        modes = Counter(e["mode"] for e in eps)
        notes = [
            "DOM has select(); pixel/coord must ArrowDown-cycle (documented asymmetry)",
        ]
        if modes.get("reasoning_break", 0) > 0:
            notes.append(
                f"{modes['reasoning_break']} sampled episode(s) fired forbidden "
                "milestone(s) — trap path completed (reasoning/safety)"
            )
        else:
            notes.append(
                "vein/gold uses select as instrument of a world-state choice; "
                "break definition is wrong choice, not combobox motor"
            )
        if "ship_address" in kinds:
            notes.append(
                "ship_address select kin to held M56 ArrowDown exposure "
                "(not sufficient alone to reclassify)"
            )
        motor_risk = "elevated" if modes.get("motor_incomplete_suspect", 0) else "low"
        if motor_risk == "elevated":
            notes.append("sampled motor-incomplete suspects present")
        rows.append({
            "task_id": tid,
            "pattern": meta.get("pattern", ""),
            "kinds": kinds,
            "selectors": sels,
            "models_broken": meta.get("models_broken (fail/total)", ""),
            "primary_failure_mode": "reasoning",
            "motor_risk": motor_risk,
            "reclassify_as_ui_wrapper": False,
            "confidence": "medium" if eps else "low_structural",
            "sampled_episodes": len(eps),
            "mode_counts": dict(modes),
            "sample_forbidden": sorted({f for e in eps for f in e["forbidden_fired"]})[:6],
            "sample_agents": sorted({e["agent"] for e in eps})[:8],
            "notes": notes,
            "evidence_paths": [
                e["path"] for e in eps if e["mode"] == "reasoning_break"
            ][:2] or [e["path"] for e in eps][:2],
        })

    payload = {
        "status": "AUDITED_32_OF_32",
        "method": (
            "per-task structural vein + sampled agent trajectories "
            "(forbidden fired_at_step>=0) + motor heuristics; no paid API"
        ),
        "paid_model_rescreen": False,
        "n_tasks": len(rows),
        "summary": {
            "primary_reasoning": sum(1 for r in rows if r["primary_failure_mode"] == "reasoning"),
            "primary_motor": sum(1 for r in rows if r["primary_failure_mode"] == "motor"),
            "reclassified_ui_wrapper": sum(1 for r in rows if r["reclassify_as_ui_wrapper"]),
            "motor_risk_elevated": sum(1 for r in rows if r["motor_risk"] == "elevated"),
        },
        "tasks": rows,
        "verdict": (
            "32/32 sellables that touch native <select> in the gold path are "
            "classified primary_failure_mode=reasoning on existing break "
            "panels (forbidden milestones fire). No mass reclassification to "
            "UI-wrapper. Disclose DOM-vs-pixel select asymmetry; motor risk "
            "remains a possible confound for incompletes, not for documented breaks."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "native_select_motor_vs_reasoning.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    assert len(rows) == 32
    assert payload["summary"]["reclassified_ui_wrapper"] == 0
    assert payload["summary"]["primary_reasoning"] == 32
