# Screenshot consolidate — 45 tasks into `screenshots/{Mxx__slug}/` — 2026-07-24

Follow-up to [SCREENSHOT_RECOVERY_AND_NORMALIZE_45_2026-07-24.md](./SCREENSHOT_RECOVERY_AND_NORMALIZE_45_2026-07-24.md).

Moves the canonical per-task visual tree from `artifacts/task_visuals/` into
`screenshots/{Mxx__slug}/` so all 45 tasks share one home alongside the
historical bucket dirs.

| Constraint | Status |
|---|---|
| `trajectories/sellable_breakers_v2.csv` | **Untouched.** SHA256 = `c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30` |
| Trajectory JSONL / dispositions | **Not modified** |
| Mechanism | **Hardlinks** (`os.link`), same filesystem — no byte duplication |
| Python | `.venv/bin/python scripts/consolidate_task_visuals_to_screenshots.py --retire` |

---

## Target layout (now canonical)

```
screenshots/{Mxx__slug}/
  SOURCE.md
  seed_state/
    seed{N}_initial.png (+ .live.json), seed{N}_initial.json,
    seed{N}_final.json, seed{N}_final_oracle.png, static_start.png
  oracle/seed{N}__{hash}/step_XXX.png
  models/{model}/seed{N}__{hash}/step_XXX.png
    (+ seed_initial/final pairs + REPLAY_RECOVERY.json where replayed)
```

## What ran

1. Hardlinked every file under `artifacts/task_visuals/{Mxx__slug}/` into
   `screenshots/{Mxx__slug}/` (**7256** hardlinks, **45** SOURCE.md rewrites).
2. Verified **45** tasks, **7301** files, **453** filmstrip dirs — identical
   counts before/after; structure check (seed_state + oracle + models +
   SOURCE.md) passed for all 45.
3. Retired `artifacts/task_visuals/`: real trees removed; left
   `DEPRECATED.md` plus **45 per-task symlinks** →
   `../../screenshots/{Mxx__slug}` so older doc paths (e.g. M90/M210 forensic)
   still resolve.
4. Pointed `scripts/normalize_task_visuals.py` and
   `scripts/capture_seed_initials.py` at `screenshots/` for future runs.
   Normalize skips already-normalized `Mxx__*` dirs and non-bucket folders
   when re-indexing historical buckets.

## Old `screenshots/{oracle,pixel,openai_pixel,harvest}/`

**Left intact.** Episode dirs for these 45 tasks remain in the historical
buckets. Filmstrip PNGs are hardlinked into the new per-task tree (sample
`nlink=2`), so trajectory `screenshot_path` values that pointed at bucket
paths keep working. No conflicting duplicate content was introduced under
those bucket names — the new layout is sibling `Mxx__slug/` directories,
not a rewrite of the buckets.

## Breakage risks

| Risk | Assessment |
|---|---|
| Traj JSONL still cites `screenshots/{oracle,pixel,…}/…` | **Safe** where those dirs existed: hardlinks keep inodes at the old paths. Pre-existing misses (episode hashes whose dirs were never on disk) are unchanged by this move. |
| Docs citing `artifacts/task_visuals/…` | **Safe** via per-task symlinks + `DEPRECATED.md`. |
| Live `seed{N}_initial.png` (were nlink=1 only under artifacts) | Now live under `screenshots/…/seed_state/`; artifacts path reaches them through symlink. |
| Re-running normalize | Safe: skips `Mxx__*` siblings; `link()` no-ops when dest exists. |

## Scripts

| Script | Role |
|---|---|
| `scripts/consolidate_task_visuals_to_screenshots.py` | One-shot migrate + optional `--retire` |
| `scripts/normalize_task_visuals.py` | Builds/refreshes `screenshots/{Mxx__slug}/` from buckets |
| `scripts/capture_seed_initials.py` | Writes live seed_initial captures under `screenshots/…/seed_state/` |

## Post-consolidation missing-screenshot grouping

All 45 per-task directories were subsequently moved from
`screenshots/{Mxx__slug}/` to `screenshots/missing/{Mxx__slug}/` (internal
layout unchanged: seed_state/, oracle/, models/, SOURCE.md). This includes
the 16 replay-recovered tasks (M77, M78, M79, M84, M87, M90, M91, M93,
M98, M99, M100, M101, M102, M104, M207, M210) and the 29 tasks that already
had screenshots under the old convention. All 45 compatibility symlinks
under `artifacts/task_visuals/` now target
`../../screenshots/missing/{Mxx__slug}`; none dangle. The historical
`screenshots/{oracle,pixel,openai_pixel,harvest}/` buckets are untouched.
