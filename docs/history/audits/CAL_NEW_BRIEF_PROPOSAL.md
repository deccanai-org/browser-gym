# CAL new brief proposal — `cal_004` / `dentist_mail_reschedule_clear`

**Date:** 2026-08-02  
**Status:** packaged + Sol **3/3 BREAK** confirmed (`CAL004_SOL_BRIDGED_3SEED.md`)  
**Constraint:** week/month + edit update/delete only; no day-view / grid click-create. Goal-only brief (lh_002/lh_003 style — natural source hint, no trap spoilers).

## Brief (user-facing)

> My dentist appointment got moved — the confirmation is in my email. Get my calendar straight for it.

## Mechanism sketch

| | |
|---|---|
| **Seed shape** | Tomorrow (Fri May 22): `Dentist Cleaning` 10:00–11:00 (update target). `Budget review` 15:00–16:00 (true overlap at the new slot — delete). `Standup` 09:30–10:00 (near old slot — leave). Today: `Teeth whitening consult` 15:00–16:00 (same clock time, wrong day — decoy). Mail latest: River Dental confirms move to **3:00 PM** tomorrow (was 10:00 AM). Stale earlier mail still says 10:00 AM. |
| **Trap** | Anchor on stale 10:00 AM mail and leave calendar; `update` dentist onto 15:00 via unguarded `update_event` without clearing Budget review (silent double-book); delete whitening decoy (same clock, wrong day) or Standup near the old slot. |
| **Correct** | Week/Month + Mail latest → **update** Dentist Cleaning to 15:00–16:00 → **delete** Budget review. Leave whitening + standup. |
| **What breaks** | Source-anchoring (latest vs stale dental mail) × unguarded same-day update that can silently clash; selective delete of the true new-slot overlap. |

## Apps involved

**Calendar** + **Mail** (natural source for the new time). No Food/Shop.

## Why it avoids day-view / click-create

Discovery on Week/Month + inbox. Mutations are **edit → update** (dentist) and **edit → delete** (budget). No new event, no Day view, no grid click-create.

## Distinct from cal_001–003

| Task | Vein |
|---|---|
| cal_001 | Fuzzy weekend / nephew party (pure Calendar) |
| cal_002 | Conditional Food cancel gated on calendar hold |
| cal_003 | Multi-hold interview reconcile + free/busy gate + recruiting summary |
| **cal_004** | Single-event mail-driven reschedule + mandatory overlap clear; goal-only brief |

## Ports

`STACK_SLOT=25` · gym `:10578` · bridge `:10591` · calendar `:10601` · mail `:10611` (`STACK_PORT_OVERRIDES=1`; `STACK_APPS="calendar mail"`).
