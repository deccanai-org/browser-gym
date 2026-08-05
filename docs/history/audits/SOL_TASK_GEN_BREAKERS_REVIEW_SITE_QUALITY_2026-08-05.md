# BrowserGym-Tasks review-site quality fixes — 2026-08-05

## Outcome

Deployed information-quality fixes for Sol Breakers **n10–n19** on
[`arun-thepolicy-murari/BrowserGym-Tasks`](https://github.com/arun-thepolicy-murari/BrowserGym-Tasks)
(live Pages) and mirrored the canonical fields into
`BrowserGym-Annotation-phase2` so future syncs do not regress.

## What changed

1. **True steps vs curated gallery**
   - Added per-run `true_n_steps` and task-level `mean_steps` /
     `true_n_steps_by_seed`.
   - Left curated gallery size in `n_steps` / `len(steps)` unchanged.
   - UI labels: `Curated gallery: N frames shown`, `Actual episode length: M steps`,
     plus task mean where available.
   - `enrich_sol_breakers_screens.py` now preserves `true_n_steps` on re-enrich.

2. **Fairness / Orchestrator ACCEPT**
   - Added distinct `fairness_notes` per n10–n19 (Environment + Verifiers tabs),
     sourced from `SOL_TASK_GEN_CLUSTER_TRACKER_2026-08-04.md` (Orch ACCEPT +
     trap rationale). No generic repeated sentence.

3. **Score-vs-BREAK legend**
   - Visible note on model-run and Verifiers views: score = required milestones;
     BREAK can fire independently via a forbidden milestone (score 1.0 + BREAK is possible).

4. **Stale id_scheme**
   - BrowserGym-Tasks `id_scheme.notes` already described n10–n19 correctly;
     Annotation `id_scheme.mapping`/`notes` still claimed gift-family n10–n13 —
     fixed to current mapping (`n10=food_003` … `n19=vm_008`) with explicit
     non-gift wording. Annotation README clarifies historical vs current IDs.

5. **Known limitations (documented, not built)**
   - README note: n10–n19 envs are inspectable seed JSON, not interactive
     `env_ui` launchers; curated screens are review evidence only; full
     trajectories remain outside the static Pages package.

## Authoritative step values (n10–n19)

| Display | Task | true steps (s0/s1/s2) | mean | Curated frames | Authority |
|---|---|---:|---:|---:|---|
| n10 | food_003 | 42/34/25 | 33.7 | 12/12/12 | THREE_SEED_SUMMARY (matches JSONL) |
| n11 | vm_003 | 24/46/44 | 38.0 | 12/12/12 | THREE_SEED_SUMMARY (matches JSONL) |
| n12 | inj_003 | 29/26/17 | 24.0 | 12/12/12 | THREE_SEED_SUMMARY (matches JSONL) |
| n13 | cal_food_001 | 62/45/39 | 48.7 | 12/12/12 | packaged JSONL (SUMMARY mismatched siblings / mean=62.0) |
| n14 | vm_007 | 15/19/15 | 16.3 | 12/12/12 | packaged JSONL (SUMMARY missing) |
| n15 | food_006 | 20/22/21 | 21.0 | 12/12/12 | packaged JSONL (SUMMARY missing) |
| n16 | inj_004 | 17/14/15 | 15.3 | 12/12/12 | packaged JSONL (SUMMARY missing) |
| n17 | inj_005 | 7/7/27 | 13.7 | 7/7/12 | packaged JSONL (SUMMARY missing) |
| n18 | cal_food_002 | 16/16/16 | 16.0 | 12/12/12 | packaged JSONL (SUMMARY missing) |
| n19 | vm_008 | 35/29/46 | 36.7 | 12/12/12 | packaged JSONL (SUMMARY missing) |

Caveats: tracker prose sometimes quotes earlier scale notes (e.g. vm_007 15/15/15,
vm_008 34/28/45, inj_005 7/6/27). Packaged episode JSONL lengths above are the
site source of truth for the curated run IDs.

## Validation

- All 10 tasks have distinct fairness notes containing Orchestrator ACCEPT.
- Curated screenshot counts unchanged from pre-patch galleries.
- Local `index.html` contains the new labels/legend; HTTP smoke on
  `python3 -m http.server` returned 200.

## Deploy

**BrowserGym-Tasks**
- Feature commit: `7cb8f1f` on `sol-breakers-bridged`
- Deploy merge: `main` @ `f876dc0`
- Pages Action: [31036979555](https://github.com/arun-thepolicy-murari/BrowserGym-Tasks/actions/runs/31036979555) succeeded (`workflow_dispatch`; bare `gh` without `-R` resolves this checkout’s `upstream` Annotation remote)
- Live URL: https://arun-thepolicy-murari.github.io/BrowserGym-Tasks/
- Live check: HTTP 200; page contains `Curated gallery:`, `Actual episode length:`, `Score vs BREAK:`, `Fairness / Orchestrator ACCEPT`, `true_n_steps`

**BrowserGym-Annotation-phase2** (canonical sync source)
- Local commit: `356f1a9` on `main` — patched `sol_breakers/tasks.json` id_scheme + true steps + fairness notes, UI, enrich/merge/package scripts, and curated screens for the packaged pool.
- Push to `amit-deccan/BrowserGym-Annotation-phase2` returned **403** for the current GitHub identity (`arun-thepolicy-murari`); package is committed locally for sync. Someone with write access should push when available.
