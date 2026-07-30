"""No-LLM smoke test for the new-UI harness driver (B).

Drives the realistic mock UIs with the REAL pixel machinery (open_app_tabs +
extract_marks + click_mark) using a deterministic mark picker instead of a model,
and asserts the action flows mock -> bridge -> gym (the gym world mutates + the
harness records a mock screenshot). Proves the plumbing without spending API.

Prereqs: gym + bridge (BRIDGE_TICK=0) + the amazon & gmail mocks running. Set:
  GYM_URL (default http://127.0.0.1:8078), BRIDGE_URL (http://127.0.0.1:8091),
  HARNESS_TOKEN (must match the gym), APP_ORIGINS (shop=...,mail=...).
Run:  HARNESS_TOKEN=... python -m tools.newui_harness_smoke
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

from harness.auth import harness_headers
from harness.runner import BrowserCtx, Trajectory, open_browser
from harness.som import extract_marks

GYM = os.environ.get("GYM_URL", "http://127.0.0.1:8078")
BRIDGE = os.environ.get("BRIDGE_URL", "http://127.0.0.1:8091")
APP_ORIGINS = {}
for part in os.environ.get(
        "APP_ORIGINS",
        "shop=http://127.0.0.1:5203,mail=http://127.0.0.1:5401").split(","):
    if "=" in part:
        k, v = part.split("=", 1)
        APP_ORIGINS[k.strip()] = v.strip()
TASK = os.environ.get("SMOKE_TASK", "A1/buy_wireless_mouse")
SHOTS = Path(os.environ.get("SMOKE_SHOTS", "/tmp/newui_smoke_shots"))


async def _by_text(page, needle):
    marks = await extract_marks(page)
    return marks, [m for m in marks if needle.lower() in (m.name or "").lower()]


async def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(headers=harness_headers()) as c:
        (await c.post(f"{GYM}/_harness/reset",
                      json={"task_id": TASK, "seed": 0})).raise_for_status()

    pw, browser, ctx_browser, page = await open_browser(
        server_url=GYM, headless=True, record_video=False)
    traj = Trajectory(episode_id=uuid.uuid4().hex[:8], task_id=TASK, seed=0,
                      agent_name="scripted", started_at=time.time(), task_brief="",
                      task_difficulty="", task_category="", ui_variant="normal")
    bctx = BrowserCtx(page=page, server_url=GYM, trajectory=traj,
                      screenshot_dir=SHOTS, app_origins=APP_ORIGINS, bridge_url=BRIDGE)

    fails = []
    def check(n, cond, extra=""):
        print(("PASS" if cond else "FAIL"), n, extra)
        if not cond:
            fails.append(n)

    await bctx.open_app_tabs(list(APP_ORIGINS), "shop")
    await asyncio.sleep(2.5)
    check("primary tab is the mock", "bridge=" in bctx.page.url, bctx.page.url)

    marks, hits = await _by_text(bctx.page, "Studio Laptop")
    if hits:
        await bctx.click_mark(hits[0].mark_id, marks)
        await asyncio.sleep(1.5)
    marks, hits = await _by_text(bctx.page, "Add to Cart")
    check("Add to Cart mark on product page", bool(hits), f"url={bctx.page.url}")
    if hits:
        rec = await bctx.click_mark(hits[0].mark_id, marks)
        await asyncio.sleep(1.0)
        check("mock screenshot recorded", bool(rec.screenshot_path)
              and Path(rec.screenshot_path).exists())

    async with httpx.AsyncClient(headers=harness_headers()) as c:
        w = (await c.get(f"{GYM}/_harness/world_full")).json()
    cart = (w.get("shop") or {}).get("cart", {}).get("items", [])
    log = [a.get("kind") for a in (w.get("shop") or {}).get("action_log", [])]
    check("UI action reached the gym (cart)", len(cart) >= 1, f"cart={len(cart)}")
    check("gym logged add_to_cart", "add_to_cart" in log, f"log={log[-3:]}")

    await ctx_browser.close(); await browser.close(); await pw.stop()
    print("\n=== RESULT:", "ALL PASS" if not fails else f"FAIL {fails}", "===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
