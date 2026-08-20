# M379-M382 screening manifest — 2026-07-14

Final disposition: M379-M381 passed their pre-build gates and remain live.
M382 was removed from the live registry after the required independent review
collapsed it into the existing generic compatibility-selection mechanism
(M312/M254). Its already-completed oracle and Qwen artifacts are retained below
as audit evidence only and are excluded from the valid-wave track record.

Tasks:

- M379/transitive_session_lunch_dedup
- M380/earliest_uncovered_training_supplies
- M381/self_approval_does_not_authorize_gift_card
- M382/public_event_requires_display_license

Protocol: standard per-task Qwen → gpt-5.1 → gpt-5.5 → Sonnet cascade,
seeds 0, 1, 2 at every reached tier, 2/3 BREAK escalation, 120 maximum
steps, model-specific standard context guards, and infrastructure-only retries.

The run uses this directory as its dedicated shared cost root. It does not use
Xmazon as a task app, Sol, Opus, or sellable-CSV merging.
