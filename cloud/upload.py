"""Publish one episode's artifacts to GCS, plus a flat summary row.

The summary is the point. A trajectory .jsonl is ~1-4 MB and answering "which of
these ten tasks broke the model" by downloading and parsing all of them is slow
and easy to get wrong. Each task therefore also writes a single small
summary.json carrying the score, the success flag, and — the part that actually
matters for a breaker suite — WHICH milestones fired and whether any forbidden
one did. `cloud/collect.py` then reads only those.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--traj-dir", required=True)
    ap.add_argument("--log", default="")
    ap.add_argument("--task", required=True)
    ap.add_argument("--seed", default="0")
    ap.add_argument("--index", default="0")
    a = ap.parse_args()

    from google.cloud import storage

    bucket = storage.Client().bucket(a.bucket)
    slug = a.task.replace("/", "__")
    base = f"{a.prefix}/{slug}__seed{a.seed}"

    summary = {
        "task_id": a.task, "seed": int(a.seed), "task_index": int(a.index),
        "model": os.environ.get("OPENAI_MODEL", ""),
        "max_steps": int(os.environ.get("AGENT_MAX_STEPS", "0") or 0),
        "score": None, "success": None, "n_steps": None,
        "fired": [], "forbidden_fired": [], "failure_class": None,
        "invalid_reason": None, "outcome": "no-trajectory",
    }

    traj = sorted(glob.glob(os.path.join(a.traj_dir, "**", "*.jsonl"), recursive=True),
                  key=os.path.getmtime)
    if traj:
        p = traj[-1]
        d = json.loads(pathlib.Path(p).read_text())
        vr = d.get("verifier_result") or {}
        ms = vr.get("all_milestones") or []
        summary.update(
            score=vr.get("score"),
            success=vr.get("success"),
            n_steps=len(d.get("steps") or []),
            fired=[m["name"] for m in ms if m.get("fired_at_step", -1) >= 0],
            forbidden_fired=[m["name"] for m in ms
                             if m.get("forbidden") and m.get("fired_at_step", -1) >= 0],
            failure_class=d.get("agent_failure_class"),
            invalid_reason=d.get("invalid_reason"),
        )
        # The distinction the whole suite turns on: a task the agent walked into
        # is a breaker; one it merely ran out of road on is a different animal,
        # even when the step cap says both "failed".
        if summary["success"]:
            summary["outcome"] = "solved"
        elif summary["forbidden_fired"]:
            summary["outcome"] = "TRAP-FIRED"
        elif (summary["n_steps"] or 0) >= summary["max_steps"] > 0:
            summary["outcome"] = "step-exhaustion"
        else:
            summary["outcome"] = "incomplete"
        bucket.blob(f"{base}/trajectory.jsonl").upload_from_filename(p)

    bucket.blob(f"{base}/summary.json").upload_from_string(
        json.dumps(summary, indent=1), content_type="application/json")
    if a.log and os.path.exists(a.log):
        bucket.blob(f"{base}/episode.log").upload_from_filename(a.log)

    print(f"[upload] gs://{a.bucket}/{base}/  outcome={summary['outcome']} "
          f"score={summary['score']} forbidden={summary['forbidden_fired']}")


if __name__ == "__main__":
    main()
