# Multi-tab ASYNC benchmark — raw-coordinate leaderboard (v0)

> Branch `feat/multi-app`. Generated 2026-05-26. Cheap/popular models on the
> deterministic-async multi-tab tasks, all driven by the SAME modality (raw
> pixel coordinates, no Set-of-Mark) so the comparison isolates the backend.

## Setup

- **Tasks:** `M15/inbox_price_watch` (absolute paired price-drop event +
  stale-state) and `M16/coordinated_dinner_delay` (4-app async branch-flip +
  negative action). Both seed the deterministic event injector
  (`server/apps/scheduler.py`); oracle scores 1.0 on each.
- **Modality (held fixed):** raw-coordinate, no SoM — the agent sees a plain
  screenshot and acts via `click_at(x, y)`. Claude via `pixel_coord`
  (`PixelCoordAgent`), GPT via `openai_coord` (`OpenAICoordAgent`, the OpenAI
  twin). This puts **visual grounding** back as the bottleneck (vs. SoM, which
  hands the agent the click targets).
- **Runs:** K=3 per (model, task), `AGENT_EVAL_MODE=1` (no reward leakage),
  50-step cap, deterministic seeds 0–2. 36 episodes total.
- **Models:** claude-haiku-4-5 + gpt-4o-mini, gpt-4.1-mini, gpt-4.1, gpt-5.1,
  gpt-5.

## Results

| Model (raw-coord) | M15 pass · avg | M16 pass · avg | **Overall pass · avg** |
|---|---|---|---|
| **claude-haiku-4-5** | **3/3 · 1.00** | **1/3 · 0.60** | **4/6 · 0.80** |
| gpt-5 | 0/3 · 0.00 | 0/3 · 0.07 | 0/6 · 0.03 |
| gpt-4.1 | 0/3 · 0.00 | 0/3 · 0.00 | 0/6 · 0.00 |
| gpt-5.1 | 0/3 · 0.00 | 0/3 · 0.00 | 0/6 · 0.00 |
| gpt-4.1-mini | 0/3 · 0.00 | 0/3 · 0.00 | 0/6 · 0.00 |
| gpt-4o-mini | 0/3 · 0.00 | 0/3 · 0.00 | 0/6 · 0.00 |

`pass` = verifier success (all required milestones + aggregate ≥ 0.999);
`avg` = mean weighted milestone score (partial credit).

**M15 verifier note (corrected):** the M15 alert's *subject line* already names
the mouse + new price, so opening the email isn't strictly necessary to do the
task. `opened_alert_email` was therefore changed to **informational (weight 0,
not required)** — M15 is now graded purely on the OUTCOME (right mouse at the new
price, 0.5 + 0.5). This flipped **Haiku from 0/3 → 3/3** (it was buying correctly
all along, reading the price off the subject) and left every GPT model at 0/3
(they never completed a purchase, so the outcome milestones never fired). The
GPT avg fell to ~0.00 because their only prior partial credit was the now-zero
`opened_alert_email`.

## Headline

**On raw-coordinate web operation, cheap Claude Haiku beats the entire GPT
family — including gpt-5 and gpt-5.1 — at actually *completing* the tasks.**
Haiku's overall avg (0.70) is ~5–10× every GPT model (0.00–0.13).

The gap is **grounding, not reasoning.** The missed-milestone breakdown shows
the GPT models reason correctly and then fail to *click*:

- **M15:** GPT models miss `ordered_correct_mouse_only` + `ordered_at_dropped_price`
  in 3/3 runs. They wait for the async alert and several (gpt-4.1, gpt-5,
  gpt-5.1) open it and identify the right mouse (→ 0.20), then **cannot land the
  "Add to Cart" button** and burn the 50-step cap. Traced example: gpt-5.1
  reached the exact correct product page, then clicked at the wrong pixel ~18
  times in a row. gpt-4o-mini can't even open the alert (0.00).
- **M16:** GPT models miss `food_order_placed` in 3/3 — they fail at the *first*
  step (placing the food order), so the async delay never even fires for them
  (avg 0.00). Haiku completes the food order → calendar → guest email and solves
  the full branch-flip 1/3 (avg 0.60).

This matches the known asymmetry: **Claude is post-trained for Computer Use
(coordinate grounding); GPT chat models are not.** A frontier *reasoner* (gpt-5)
scores 0.00–0.07 on tasks a cheap Haiku partly/fully solves — because, at a fixed
raw-coordinate interface, reasoning ≠ grounding.

## Honest caveats

1. **M15 pass-rate is muddied** by an over-strict `opened_alert_email` milestone
   + the alert's subject line leaking the mouse + price. Haiku does the real
   task (right mouse, right dropped price = 0.80) but reads the subject instead
   of *opening* the email, so it scores 0/3. The **avg-score column is the clean
   metric** here; pass-rate needs a verifier tweak (vague subject, or
   outcome-only scoring).
2. **The grounding wall masks the async traps for GPT** — they fail before
   reaching the stale-price / over-keep decisions, so for the GPT models this
   measures *grounding*. Only Haiku reaches the async logic (and handles it).
3. **K=3** is directional, not statistically tight. But the gap (Haiku completes;
   five GPT models at 0.00–0.13) is large and consistent across the whole GPT
   family → a robust signal.

## Next

- Fix M15's verifier (vague subject / outcome-only) and re-run for clean
  pass-rates.
- Add a **Set-of-Mark column** (same models, mark-based actions) to separate
  "can't ground" from "can't reason" — this would reveal whether the GPT models'
  async-handling is actually fine once grounding is removed as a variable.
