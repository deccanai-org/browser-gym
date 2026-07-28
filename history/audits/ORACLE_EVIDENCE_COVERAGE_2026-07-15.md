# Active Sellable Oracle Evidence Audit — 2026-07-15

## Verdict

**CLOSED: 85/85 active sellables have retained UI-only 1.00×3 evidence,
with zero blockers.**

The authoritative task set was read directly from
`trajectories/sellable_breakers_v2.csv`. For every exact task ID, the audit
requires successful score-1.00 oracle trajectories for seeds 0, 1, and 2.
It validates the trajectory task ID, seed, agent identity, verifier success,
score, and absence of privileged-control markers in the runtime artifact.

UI-only status is not inferred from trajectory existence. The registered
solver's decision path is scanned transitively across every repository-local
function it calls. The scan rejects `ctx.http`, `/_harness/world`,
`/_harness/state`, and direct server module/state dependencies. Runner-owned
reset, snapshot, and verifier calls are outside oracle decision logic and are
not treated as violations.

## Evidence

- Machine-readable inventory:
  `trajectories/prepublication_oracles_20260715/coverage.json`
- Reproducible scanner: `eval/audit_oracle_coverage.py`
- Fresh gap-fill scorecard:
  `trajectories/prepublication_oracles_20260715/fresh/_scorecard.json`
- Fresh gap-fill tasks: M271 and M312, each 1.00×3
- M37 replacement evidence:
  `trajectories/prepublication_m37_20260715/oracle/_scorecard.json`

The coverage file records, per task, exact evidence paths and seed scores,
all transitively scanned oracle functions, static scan hits, UI-only status,
and blockers. Final summary: active=85, complete=85, blocked/incomplete=0.
