# M384 formula-bar append thrash — Control+a harness bug — 2026-07-20

**Sources:** no-LLM Playwright probe `tests/test_sheets_formula_control_a.py`; postfix trajs `trajectories/sheets_s1_cascade_20260720_postfix/qwen/`; `harness/runner.py` `key_press` / `type_into_mark`; workbook `ui/pages/sheets/workbook.html`.  
**S2/S3:** not screened.

## Corrected verdict

**Harness infra bug (Darwin Chromium), not (primarily) model capability.**

On Chromium/macOS, raw `page.keyboard.press("Control+a")` is the emacs **line-start** binding: caret → 0, **no selection**. True select-all is `Meta+a` / Playwright `ControlOrMeta+a`.

Pre-fix cascades ran on Darwin. Agents correctly emitted `key("Control+a")` for overwrite; the harness passed that chord through unchanged → Backspace was a no-op at caret 0 → next `type_into_mark` appended (`12` → `122` → …). Prior audits that blamed “model motor failure / unfocused after Enter” were **wrong** on the root cause:

- Enter/`saveCell` with `focusFormula: false` does **not** blur the formula bar (focus stays).
- Standalone focused Control+a (pre-fix) did **not** select-all.

`type_into_mark` click-then-type without clear remains intentional Anthropic-CU semantics (first append `1`→`12` is expected). Overwrite via Control+a+Backspace was broken underneath that.

## Evidence (no LLM)

| Probe | Result |
|---|---|
| Raw `keyboard.press("Control+a")` on focused formula `"12"` | caret 0..0; type `"X"` → **`X12`** (prepend) |
| `Meta+a` / `ControlOrMeta+a` | select 0..2; type `"X"` → **`X`** (replace) |
| Harness-normalized Control+a → type (no click) | **`2`** replace |
| Control+a → Backspace → `type_into_mark("2")` | **`2`** replace |
| Seed-0 chain: append → Enter → Control+a → Backspace → type | **`2`** replace (post-fix) |
| Control+a → `type_into_mark` **without** Backspace | **`122`** append (click collapses selection; intentional) |

## Fix

`BrowserCtx.key_press` maps `Control+a` / `Control+A` → Playwright `ControlOrMeta+a` (`harness/runner.py`). Agents keep emitting `Control+a`; Linux/Windows still get Control; macOS gets Meta.

Focused regression: `tests/test_sheets_formula_control_a.py` (6 cases).

## Cascade

Fresh Qwen-first M384 panel after fix: [`trajectories/sheets_s1_cascade_20260720_ctrla_fix/`](../../../trajectories/sheets_s1_cascade_20260720_ctrla_fix/)

| Seed | Verdict | Notes |
|---|---|---|
| 0 | **success** 1.0 | Control+a → Backspace → type recovery; Market + Mail |
| 1 | incomplete | Unrelated app-bar/Calendar thrash; never Market |
| 2 | **success** 1.0 | Same overwrite recovery; Market + Mail |

**2/3 SUCCESS / 0 BREAK** → protocol **defended at Qwen** (`eval/cascade_v2`: escalate iff BREAKs ≥2/3; else STOP). Pre-fix postfix was **0/3 SUCCESS** with systematic `12`/`122` thrash. Fix unblocked the panel. Candidate-breaker origin does not change the gate.

**Consolidated story:** [`SHEETS_SCAFFOLD_INFRA_INTEGRITY_ARC_2026-07-20.md`](SHEETS_SCAFFOLD_INFRA_INTEGRITY_ARC_2026-07-20.md).

## What remains model-side

Even with working select-all, agents must still use the documented protocol (`Control+a` → `Backspace` → type) rather than Control+a then `type_into_mark` alone (click collapses selection). First-append after cell select remains tool semantics. Seed 1 shows residual navigation fumbling — keep as secondary **overwrite/edit capability risk**, not the root cause of the old thrash.
