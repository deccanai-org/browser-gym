"""Capture live-gym seed_initial.png/json for a list of tasks x seeds.

$0 API — no model. Reset the gym (task, seed), pre-navigate to start_path
exactly like eval/run.py, screenshot before any action. Uses the pinned
viewport and this week's seed_initial pairing semantics.

Output: screenshots/{Mxx__slug}/seed_state/seed{N}_initial.png/.json

Usage:
    .venv/bin/python scripts/capture_seed_initials.py --port 8074
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.auth import ensure_harness_token, harness_headers  # noqa: E402
from harness.runner import open_browser, reset_gym  # noqa: E402

import httpx  # noqa: E402

TASK_IDS = [
    'M40', 'M41', 'M47', 'M51', 'M57', 'M68', 'M72', 'M73', 'M74', 'M76',
    'M77', 'M78', 'M79', 'M81', 'M82', 'M83', 'M84', 'M86', 'M87', 'M90',
    'M91', 'M92', 'M93', 'M94', 'M95', 'M96', 'M97', 'M98', 'M99', 'M100',
    'M101', 'M102', 'M104', 'M148', 'M164', 'M200', 'M207', 'M210', 'M212',
    'M214', 'M217', 'M219', 'M220', 'M224', 'M227',
]
SEEDS = [0, 1, 2]


def _slug_map() -> dict[str, str]:
    out = {}
    for d in os.listdir(ROOT / 'seed_snapshots'):
        if '__' in d:
            out[d.split('__')[0]] = d
    return out


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
            return proc
        time.sleep(1)
    proc.kill()
    raise RuntimeError(f"server on :{port} failed to come up")


async def amain(server_url: str) -> None:
    slugs = _slug_map()
    pw, browser, ctx_browser, page = await open_browser(
        server_url=server_url, headless=True, record_video=False)
    try:
        for mid in TASK_IDS:
            slug_dir = slugs[mid]
            task_id = slug_dir.replace('__', '/', 1)
            out_dir = ROOT / 'screenshots' / slug_dir / 'seed_state'
            out_dir.mkdir(parents=True, exist_ok=True)
            for seed in SEEDS:
                png = out_dir / f"seed{seed}_initial.png"
                if png.exists():
                    continue
                reset = await reset_gym(server_url, task_id, seed, ui="normal")
                start_path = reset.get("start_path", "/")
                await page.goto(f"{server_url}{start_path}", wait_until="load")
                async with httpx.AsyncClient(headers=harness_headers()) as c:
                    snap = (await c.get(f"{server_url}/_harness/snapshot")).json()
                    try:
                        world = (await c.get(f"{server_url}/_harness/world")).json()
                    except Exception:
                        world = {"snapshot": snap}
                (out_dir / f"seed{seed}_initial.live.json").write_text(
                    json.dumps({
                        "schema_version": 1,
                        "snapshot_kind": "seed_initial",
                        "task_id": task_id, "seed": seed,
                        "url": page.url,
                        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "provenance": "live gym capture 2026-07-24 "
                                      "(post infra fix; no model, $0 API)",
                        "compact_snapshot": snap,
                        "world": world,
                    }, indent=2, default=str), encoding="utf-8")
                await page.screenshot(path=str(png), full_page=False)
                print(f"[seed-init] {task_id} seed={seed} -> {png}", flush=True)
    finally:
        await ctx_browser.close()
        await browser.close()
        await pw.stop()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8074)
    args = ap.parse_args()
    ensure_harness_token()
    os.chdir(ROOT)
    proc = start_server(args.port)
    try:
        asyncio.run(amain(f"http://127.0.0.1:{args.port}"))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    print("[seed-init] done", flush=True)


if __name__ == "__main__":
    main()
