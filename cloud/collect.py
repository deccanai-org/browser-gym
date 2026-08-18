"""Pull the per-episode summaries and print the breaker ledger.

Reads only summary.json per episode (a few hundred bytes each), never the
trajectories, so the verdict for a 10-episode fan-out lands in a second or two.
"""
from __future__ import annotations
import argparse, json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args()
    from google.cloud import storage

    rows = []
    for b in storage.Client().list_blobs(a.bucket, prefix=f"runs/{a.run_id}/"):
        if b.name.endswith("summary.json"):
            rows.append(json.loads(b.download_as_text()))
    rows.sort(key=lambda r: r.get("task_id", ""))

    if not rows:
        print(f"no summaries under gs://{a.bucket}/runs/{a.run_id}/"); return

    w = max(len(r["task_id"]) for r in rows)
    print(f"{'task':{w}}  {'seed':4} {'score':>5} {'steps':>5}  outcome         forbidden fired")
    print("-" * (w + 62))
    for r in rows:
        print(f"{r['task_id']:{w}}  {r['seed']:<4} {str(r['score']):>5} {str(r['n_steps']):>5}  "
              f"{r['outcome']:<15} {','.join(r['forbidden_fired']) or '-'}")

    n = len(rows)
    trap = [r for r in rows if r["outcome"] == "TRAP-FIRED"]
    solved = [r for r in rows if r["outcome"] == "solved"]
    starved = [r for r in rows if r["outcome"] == "step-exhaustion"]
    print(f"\n{n} episodes: {len(trap)} trap-fired, {len(starved)} step-exhaustion, "
          f"{len(solved)} solved, {n-len(trap)-len(starved)-len(solved)} incomplete")
    if trap:
        print("\nGENUINE BREAKERS (a forbidden milestone actually fired):")
        for r in trap:
            print(f"  {r['task_id']} — {', '.join(r['forbidden_fired'])}")


if __name__ == "__main__":
    main()
