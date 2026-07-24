# Sellable CSV vs 44e27e1 — drift check (2026-07-23)

## Question

Is current `trajectories/sellable_breakers_v2.csv` drifted *after* remediation commit `44e27e1`, or is any dirty-tree delta just that remediation landing on another branch?

## Verdict

**Intentional follow-up / cross-worktree reconcile — do not revert.**

- Blob at `44e27e1` = `471b8a15b763290d0c72bd23f1d6410f71b1785b`.
- Both worktrees’ **current file contents** match that blob exactly.
- `git diff 44e27e1 -- trajectories/sellable_breakers_v2.csv` is **empty** everywhere the working tree holds the remediation CSV.

There is **no post-44e27e1 content drift**. The only “dirty” signal is on `ecommerce-browser-gym` (`feat/docs-sheets-coupons` @ `2a133e9`), where HEAD still has the pre-remediation blob and the working tree was updated to match `44e27e1` (identical to the sonnet-completions worktree). That is applying known remediation onto an older branch tip, not accidental junk.

## Worktrees

| Worktree | Branch / HEAD | CSV vs `44e27e1` | Status |
|----------|---------------|------------------|--------|
| `ecommerce-browser-gym-sonnet-completions` | `feat/multi-app` @ **`44e27e1`** | identical | clean |
| `ecommerce-browser-gym` | `feat/docs-sheets-coupons` @ `2a133e9` | WT identical; HEAD is pre-remediation | `M` (WT = remediation) |

File mtime on the drifted copy: **2026-07-23 12:53:13** (matches commit author time **12:53:15 -0700**).

## When / who

- **Commit:** `44e27e16e91069e63a06442281428289e7ac8f5d`
- **Author / committer:** ArunMurari `<154778442+jkbooster@users.noreply.github.com>`
- **Date:** 2026-07-23 12:53:15 -0700
- **Subject:** Apply M211/M220/M224 sellable disposition remediations.
- **Co-authored-by:** Cursor `<cursoragent@cursor.com>`
- **Blame** on changed rows M211/M220/M224 at that commit: `44e27e16` (same author/date).

## The 3-line change (full patch = commit `44e27e1`)

`git show 44e27e1 -- trajectories/sellable_breakers_v2.csv` → **3 lines changed** (M211, M220, M224). Same as `git diff HEAD -- trajectories/sellable_breakers_v2.csv` on `ecommerce-browser-gym` (WT bringing remediation onto pre-commit HEAD).

Field-level:

| Task | What changed |
|------|----------------|
| **M211** | grid `0/3·2/3·2/3` → `0/3·1/3·2/3`; tier `strong-pair(5.5+son)` → `sonnet-only`; models_broken / robustness notes updated for affirmative re-score |
| **M220** | robustness note only (+ 2026-07-23 confirm); grid/tier unchanged |
| **M224** | robustness note only (+ Sol seed0 note); grid/tier unchanged |

## Table 1 impact

**No — does not change Table 1 65/7/12/1.**

Commit message and `SELLABLE_PENDING_DISPOSITION_DIFFS_2026-07-23.md` state explicitly: M211 remains Sonnet-break (sonnet still ≥2/3); M220/M224 strongest-tier membership unchanged. **Flag: Table 1 not “final” until any broader ledger freeze, but this CSV delta does not move the headline counts.**

## Recommendation

- **Report-only; do not revert** the WT CSV on `ecommerce-browser-gym` if the intent is to carry remediation onto that branch.
- Prefer committing/cherry-picking `44e27e1` (or the CSV blob) onto `feat/docs-sheets-coupons` when ready, rather than leaving a long-lived dirty copy.
