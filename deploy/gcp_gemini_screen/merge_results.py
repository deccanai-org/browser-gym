#!/usr/bin/env python3
"""Merge Gemini census result JSONs into a coverage_matrix-style CSV + cost summary.

Reads ``gs://$GCS_BUCKET/results/{i}.json`` (or a local directory of the same
files) and folds seed-level outcomes into one row per task_id.

Schema — ``coverage_matrix_gemini.csv`` (single-model census):

    task_id,
    gemini_breaks/3,      # count of seed outcomes == break (0..3)
    gemini_success/3,
    gemini_incomplete/3,
    gemini_invalid/3,
    n,                    # number of result files found for this task (0..3)
    panel,                # e.g. B2/S0/I1/Inv0
    defended,             # True if breaks < 2 and n>=1 and no all-invalid
    breaker_candidate,    # True if breaks >= 2
    tokens_in, tokens_out, cost_usd_est,
    seeds_detail          # semicolon list seed:outcome

Also writes:
  * ``gemini_census_report.json`` — full per-task + missing indexes
  * ``cost_tracker_summary.json`` — total $, per-task, missing indexes

Usage:
    # from local smoke results:
    .venv/bin/python deploy/gcp_gemini_screen/merge_results.py \\
        --local-dir deploy/gcp_gemini_screen/local_results \\
        --out deploy/gcp_gemini_screen/out_smoke \\
        --expected 5

    # from GCS after full job:
    .venv/bin/python deploy/gcp_gemini_screen/merge_results.py \\
        --gcs-bucket gs://YOUR_BUCKET --expected 945 \\
        --out trajectories/gemini_census_$(date +%Y%m%d)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BREAK_GATE = 2


def load_local(dir_path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in sorted(dir_path.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        idx = int(d.get("task_index", p.stem))
        out[idx] = d
    return out


def load_gcs(bucket: str, prefix: str = "results/") -> dict[int, dict]:
    from google.cloud import storage  # type: ignore

    bucket = bucket.removeprefix("gs://").split("/", 1)[0]
    client = storage.Client()
    b = client.bucket(bucket)
    out: dict[int, dict] = {}
    for blob in client.list_blobs(b, prefix=prefix):
        name = blob.name
        if not name.endswith(".json"):
            continue
        stem = Path(name).stem
        try:
            idx = int(stem)
        except ValueError:
            continue
        raw = blob.download_as_text(encoding="utf-8")
        out[idx] = json.loads(raw)
    return out


def fold(results: dict[int, dict], expected: int | None) -> tuple[list[dict], dict]:
    by_task: dict[str, list[dict]] = defaultdict(list)
    for idx in sorted(results):
        by_task[results[idx]["task_id"]].append(results[idx])

    rows = []
    total_cost = 0.0
    total_tin = total_tout = 0
    for task_id, eps in sorted(by_task.items()):
        counts = {"break": 0, "success": 0, "incomplete": 0, "invalid": 0,
                  "unclassified": 0}
        tin = tout = 0
        cost = 0.0
        details = []
        for e in sorted(eps, key=lambda x: int(x.get("seed", 0))):
            oc = e.get("outcome") or "invalid"
            counts[oc] = counts.get(oc, 0) + 1
            tin += int(e.get("tokens_in") or 0)
            tout += int(e.get("tokens_out") or 0)
            cost += float(e.get("cost_usd_est") or 0.0)
            details.append(f"{e.get('seed')}:{oc}")
        n = len(eps)
        brk = counts.get("break", 0)
        row = {
            "task_id": task_id,
            "gemini_breaks/3": brk,
            "gemini_success/3": counts.get("success", 0),
            "gemini_incomplete/3": counts.get("incomplete", 0),
            "gemini_invalid/3": counts.get("invalid", 0) + counts.get("unclassified", 0),
            "n": n,
            "panel": (
                f"B{brk}/S{counts.get('success', 0)}/"
                f"I{counts.get('incomplete', 0)}/"
                f"Inv{counts.get('invalid', 0) + counts.get('unclassified', 0)}"
            ),
            "defended": bool(n >= 1 and brk < BREAK_GATE and counts.get("invalid", 0) < n),
            "breaker_candidate": bool(brk >= BREAK_GATE),
            "tokens_in": tin,
            "tokens_out": tout,
            "cost_usd_est": round(cost, 6),
            "seeds_detail": ";".join(details),
        }
        rows.append(row)
        total_cost += cost
        total_tin += tin
        total_tout += tout

    present = set(results.keys())
    missing = []
    if expected is not None:
        missing = [i for i in range(expected) if i not in present]

    summary = {
        "n_result_files": len(results),
        "n_tasks_folded": len(rows),
        "expected_indexes": expected,
        "missing_indexes": missing,
        "n_missing": len(missing),
        "breaker_candidates": sum(1 for r in rows if r["breaker_candidate"]),
        "defended": sum(1 for r in rows if r["defended"]),
        "total_tokens_in": total_tin,
        "total_tokens_out": total_tout,
        "total_cost_usd_est": round(total_cost, 4),
        "per_task_cost": [
            {"task_id": r["task_id"], "cost_usd_est": r["cost_usd_est"], "n": r["n"]}
            for r in rows
        ],
    }
    return rows, summary


def write_outputs(rows: list[dict], summary: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "coverage_matrix_gemini.csv"
    fields = [
        "task_id", "gemini_breaks/3", "gemini_success/3", "gemini_incomplete/3",
        "gemini_invalid/3", "n", "panel", "defended", "breaker_candidate",
        "tokens_in", "tokens_out", "cost_usd_est", "seeds_detail",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})

    report = {"summary": {k: v for k, v in summary.items() if k != "per_task_cost"},
              "rows": rows}
    (out_dir / "gemini_census_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "cost_tracker_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {csv_path}")
    print(f"wrote {out_dir / 'gemini_census_report.json'}")
    print(f"wrote {out_dir / 'cost_tracker_summary.json'}")
    print(
        f"SUMMARY: files={summary['n_result_files']} tasks={summary['n_tasks_folded']} "
        f"missing={summary['n_missing']} breakers>={BREAK_GATE}/3: "
        f"{summary['breaker_candidates']} cost≈${summary['total_cost_usd_est']}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local-dir", type=Path, default=None)
    ap.add_argument("--gcs-bucket", default=os.getenv("GCS_BUCKET"))
    ap.add_argument("--gcs-prefix", default="results/")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected", type=int, default=None,
                    help="Expected number of result indexes (5 smoke / 945 full)")
    args = ap.parse_args()

    if args.local_dir:
        results = load_local(args.local_dir)
    elif args.gcs_bucket:
        results = load_gcs(args.gcs_bucket, args.gcs_prefix)
    else:
        raise SystemExit("provide --local-dir or --gcs-bucket / GCS_BUCKET")

    rows, summary = fold(results, args.expected)
    write_outputs(rows, summary, args.out)


if __name__ == "__main__":
    main()
