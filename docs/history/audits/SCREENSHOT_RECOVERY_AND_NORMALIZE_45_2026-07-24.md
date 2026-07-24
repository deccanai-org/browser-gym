# Screenshot recovery + 45-task visual normalization — 2026-07-24

Execution of **Option A** from [FOUR_STREAM_REMEDIATION_2026-07-24.md](./FOUR_STREAM_REMEDIATION_2026-07-24.md)
§1c, plus normalization of visual evidence for all 45 missing-screenshot
tasks into one folder scheme.

| Constraint | Status |
|---|---|
| `trajectories/sellable_breakers_v2.csv` | **Untouched.** SHA256 before = after = `c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30` (matches the four-stream audit baseline) |
| New BREAK/SUCCESS/INCOMPLETE dispositions | **None written.** Historical verdicts remain ground truth everywhere; replay verifier output is stored only as an explicitly non-authoritative QA field (see below) |
| Source trajectory files | **Not modified** — replay reads them, never writes them |
| Cost | **$0 API** (mechanical replay + live captures, no model calls) vs the ~$15–40 Option A estimate. Not over budget |
| Python | `.venv/bin/python` |
| Infra | This week's `eval/run.py` seed_initial/seed_final pairing + `harness/runner.py` search-dropdown wait were reused verbatim (replay drives `BrowserCtx` directly) |

---

## Part 1 — 16 tasks: model filmstrips recovered by mechanical replay

Tasks: M77, M78, M79, M84, M87, M90, M91, M93, M98, M99, M100, M101, M102,
M104, M207, M210.

**Method (preferred path — no live model re-run was needed):** every
seed×model cell with a recorded historical disposition has a trajectory
JSONL whose steps record `action_kind` + fully resolved `action_args`
(mark actions carry the resolved pixel `coord`). A new script,
`scripts/replay_visual_recovery.py`, resets the gym for the same
(task, seed, ui_variant), pre-navigates to `start_path`, then re-executes
the recorded action sequence through the same `harness/runner.py`
`BrowserCtx` used by live runs — ticking the async clock before each turn
exactly like the agent loops do. Screenshots are written to the episode's
**original** recorded directory (Windows-style path normalized), so all
historical `screenshot_path` references now resolve.

Per replayed episode dir:

- `step_000.png … step_NNN.png` — the filmstrip, index-aligned to the
  recorded steps (a dispatch failure still records a stub frame so indices
  never shift);
- `seed_initial.png/.json` and `seed_final.png/.json` — this week's pairing
  semantics;
- `REPLAY_RECOVERY.json` — provenance marker: source trajectory, the
  **historical verifier result (ground truth)**, the replay verifier output
  under `replay_verifier_result_non_authoritative` (QA only, discarded as a
  disposition), and a per-step URL-trace fidelity report.

### Coverage and fidelity

**179 / 179** model episodes replayed OK (100%); 2,406 recorded steps
re-captured. Every one of the 16 tasks now has filmstrips for **all three
historical model tiers × all three seeds** (gpt-5.1, gpt-5.5,
claude-sonnet-4-6; several cells have 2 historical episodes, both replayed).

Fidelity = fraction of steps whose post-action URL path matches the
recorded one:

| task | episodes | steps | mean match | min | perfect episodes |
|---|---|---|---|---|---|
| M77 | 9 | 39 | 1.000 | 1.000 | 9/9 |
| M78 | 9 | 72 | 1.000 | 1.000 | 9/9 |
| M79 | 9 | 107 | 0.886 | 0.700 | 4/9 |
| M84 | 15 | 60 | 1.000 | 1.000 | 15/15 |
| M87 | 15 | 79 | 0.929 | 0.714 | 11/15 |
| M90 | 15 | 73 | 0.993 | 0.889 | 14/15 |
| M91 | 15 | 78 | 1.000 | 1.000 | 15/15 |
| M93 | 9 | 133 | 1.000 | 1.000 | 9/9 |
| M98 | 9 | 90 | 1.000 | 1.000 | 9/9 |
| M99 | 9 | 38 | 1.000 | 1.000 | 9/9 |
| **M100** | 9 | 353 | **0.585** | **0.190** | 0/9 |
| M101 | 9 | 66 | 0.984 | 0.857 | 8/9 |
| M102 | 9 | 141 | 0.880 | 0.625 | 5/9 |
| M104 | 9 | 57 | 1.000 | 1.000 | 9/9 |
| M207 | 17 | 675 | 0.909 | 0.385 | 12/17 |
| M210 | 12 | 345 | 1.000 | 1.000 | 12/12 |
| **Total** | **179** | **2,406** | **0.951** | — | **150/179** |

- 150/179 episodes are byte-for-byte faithful to the recorded URL trace;
  152 are ≥ 0.9.
- **Low-fidelity flag (coordinate drift):** M100 (all 9), plus single long
  episodes of M207 (`esc_gpt55` seed0 0.385, `esc2_gpt55` seed1 0.675) and a
  few M79/M87/M102 episodes. Cause: long cart-editing flows where an early
  quantity/row change shifts layout, so a later recorded coordinate lands on
  a different element and the replay path diverges from there. Frames up to
  the divergence step are faithful; frames after it show a *plausible but
  different* continuation. Each episode's `REPLAY_RECOVERY.json` marks the
  exact first divergent step. If pixel-perfect filmstrips for M100 are ever
  required, that is the one task where a live model re-run (Option C-style,
  ~$3–6) would be the only alternative — **not launched** under this pass's
  $0 preference.
- **QA-only verdict agreement (all discarded):** 176/179 replay verifier
  outputs agree with the historical verdict. The 3 disagreements (historical
  SUCCESS → replay non-success; two at URL match 1.0) are
  `cset_g55_backfill/M90…__0__fddcf86e`, `cascade_b7/gpt-5.5/M90…__2__45037c73`,
  `cascade_newpatterns2/gpt-5.1/M210…__2__e2d642cd`. **Disposition triage
  (2026-07-24 follow-up):** M90 seed0 gpt-5.5 is quiet cart-toggle / last-step
  URL drift (match 0.889) → close, no action. M90 seed2 gpt-5.5 and M210
  seed2 gpt-5.1 are URL-perfect (1.0) with flipped required/forbidden
  milestones under identical path traces — genuine replay-pacing /
  env-scoring discrepancy; both tasks are on the sellable 85 ledger and
  warrant mismatch-style investigation if scores are re-audited. **No
  disposition was changed** — historical verdict remains ground truth.

### Cells without replayable actions

10 quarantined zero-step trajectories exist under
`trajectories/overnight_push/xmodel/_quarantine_pre_resume_20260713_152336/`
(claude-opus-4-8 and gpt-5.6-sol, seed 0, for M77/M78/M79/M84/M87). All are
`LLMCallError: … APIConnectionError` infra failures with **no recorded
actions and no meaningful disposition** (score 0.0, already quarantined).
Nothing to replay; documented here as the only non-replayable cells. No
live model re-run was needed for any cell with a real historical
disposition.

### Cost

| Item | Actual |
|---|---|
| Replay (179 episodes, 2,406 steps, 3 parallel workers ≈ 22 min wall) | **$0 API** |
| Live seed-initial captures (45 tasks × 3 seeds) | **$0 API** |
| Live model re-runs | **none launched** |
| vs Option A estimate ~$15–40 | **under** (replay made re-runs unnecessary) |

---

## Part 2 — All 45 tasks normalized under `artifacts/task_visuals/`

### Where the 29 already-recoverable tasks lived (confirmed)

| Source | Content |
|---|---|
| `screenshots/oracle/` | Oracle filmstrips, 3 seeds, **all 45 tasks** |
| `screenshots/pixel/`, `screenshots/openai_pixel/` | Historical model filmstrips for the 29 (sonnet / gpt tiers; a few opus + gpt-5.6-sol episodes) |
| `screenshots/harvest/` | Cascade-run filmstrips (now also holds most of the 16 replayed tasks' episodes) |
| `seed_snapshots/{slug}/` | Factory world JSON (`seed{0-2}_initial/final/replay.json`) — no PNGs |
| `docs/history/audits/artifacts/static_seeds_2026-07-24/` | 45 static BrowerGym GitHub-Pages start-page PNGs |
| `ecommerce-browser-gym-sonnet-completions` twin | Checked — contains **no** episodes for these 45 tasks (M37/M252/M271/M346 only); not used |

### Normalized layout (one scheme for all 45)

```
artifacts/task_visuals/{Mxx__slug}/
  SOURCE.md                        # per-task provenance table (all rows below)
  seed_state/
    seed{N}_initial.png            # live gym capture 2026-07-24 (post infra fix)
    seed{N}_initial.live.json      # world dump paired with that PNG
    seed{N}_initial.json           # factory world JSON (seed_snapshots)
    seed{N}_final.json             # factory world JSON (seed_snapshots)
    seed{N}_final_oracle.png       # last frame of longest oracle filmstrip
                                   # (state after CORRECT completion)
    static_start.png               # static BrowerGym capture
  oracle/seed{N}__{hash}/step_XXX.png
  models/{model}/seed{N}__{hash}/  # model filmstrips (historical + recovered)
    step_XXX.png
    seed_initial.png/.json  seed_final.png/.json   # replayed episodes
    REPLAY_RECOVERY.json                           # replayed episodes
```

Built by `scripts/normalize_task_visuals.py`. Files are **hardlinks** into
the historical `screenshots/` buckets — downstream can consume one tree
without caring which bucket an episode came from, originals stay valid, and
no bytes are duplicated. Model attribution comes from the trajectory index
(episode hash → `agent_name`), not from the bucket name.

### Verification — 45 / 45 present and consistent

- 45 task dirs; **453 filmstrip episode dirs** linked
  (oracle + models; 4 legacy PNG dirs had no matching trajectory and sit
  under `models/_unattributed/` with their bucket name preserved).
- Every task has: 3× `seed{N}_initial.png` (135 live captures total),
  factory initial/final JSON, `static_start.png`, ≥1 oracle filmstrip,
  ≥1 model filmstrip, 3× `seed{N}_final_oracle.png`, and a `SOURCE.md`.
  **Zero tasks with gaps.**
- Models present across the tree: gpt-5.1, gpt-5.5, claude-sonnet-4-6,
  claude-opus-4-8, gpt-5.6-sol (+ `_unattributed`).

### Per-task completion (all 45)

Complete = normalized dir has seed-state pairing, oracle filmstrip(s), and
model filmstrip(s).

| Tasks | Status |
|---|---|
| M40 M41 M47 M51 M57 M68 M72 M73 M74 M76 M81 M82 M83 M86 M92 M94 M95 M96 M97 M148 M164 M200 M212 M214 M217 M219 M220 M224 M227 (the 29) | **Complete** — historical PNGs normalized |
| M77 M78 M79 M84 M87 M90 M91 M93 M98 M99 M100 M101 M102 M104 M207 M210 (the 16) | **Complete** — model filmstrips replay-recovered this pass (M100 flagged partial-fidelity, see Part 1) |

### New scripts (this pass)

| Script | Purpose |
|---|---|
| `scripts/replay_visual_recovery.py` | Mechanical action replay → filmstrip + seed pairing + `REPLAY_RECOVERY.json`; idempotent (skips dirs already marked) |
| `scripts/capture_seed_initials.py` | Live seed-initial PNG+JSON for the 45×3 cells |
| `scripts/normalize_task_visuals.py` | Builds/refreshes `artifacts/task_visuals/` (hardlinks + SOURCE.md); safe to re-run |

Replay worker logs: `logs/replay_recovery_{8071,8072,8073}.jsonl` (+
`logs/replay_smoke.jsonl`).

---

## Final summary

- **Part 1:** 179/179 historical model episodes for the 16 tasks now have
  on-disk filmstrips at their original recorded paths, produced by $0
  mechanical replay; no new dispositions; mean URL-trace fidelity 0.951
  (M100 flagged as the one materially divergent task).
- **Part 2:** all 45 tasks live under one documented scheme in
  `artifacts/task_visuals/` with per-task SOURCE.md provenance and
  seed_initial/final pairing.
- **Total cost: $0 API** (estimate was $15–40 — under, not over).
- **Sellable ledger untouched:** SHA256
  `c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30`
  verified at start and end of this pass.
---

## Follow-up — consolidated into `screenshots/` (2026-07-24)

Canonical home is now `screenshots/{Mxx__slug}/` (same layout). `artifacts/task_visuals/` is deprecated with per-task symlinks. See [SCREENSHOT_CONSOLIDATE_45_TO_SCREENSHOTS_2026-07-24.md](./SCREENSHOT_CONSOLIDATE_45_TO_SCREENSHOTS_2026-07-24.md).
