#!/usr/bin/env python3
"""Merge per-episode GCS (or local) filtration result JSON into one CSV/table."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


FIELDS = [
    "index",
    "task_id",
    "seed",
    "model",
    "agent",
    "success",
    "disposition",
    "valid",
    "credit_death",
    "failure_class",
    "score",
    "steps",
    "hub_source",
    "error",
    "gcs_uri",
    "wall_s",
    "tokens_in",
    "tokens_out",
    "luna_usd",
]


def _attach_log_scan(row: dict, log_text: str) -> dict:
    """Backfill the failure classification from the episode's raw log.

    Episodes produced before the worker started recording ``failure_class`` have
    an empty ``error`` even when the run died on Anthropic credits, so the log
    text is the only surviving evidence. Rows that already carry the field are
    left alone.
    """
    from harness.api_failure_class import scan_log_text

    if row.get("failure_class") is not None or row.get("credit_death") is not None:
        return row
    scan = scan_log_text(log_text)
    row["failure_class"] = scan["failure_class"]
    row["credit_death"] = scan["credit_death"]
    row["valid"] = not scan["credit_death"]
    if scan["credit_death"] and not row.get("error"):
        row["error"] = f"credit_exhausted (from log): {scan['excerpt']}"[:500]
    return row


def load_local(path: Path) -> list[dict]:
    rows: list[dict] = []
    if path.is_file():
        rows.append(json.loads(path.read_text()))
        return rows
    for p in sorted(path.glob("**/*.json")):
        if p.name.startswith("_") or p.name in ("SMOKE_AGGREGATE.json", "SMOKE_DRIVER_SUMMARY.json"):
            continue
        try:
            row = json.loads(p.read_text())
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr)
            continue
        log_p = p.with_suffix(".log")
        rows.append(_attach_log_scan(
            row, log_p.read_text(errors="ignore") if log_p.is_file() else ""))
    return rows


def load_gcs(bucket: str, prefix: str) -> list[dict]:
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    b = client.bucket(bucket)
    rows: list[dict] = []
    for blob in client.list_blobs(b, prefix=prefix):
        if not blob.name.endswith(".json"):
            continue
        if blob.name.endswith("/") or "/_merged" in blob.name:
            continue
        try:
            row = json.loads(blob.download_as_text())
        except Exception as e:
            print(f"skip gs://{bucket}/{blob.name}: {e}", file=sys.stderr)
            continue
        log_text = ""
        log_blob = b.blob(blob.name[: -len(".json")] + ".log")
        try:
            if log_blob.exists():
                log_text = log_blob.download_as_text()
        except Exception as e:
            print(f"log unavailable for {blob.name}: {e}", file=sys.stderr)
        rows.append(_attach_log_scan(row, log_text))
    return rows


def normalize(row: dict) -> dict:
    success = row.get("success")
    if row.get("disposition") in ("BREAK", "HOLD"):
        disposition = row["disposition"]
    elif success is True:
        disposition = "HOLD"
    elif success is False:
        disposition = "BREAK"
    else:
        disposition = row.get("disposition") or "ERROR"
    credit_death = bool(row.get("credit_death"))
    return {
        "index": row.get("index"),
        "task_id": row.get("task_id"),
        "seed": row.get("seed"),
        "model": row.get("model"),
        "agent": row.get("agent"),
        "success": success,
        "disposition": disposition,
        "valid": (not credit_death) if row.get("valid") is None
        else bool(row.get("valid")),
        "credit_death": credit_death,
        "failure_class": row.get("failure_class") or "",
        "score": row.get("score"),
        "steps": row.get("steps"),
        "hub_source": row.get("hub_source"),
        "error": row.get("error") or "",
        "gcs_uri": row.get("gcs_uri") or "",
        "wall_s": row.get("wall_s"),
        "tokens_in": row.get("tokens_in"),
        "tokens_out": row.get("tokens_out"),
        "luna_usd": row.get("luna_usd"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local", type=Path, help="Local dir/file of result JSON")
    ap.add_argument("--gcs-bucket")
    ap.add_argument("--gcs-prefix", default="filtration/")
    ap.add_argument("--out-csv", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    rows: list[dict] = []
    if args.local:
        rows.extend(load_local(args.local))
    if args.gcs_bucket:
        rows.extend(load_gcs(args.gcs_bucket, args.gcs_prefix))
    if not rows:
        raise SystemExit("no rows loaded")

    norm = [normalize(r) for r in rows]
    norm.sort(key=lambda r: (r.get("index") is None, r.get("index") or 0, str(r.get("task_id")), r.get("seed") or 0))

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(norm)

    if args.out_json:
        args.out_json.write_text(json.dumps(norm, indent=2) + "\n")

    n = len(norm)
    valid = [r for r in norm if r["valid"]]
    dead = [r for r in norm if r["credit_death"]]
    breaks = sum(1 for r in valid if r["disposition"] == "BREAK")
    holds = sum(1 for r in valid if r["disposition"] == "HOLD")
    errors = sum(1 for r in valid if r["disposition"] == "ERROR")
    hub_ok = sum(1 for r in norm if r.get("hub_source") == "explicit-env")
    print(f"merged {n} rows → {args.out_csv}")
    # BREAK/HOLD are reported over VALID episodes only: a credit death is not a
    # model decision, and counting it inflates whichever side it lands on.
    print(f"  valid={len(valid)}/{n} credit_death={len(dead)}")
    print(f"  BREAK={breaks} HOLD={holds} ERROR={errors} (valid only) "
          f"hub_source=explicit-env={hub_ok}/{n}")
    if dead:
        raw_breaks = sum(1 for r in dead if r["disposition"] == "BREAK")
        raw_holds = sum(1 for r in dead if r["disposition"] == "HOLD")
        print(f"  !! {len(dead)} credit-dead episodes excluded "
              f"(would have counted as {raw_breaks} BREAK / {raw_holds} HOLD)")


if __name__ == "__main__":
    main()
