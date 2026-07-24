"""Cloud Run Jobs worker — one Gemini census episode per task index.

Startup:
  1. Read CLOUD_RUN_TASK_INDEX (0..N-1).
  2. Look up (task_id, seed) from the 945-entry (or smoke-5) manifest.
  3. Spin up an isolated Playwright browser + gym server with a unique
     HARNESS_TOKEN derived from the task index.
  4. Run exactly one episode via the Gemini pixel adapter.
  5. Write result JSON to gs://$GCS_BUCKET/results/{task_index}.json
     (or $LOCAL_RESULTS_DIR when GCS is unset / mock mode).

Env (see README.md for the full list):
  CLOUD_RUN_TASK_INDEX, GCS_BUCKET, GEMINI_API_KEY / GEMINI_MODEL,
  GEMINI_MOCK=1 for dry-run without a live Gemini call.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# worker/main.py → deploy/gcp_gemini_screen/worker → repo root is parents[3]
# In the container WORKDIR is /app and the same relative layout is copied.
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from harness.auth import HARNESS_TOKEN_ENV, ensure_harness_token  # noqa: E402

DEFAULT_MODEL = "gemini-3.1-pro-preview"
# Gemini 3.1 Pro ≤200k list rates ($/MTok) — CURRENT_WORK §G / Google list.
RATE_IN_PER_M = float(os.getenv("RATE_GEMINI_IN", "2.0"))
RATE_OUT_PER_M = float(os.getenv("RATE_GEMINI_OUT", "12.0"))


def _log(msg: str) -> None:
    print(f"[gemini-worker] {msg}", flush=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest(path: Path | None = None) -> list[dict]:
    if path is None:
        env_path = os.getenv("MANIFEST_PATH")
        if env_path:
            path = Path(env_path)
        else:
            # Prefer full; smoke jobs mount/override MANIFEST_PATH.
            cand = _ROOT / "deploy/gcp_gemini_screen/manifests/full_manifest_945.json"
            path = cand
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"manifest must be a JSON list: {path}")
    return data


def lookup_entry(manifest: list[dict], task_index: int) -> dict:
    # Prefer explicit task_index field; fall back to list position.
    for e in manifest:
        if int(e["task_index"]) == task_index:
            return e
    if 0 <= task_index < len(manifest):
        e = dict(manifest[task_index])
        e.setdefault("task_index", task_index)
        return e
    raise IndexError(
        f"task_index={task_index} out of range for manifest len={len(manifest)}"
    )


def derive_harness_token(task_index: int) -> str:
    """Unique per-worker secret — not shared across Cloud Run task indexes."""
    salt = os.getenv("HARNESS_TOKEN_SALT", "gemini-census-v1")
    digest = hashlib.sha256(f"{salt}:{task_index}".encode()).hexdigest()
    return digest  # 64 hex chars; stable across retries of the same index


def derive_port(task_index: int) -> int:
    """Unique local port (still one process per container; avoids stale binds)."""
    base = int(os.getenv("WORKER_BASE_PORT", "8100"))
    return base + (task_index % 5000)


def _port_open(port: int, token: str) -> bool:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/_harness/world",
            headers={"X-Harness-Token": token},
        )
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def wait_health(port: int, token: str, timeout_s: int = 60) -> bool:
    for _ in range(timeout_s):
        if _port_open(port, token):
            return True
        time.sleep(1)
    return False


def start_server(port: int, token: str) -> subprocess.Popen:
    env = {
        **os.environ,
        HARNESS_TOKEN_ENV: token,
        "AGENT_EVAL_MODE": "1",
    }
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "server.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=str(_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if not wait_health(port, token, 60):
        err = ""
        try:
            if proc.stderr:
                err = proc.stderr.read().decode("utf-8", errors="replace")[-2000:]
        except Exception:
            pass
        proc.kill()
        raise RuntimeError(f"server on :{port} failed to come up: {err}")
    _log(f"server up on :{port} (pid {proc.pid})")
    return proc


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def classify_traj(task_id: str, traj: dict) -> str:
    """Mirror eval.cascade.classify for a single in-memory trajectory."""
    from eval.cascade import forbidden_milestones

    forb = forbidden_milestones(task_id)
    vr = traj.get("verifier_result") or {}
    fired = {
        m["name"]
        for m in (vr.get("all_milestones") or [])
        if m.get("fired_at_step", -1) >= 0
    }
    if traj.get("invalid_reason"):
        return "invalid"
    if vr.get("success"):
        return "success"
    if forb and (forb & fired):
        return "break"
    if forb:
        return "incomplete"
    return "unclassified"


def traj_to_dict(traj) -> dict:
    if isinstance(traj, dict):
        return traj
    if hasattr(traj, "to_json"):
        return traj.to_json()
    raw = getattr(traj, "__dict__", {})
    out = {}
    for k, v in raw.items():
        try:
            json.dumps(v)
            out[k] = v
        except TypeError:
            out[k] = str(v)
    return out


def sum_tokens(traj: dict) -> tuple[int, int]:
    tin = tout = 0
    for s in traj.get("steps") or []:
        tin += int(s.get("tokens_in") or 0)
        tout += int(s.get("tokens_out") or 0)
    return tin, tout


def estimate_cost_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * RATE_IN_PER_M + tokens_out * RATE_OUT_PER_M) / 1e6


def write_result(result: dict, task_index: int) -> str:
    """Write to GCS or local fallback. Returns destination URI/path."""
    bucket = (os.getenv("GCS_BUCKET") or "").strip()
    local_dir = os.getenv("LOCAL_RESULTS_DIR", "").strip()
    payload = json.dumps(result, indent=2) + "\n"

    if bucket and not os.getenv("GEMINI_MOCK_SKIP_GCS"):
        # Allow bucket with or without gs:// prefix.
        bucket = bucket.removeprefix("gs://").split("/", 1)[0]
        blob_path = f"results/{task_index}.json"
        try:
            from google.cloud import storage  # type: ignore

            client = storage.Client()
            b = client.bucket(bucket)
            blob = b.blob(blob_path)
            blob.upload_from_string(payload, content_type="application/json")
            uri = f"gs://{bucket}/{blob_path}"
            _log(f"wrote {uri}")
            return uri
        except Exception as e:
            _log(f"GCS write failed ({e}); falling back to local")

    out_dir = Path(local_dir) if local_dir else (_ROOT / "deploy/gcp_gemini_screen/local_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{task_index}.json"
    path.write_text(payload, encoding="utf-8")
    _log(f"wrote {path}")
    return str(path)


async def run_episode(task_id: str, seed: int, server_url: str, model: str,
                      traj_dir: Path, screens_dir: Path):
    from eval.run import _run_one

    traj_dir.mkdir(parents=True, exist_ok=True)
    screens_dir.mkdir(parents=True, exist_ok=True)
    return await _run_one(
        agent_kind="gemini",
        task_id=task_id,
        seed=seed,
        server_url=server_url,
        headless=True,
        record_video=False,
        out_traj_dir=traj_dir,
        out_screens_dir=screens_dir,
        llm_model=model,
        ui="normal",
        use_llm_judge=False,
    )


def mock_traj(task_id: str, seed: int, model: str) -> dict:
    """Dry-run trajectory — no Gemini API call."""
    return {
        "episode_id": f"mock-{seed}",
        "task_id": task_id,
        "seed": seed,
        "agent_name": f"gemini[{model}]",
        "started_at": time.time(),
        "finished_at": time.time(),
        "steps": [],
        "error": None,
        "invalid_reason": None,
        "verifier_result": {
            "success": False,
            "score": 0.0,
            "all_milestones": [],
        },
        "mock": True,
    }


def build_result(
    *,
    task_index: int,
    task_id: str,
    seed: int,
    model: str,
    traj: dict,
    wall_s: float,
    error: str | None,
    started_at: str,
    finished_at: str,
) -> dict:
    outcome = classify_traj(task_id, traj) if traj else "invalid"
    tin, tout = sum_tokens(traj or {})
    vr = (traj or {}).get("verifier_result") or {}
    milestones = [
        {
            "name": m.get("name"),
            "required": m.get("required"),
            "forbidden": m.get("forbidden"),
            "fired_at_step": m.get("fired_at_step"),
        }
        for m in (vr.get("all_milestones") or [])
    ]
    return {
        "task_index": task_index,
        "task_id": task_id,
        "seed": seed,
        "model": model,
        "agent": "gemini",
        "outcome": outcome,  # success | break | incomplete | invalid | unclassified
        "success": bool(vr.get("success")),
        "score": float(vr.get("score") or 0.0),
        "milestones": milestones,
        "n_steps": len((traj or {}).get("steps") or []),
        "tokens_in": tin,
        "tokens_out": tout,
        "cost_usd_est": round(estimate_cost_usd(tin, tout), 6),
        "rate_in_per_mtok": RATE_IN_PER_M,
        "rate_out_per_mtok": RATE_OUT_PER_M,
        "error": error or (traj or {}).get("error"),
        "invalid_reason": (traj or {}).get("invalid_reason"),
        "wall_s": round(wall_s, 3),
        "started_at": started_at,
        "finished_at": finished_at,
        "mock": bool((traj or {}).get("mock")),
    }


def main() -> int:
    task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", os.environ.get("TASK_INDEX", "0")))
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    mock = os.getenv("GEMINI_MOCK", "").strip() in ("1", "true", "TRUE", "yes")

    started_at = _utc_now()
    t0 = time.time()
    manifest = load_manifest()
    entry = lookup_entry(manifest, task_index)
    task_id = entry["task_id"]
    seed = int(entry["seed"])
    _log(f"index={task_index} task={task_id} seed={seed} model={model} mock={mock}")

    token = derive_harness_token(task_index)
    os.environ[HARNESS_TOKEN_ENV] = token
    # ensure_harness_token will keep the one we set
    ensure_harness_token()
    port = derive_port(task_index)
    server_url = f"http://127.0.0.1:{port}"

    proc = None
    traj_dict: dict = {}
    err: str | None = None
    try:
        proc = start_server(port, token)
        if mock:
            # Still prove server+token isolation; skip live Gemini.
            _log("GEMINI_MOCK=1 — skipping live episode")
            traj_dict = mock_traj(task_id, seed, model)
        else:
            import asyncio

            traj_dir = Path(os.getenv(
                "TRAJ_DIR", f"/tmp/gemini_census/{task_index}/traj"
            ))
            screens_dir = Path(os.getenv(
                "SCREENS_DIR", f"/tmp/gemini_census/{task_index}/screens"
            ))
            # Bound context for Gemini (1M window; keep generous vs Qwen).
            os.environ.setdefault("AGENT_MAX_STEPS", "120")
            os.environ.setdefault("LLM_CONTEXT_BUDGET", "900000")
            os.environ["AGENT_EVAL_MODE"] = "1"
            traj = asyncio.run(
                run_episode(task_id, seed, server_url, model, traj_dir, screens_dir)
            )
            traj_dict = traj_to_dict(traj)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        _log(err)
        traceback.print_exc()
        traj_dict = traj_dict or {
            "task_id": task_id,
            "seed": seed,
            "steps": [],
            "error": err,
            "invalid_reason": "infra_error",
            "verifier_result": {},
        }
    finally:
        stop_server(proc)

    finished_at = _utc_now()
    wall_s = time.time() - t0
    result = build_result(
        task_index=task_index,
        task_id=task_id,
        seed=seed,
        model=model,
        traj=traj_dict,
        wall_s=wall_s,
        error=err,
        started_at=started_at,
        finished_at=finished_at,
    )
    write_result(result, task_index)
    _log(f"done outcome={result['outcome']} wall_s={result['wall_s']} "
         f"cost_est=${result['cost_usd_est']}")
    # Non-zero only on hard worker failure before a result was written —
    # Cloud Run can retry; idempotent overwrite of the same GCS object is OK.
    return 0 if result.get("outcome") else 1


if __name__ == "__main__":
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main())
