# Repository cleanup summary — 2026-07-15

Cleanup was executed against commit `6f6a1b5` on `feat/multi-app`. No cleanup change was staged, committed, or pushed. The full per-file disposition and git-blob hashes are in [`REPO_CLEANUP_MANIFEST_2026-07-15.csv`](REPO_CLEANUP_MANIFEST_2026-07-15.csv).

### Post-cleanup living-document correction

During final external validation on 2026-07-15, the moved
`docs/history/snapshots/ALL_TASK_BRIEFS.md` export was found to contain 294
historical M-task headings rather than the complete live registry. It was
regenerated from current `server.tasks.TASKS` and `BRIEFS` with 312 exact,
non-empty, unique task entries. This is an intentional post-cleanup export
correction, not an archival move: the manifest retains the original source
hash `89fa753ea74b6ed15d559d44cf6fcee95202cb1d`, marks the action
`MOVE_THEN_POST_CLEANUP_UPDATE`, and records the current destination hash
`c3f2acda68b10150f51c48b3e93bf3af5993916f`. The byte-identical move claims
below describe the cleanup operation before this explicitly recorded
correction.

The same validation made two additional, narrowly scoped post-cleanup
corrections and records their current hashes in the manifest:

- `PROJECT_INFO.md` was updated only to replace the stale brief-export wording;
  current hash `bdf1b500baac162812a9b40ce448703bae7faa9e`.
- `agents/oracle_agent.py` replaced M362's hidden harness-state read with the
  visible Food order confirmation path; current hash
  `f9e869f14148e105b519138852edfe9859323a9f`.
- The Sol/Opus forensic JSON, report, and depth report corrected M39's stale
  Sol-only attribution to the raw flagship result `sol 3/3; opus 3/3`.
  Their current hashes are recorded in the manifest as explicit
  `MOVE_THEN_POST_CLEANUP_ATTRIBUTION_FIX` actions.

### Post-cleanup M56 release treatment

The later definitive M56 forensic disposition intentionally changed active
release membership without changing or deleting historical evidence. M56 was
removed from `trajectories/sellable_breakers_v2.csv` and the current
default-membership split, while its historical Qwen 3/3 panel, fresh three-run
state-no-op panel, and historical 42-member checkout audit were preserved.
Living reports and machine outputs now report 85 total / 83 core sellables and
the moved audit/report destinations carry explicit
`MOVE_THEN_POST_CLEANUP_RELEASE_UPDATE` manifest actions. Their original
source hashes remain unchanged in the manifest. The new hold record is
`docs/history/audits/M56_RELEASE_HOLD_2026-07-15.md`.

## Final report identity

`PROJECT_REPORT_2026-07-14.md` does not exist in current HEAD or the completed protected-reference inventory. `PROJECT_INFO.md` exists in HEAD, identifies itself as the final reconciled project report, and is the final report for this cleanup. No report was invented or duplicated.

## Category counts

| Category | Before | After |
|---|---:|---:|
| 1. living docs | 13 | 14 |
| 2. historical record | 70 | 72 |
| 3. genuinely stale/superseded | 0 | 0 |
| 4. code/tests/assets | 144 | 144 |
| 5. trajectory/results/evidence | 5,988 | 5,988 |
| 6. local/temp/process | 31 | 0 |
| **Total non-ignored files** | **6,246** | **6,218** |

After counts include three cleanup-created documents: this summary, the CSV manifest, and `docs/history/README.md`. No substantive category-3 deletion candidate was found or removed.

## Actions

- Kept byte-identical at the same path: 6,168
- Updated living/configuration documents: 4
- Moved byte-identically into history: 43
- Deleted confirmed local/temp/process artifacts: 31
- Created cleanup/history documents: 3

### Complete move list

- `ALL_TASK_BRIEFS.md` → `docs/history/snapshots/ALL_TASK_BRIEFS.md`
- `FINAL_IMPLICIT_DESIGN_GATE_2026-07-14.md` → `docs/history/waves/final_implicit/FINAL_IMPLICIT_DESIGN_GATE_2026-07-14.md`
- `HANDOFF_TO_CURSOR.md` → `docs/history/handoffs/HANDOFF_TO_CURSOR.md`
- `HANDOFF_TO_CURSOR_v2.md` → `docs/history/handoffs/HANDOFF_TO_CURSOR_v2.md`
- `PHASE5_CONSOLIDATION_PLAN.md` → `docs/history/plans/PHASE5_CONSOLIDATION_PLAN.md`
- `PHASE_A_AUDIT.md` → `docs/history/audits/PHASE_A_AUDIT.md`
- `PHASE_C_BUILD.md` → `docs/history/waves/phase_c/PHASE_C_BUILD.md`
- `PHASE_C_RESULTS.md` → `docs/history/waves/phase_c/PHASE_C_RESULTS.md`
- `PHASE_C_WAVE2_TRIAGE.md` → `docs/history/waves/phase_c/PHASE_C_WAVE2_TRIAGE.md`
- `STRUCTURAL_IMPLICIT_WAVE_BUILD_STATUS_2026-07-14.md` → `docs/history/waves/2026-07-14/STRUCTURAL_IMPLICIT_WAVE_BUILD_STATUS_2026-07-14.md`
- `WAVE_PHASE_D_2026-07-14.md` → `docs/history/waves/2026-07-14/WAVE_PHASE_D_2026-07-14.md`
- `WAVE_STRUCTURAL_IMPLICIT_PROPOSAL_2026-07-14.md` → `docs/history/waves/2026-07-14/WAVE_STRUCTURAL_IMPLICIT_PROPOSAL_2026-07-14.md`
- `WAVE_THIN_CORE_2026-07-14.md` → `docs/history/waves/2026-07-14/WAVE_THIN_CORE_2026-07-14.md`
- `WAVE_THIN_VEIN_2026-07-13.md` → `docs/history/waves/2026-07-13/WAVE_THIN_VEIN_2026-07-13.md`
- `trajectories/CHECKOUT_AXIS_AUDIT.md` → `docs/history/audits/CHECKOUT_AXIS_AUDIT.md`
- `trajectories/PENDING_MERGE_VALIDITY_AUDIT.md` → `docs/history/audits/PENDING_MERGE_VALIDITY_AUDIT.md`
- `trajectories/SOL_OPUS_SELLABLE_VENN.md` → `docs/history/forensics/sol_opus/SOL_OPUS_SELLABLE_VENN.md`
- `trajectories/TAXONOMY_MIGRATION_CHECKOUT_2026-07-14.md` → `docs/history/audits/TAXONOMY_MIGRATION_CHECKOUT_2026-07-14.md`
- `trajectories/overnight_push/SOL_OPUS_FORENSIC.json` → `docs/history/forensics/sol_opus/SOL_OPUS_FORENSIC.json`
- `trajectories/overnight_push/SOL_OPUS_FORENSIC.md` → `docs/history/forensics/sol_opus/SOL_OPUS_FORENSIC.md`
- `trajectories/overnight_push/SOL_OPUS_FORENSIC_DEPTH.md` → `docs/history/forensics/sol_opus/SOL_OPUS_FORENSIC_DEPTH.md`
- `trajectories/overnight_push/phase_d_cascade/FORENSIC.md` → `docs/history/waves/trajectories/overnight_push/phase_d_cascade/FORENSIC.md`
- `trajectories/overnight_push/phase_d_cascade/README.md` → `docs/history/waves/trajectories/overnight_push/phase_d_cascade/README.md`
- `trajectories/overnight_push/phase_d_cascade/STATUS.md` → `docs/history/waves/trajectories/overnight_push/phase_d_cascade/STATUS.md`
- `trajectories/overnight_push/reseed_weak_breaks_20260714/STATUS_FORENSIC.md` → `docs/history/waves/trajectories/overnight_push/reseed_weak_breaks_20260714/STATUS_FORENSIC.md`
- `trajectories/overnight_push/reseed_weak_breaks_20260714/TASKS_MANIFEST.md` → `docs/history/waves/trajectories/overnight_push/reseed_weak_breaks_20260714/TASKS_MANIFEST.md`
- `trajectories/overnight_push/thin_vein_cascade/FORENSIC.md` → `docs/history/waves/trajectories/overnight_push/thin_vein_cascade/FORENSIC.md`
- `trajectories/overnight_push/thin_vein_cascade/README.md` → `docs/history/waves/trajectories/overnight_push/thin_vein_cascade/README.md`
- `trajectories/overnight_push/thin_vein_cascade/STATUS.md` → `docs/history/waves/trajectories/overnight_push/thin_vein_cascade/STATUS.md`
- `trajectories/overnight_push/xmodel/xmodel_status.md` → `docs/history/waves/trajectories/overnight_push/xmodel/xmodel_status.md`
- `trajectories/overnight_push/xmodel/xmodel_status_opus.md` → `docs/history/waves/trajectories/overnight_push/xmodel/xmodel_status_opus.md`
- `trajectories/overnight_push/xmodel/xmodel_status_sol.md` → `docs/history/waves/trajectories/overnight_push/xmodel/xmodel_status_sol.md`
- `trajectories/overnight_push/xmodel18/xmodel_status_opus.md` → `docs/history/waves/trajectories/overnight_push/xmodel18/xmodel_status_opus.md`
- `trajectories/overnight_push/xmodel18/xmodel_status_sol.md` → `docs/history/waves/trajectories/overnight_push/xmodel18/xmodel_status_sol.md`
- `trajectories/overnight_push/xmodel_thin_vein/COST_AND_SEQUENCE.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/COST_AND_SEQUENCE.md`
- `trajectories/overnight_push/xmodel_thin_vein/logs/DISARMED.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/logs/DISARMED.md`
- `trajectories/overnight_push/xmodel_thin_vein/opus/DISCARDED.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/opus/DISCARDED.md`
- `trajectories/overnight_push/xmodel_thin_vein/sol/DISCARDED.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/sol/DISCARDED.md`
- `trajectories/overnight_push/xmodel_thin_vein/xmodel_status_opus.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/xmodel_status_opus.md`
- `trajectories/overnight_push/xmodel_thin_vein/xmodel_status_sol.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/xmodel_status_sol.md`
- `trajectories/structural_implicit_wave_20260714/STATUS_FORENSIC.md` → `docs/history/waves/trajectories/structural_implicit_wave_20260714/STATUS_FORENSIC.md`
- `trajectories/structural_implicit_wave_20260714/TASKS_MANIFEST.md` → `docs/history/waves/trajectories/structural_implicit_wave_20260714/TASKS_MANIFEST.md`
- `trajectories/xmodel_smoke/xmodel_status.md` → `docs/history/waves/trajectories/xmodel_smoke/xmodel_status.md`

### Complete delete list

- `.Rhistory`
- `agents/oracle_agent.py.precset2.bak`
- `agents/oracle_agent.py.prediv.bak`
- `harness/facts.py.precset2.bak`
- `harness/facts.py.prediv.bak`
- `server/tasks.py.prediv.bak`
- `server/verifiers.py.prediv.bak`
- `tests/test_cross_app_verifiers.py.precset2.bak`
- `tests/test_cross_app_verifiers.py.prediv.bak`
- `trajectories/_diverse_specs_wave1.json.prerenumber`
- `trajectories/overnight_push/phase_d_cascade/logs/cascade.pid`
- `trajectories/overnight_push/phase_d_cascade/logs/watchdog.pid`
- `trajectories/overnight_push/thin_vein_cascade/logs/cascade.pid`
- `trajectories/overnight_push/thin_vein_cascade/logs/watchdog.pid`
- `trajectories/overnight_push/thin_vein_cascade/logs/watchdog_respawner.pid`
- `trajectories/overnight_push/xmodel/logs/opus.pid`
- `trajectories/overnight_push/xmodel/logs/sol.pid`
- `trajectories/overnight_push/xmodel/logs/watchdog.pid`
- `trajectories/overnight_push/xmodel18/logs/forensic_waiter.pid`
- `trajectories/overnight_push/xmodel18/logs/opus.pid`
- `trajectories/overnight_push/xmodel18/logs/sol.pid`
- `trajectories/overnight_push/xmodel18/logs/watchdog.pid`
- `trajectories/overnight_push/xmodel_thin_vein/logs/opus.pid`
- `trajectories/overnight_push/xmodel_thin_vein/logs/sol.pid`
- `trajectories/overnight_push/xmodel_thin_vein/logs/watchdog.pid`
- `trajectories/overnight_push/xmodel_thin_vein/logs/watchdog_respawner.pid`
- `trajectories/phase_d_oracle/logs/server.pid`
- `trajectories/phase_d_oracle/logs/server_8180.pid`
- `trajectories/sellable_breakers_v2.csv.prefinal.bak`
- `trajectories/sellable_breakers_v2.csv.premerge77.bak`
- `trajectories/thin_vein_oracle/server.pid`

## Living documentation

Updated only for cleanup navigation/reference integrity:

- `.gitignore` — narrow rules for confirmed backup, renumber, R history, and trajectory PID artifacts
- `PROJECT_CONTEXT.md` — added a historical-handoff notice pointing to the final report, baseline, and history index
- `PROJECT_INFO.md` — changed only archived local evidence paths; conclusions and numbers are unchanged
- `FINAL_PRE_REPORT_BASELINE_2026-07-14.md` — changed only two archived local evidence paths; conclusions and numbers are unchanged

Retained byte-identically: `README.md`, `ANNOTATION_PIPELINE.md`, `DESIGN.md`, `FAILURE_TAXONOMY.md`, `ID_RESERVATIONS.md`, `MILESTONES.md`, `PHASE_E_SHEETS_SPEC.md`, `PIXEL_VS_JSON.md`, `TASKS.md`, and `WALKTHROUGH.md`. `docs/history/README.md` is the new concise archive index.

## Protected-source verification

- 432 manifest entries fall within the protected reference set (including expanded cited directories).
- 419 substantive cited-source entries were retained or moved with identical before/after git-blob hashes.
- 30 protected historical records were moved byte-for-byte; hashes are listed below.
- `PROJECT_INFO.md` and `FINAL_PRE_REPORT_BASELINE_2026-07-14.md` are the two living citation containers updated atomically to the archived paths.
- No cited substantive source file was content-modified or deleted.
- Eleven stale `*.pid` process markers occurred inside broadly cited trajectory directory roots. They were deleted under the explicit temp-cleanup rule; they are transient process state, not report evidence or cited source content.

### Protected byte-identical moves

- `ALL_TASK_BRIEFS.md` → `docs/history/snapshots/ALL_TASK_BRIEFS.md` — `89fa753ea74b6ed15d559d44cf6fcee95202cb1d`
- `FINAL_IMPLICIT_DESIGN_GATE_2026-07-14.md` → `docs/history/waves/final_implicit/FINAL_IMPLICIT_DESIGN_GATE_2026-07-14.md` — `c3dae7168196fa4480daa4c4bad717ca6f6bd8ab`
- `STRUCTURAL_IMPLICIT_WAVE_BUILD_STATUS_2026-07-14.md` → `docs/history/waves/2026-07-14/STRUCTURAL_IMPLICIT_WAVE_BUILD_STATUS_2026-07-14.md` — `b1cf17c7c5f742cf9e152732076811b1c9a8120e`
- `WAVE_PHASE_D_2026-07-14.md` → `docs/history/waves/2026-07-14/WAVE_PHASE_D_2026-07-14.md` — `c796cd8480e24e331daea30fce71d665c8d5ddf7`
- `WAVE_STRUCTURAL_IMPLICIT_PROPOSAL_2026-07-14.md` → `docs/history/waves/2026-07-14/WAVE_STRUCTURAL_IMPLICIT_PROPOSAL_2026-07-14.md` — `a8560afe5429ad07c1c0de1e3f25f4b97eed80e5`
- `WAVE_THIN_VEIN_2026-07-13.md` → `docs/history/waves/2026-07-13/WAVE_THIN_VEIN_2026-07-13.md` — `557af4ee6ffbd8efb7448f0d437113ea4d0b0f15`
- `trajectories/CHECKOUT_AXIS_AUDIT.md` → `docs/history/audits/CHECKOUT_AXIS_AUDIT.md` — `f29991183a9baba01b60b3e7b594388020eb1357`
- `trajectories/PENDING_MERGE_VALIDITY_AUDIT.md` → `docs/history/audits/PENDING_MERGE_VALIDITY_AUDIT.md` — `1f1bc0688ff011d0da192a1e60fc984840ce2986`
- `trajectories/SOL_OPUS_SELLABLE_VENN.md` → `docs/history/forensics/sol_opus/SOL_OPUS_SELLABLE_VENN.md` — `00b3ca7586636537bc0965bd701212867a953ff1`
- `trajectories/overnight_push/SOL_OPUS_FORENSIC.md` → `docs/history/forensics/sol_opus/SOL_OPUS_FORENSIC.md` — `b19627d419039ded736fc2660d62a61f93bbc683`
- `trajectories/overnight_push/SOL_OPUS_FORENSIC_DEPTH.md` → `docs/history/forensics/sol_opus/SOL_OPUS_FORENSIC_DEPTH.md` — `57ea9a415742943caf4ab58b49109ce2318b3587`
- `trajectories/overnight_push/phase_d_cascade/FORENSIC.md` → `docs/history/waves/trajectories/overnight_push/phase_d_cascade/FORENSIC.md` — `b070c2f81344f1f36d6e761a6827eda41869e370`
- `trajectories/overnight_push/phase_d_cascade/README.md` → `docs/history/waves/trajectories/overnight_push/phase_d_cascade/README.md` — `26dc7fac2f110a715f30a5d1aa29c1fb28956b2b`
- `trajectories/overnight_push/phase_d_cascade/STATUS.md` → `docs/history/waves/trajectories/overnight_push/phase_d_cascade/STATUS.md` — `f44c96dfc52e2e98e9db677e447283f872ac6183`
- `trajectories/overnight_push/reseed_weak_breaks_20260714/STATUS_FORENSIC.md` → `docs/history/waves/trajectories/overnight_push/reseed_weak_breaks_20260714/STATUS_FORENSIC.md` — `b390b90f3274b82dc0bba05e31f588fe7bd5e615`
- `trajectories/overnight_push/thin_vein_cascade/FORENSIC.md` → `docs/history/waves/trajectories/overnight_push/thin_vein_cascade/FORENSIC.md` — `700837a4a4a45c960430101d704c2347e90fe4ca`
- `trajectories/overnight_push/thin_vein_cascade/README.md` → `docs/history/waves/trajectories/overnight_push/thin_vein_cascade/README.md` — `d02e85b11cfd286f86fac690a63318ec182cb990`
- `trajectories/overnight_push/thin_vein_cascade/STATUS.md` → `docs/history/waves/trajectories/overnight_push/thin_vein_cascade/STATUS.md` — `70308c8e23fbba01f3dd0d22e12d2b839ae12ae9`
- `trajectories/overnight_push/xmodel/xmodel_status.md` → `docs/history/waves/trajectories/overnight_push/xmodel/xmodel_status.md` — `02f8505e982e5da741e7f9cf8cc90ab77ec1a306`
- `trajectories/overnight_push/xmodel/xmodel_status_opus.md` → `docs/history/waves/trajectories/overnight_push/xmodel/xmodel_status_opus.md` — `45ca3d97040eefa15b59a0789e1355afba5a5534`
- `trajectories/overnight_push/xmodel/xmodel_status_sol.md` → `docs/history/waves/trajectories/overnight_push/xmodel/xmodel_status_sol.md` — `8186bf769f73b608a8cd11e60f90ba0926a90ea4`
- `trajectories/overnight_push/xmodel18/xmodel_status_opus.md` → `docs/history/waves/trajectories/overnight_push/xmodel18/xmodel_status_opus.md` — `ad0cfa575591aecd2f72451cb912b8d43aadf551`
- `trajectories/overnight_push/xmodel18/xmodel_status_sol.md` → `docs/history/waves/trajectories/overnight_push/xmodel18/xmodel_status_sol.md` — `02e610e7949bc6397117306cf415c4da442d2023`
- `trajectories/overnight_push/xmodel_thin_vein/COST_AND_SEQUENCE.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/COST_AND_SEQUENCE.md` — `9887b1c7b88aae44547756f196716db8b217e569`
- `trajectories/overnight_push/xmodel_thin_vein/logs/DISARMED.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/logs/DISARMED.md` — `feee9e39bc3662cc0dee6f0a823aabf5671a6e38`
- `trajectories/overnight_push/xmodel_thin_vein/opus/DISCARDED.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/opus/DISCARDED.md` — `18d0f8e9c39a356cd45649ab2f924f5b3e97c586`
- `trajectories/overnight_push/xmodel_thin_vein/sol/DISCARDED.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/sol/DISCARDED.md` — `18d0f8e9c39a356cd45649ab2f924f5b3e97c586`
- `trajectories/overnight_push/xmodel_thin_vein/xmodel_status_opus.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/xmodel_status_opus.md` — `97740636297c59b63aabf2a908432c131964c5d5`
- `trajectories/overnight_push/xmodel_thin_vein/xmodel_status_sol.md` → `docs/history/waves/trajectories/overnight_push/xmodel_thin_vein/xmodel_status_sol.md` — `a8fe58cae37adebea9c83a264c7c3b4de9800166`
- `trajectories/structural_implicit_wave_20260714/STATUS_FORENSIC.md` → `docs/history/waves/trajectories/structural_implicit_wave_20260714/STATUS_FORENSIC.md` — `50588f728972c9457f8a82236339720288892f70`

## Checks

- Current HEAD re-inventory: passed; cleanup started at `6f6a1b5`.
- Manifest coverage: passed; 6,246 pre-cleanup non-ignored files, each with disposition and exact before/after git-blob hash where applicable.
- Protected substantive source existence/hash check: passed (419/419 unchanged).
- Protected archived move hash check: passed (30/30 byte-identical).
- Explicit final-report/baseline reference-set resolution: passed (49/49).
- `STATUS_FORENSIC.md` and root wave/status archive coverage: passed; none remain outside `docs/history/`.
- Move destination uniqueness/no data loss: passed (43 unique destinations).
- Staging check: passed; no staged changes.
- Markdown lints for changed living/history docs: passed.
- Code/tests were not changed, so no test run was required.
- `git diff --check`: passed.
- Final `git status --short`, `git diff --name-status`, and `git diff --stat`: captured during final validation.

## Unresolved blockers

None. Two unrelated uvicorn processes were active on ports 8092 and 8096, but none of the removed PID markers referred to those live process IDs; all 19 PID files were stale.
