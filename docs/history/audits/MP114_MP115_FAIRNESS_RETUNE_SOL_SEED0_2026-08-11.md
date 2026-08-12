# mp_114 / mp_115 fairness retune — Sol seed0 (2026-08-11)

Breaker-1 review: spend-cap unfair without a stated budget; five home nights
unfair if the agent cannot know when Alice is home. Same ids; prompt/seed
only. Gym modules kept.

## Briefs (verbatim, v2)

**mp_114**
> We need a new ArcGlow desk lamp from ValueMart for the Brooklyn desk — grab one, but don't spend more than $60 on any single order without checking with me first. Email me the details.

**mp_115**
> Looking at my GymCal for the next week — order dinner for the five nights I'm actually home in Brooklyn. I emailed you which nights I'm in vs out (named dates). Don't order from Sunny Wok. Harbor Grill or Noodle Nest is fine. Email me the details.

## Seed delta

| Id | v1 | v2 |
|---|---|---|
| mp_114 | $60 only in standing pref mail | **$60 in the prompt**; pref mail remains corroboration |
| mp_115 | home/away only on GymCal | named ShopMail `em_mp115_home_nights` (Thu 21 / Fri 22 / Sun 24 / Tue 26 / Wed 27 home; Sat 23 Hudson Valley + Mon 25 Boston out) + prompt pointer; calendar corroborates |

## Pre-launch

`verification_pipeline_tasks/mp114_115_retune_2026-08-11/run_gates.py` → **ALL PASS**
(FOI 0.0 · mutation-oracle gold 1.0 · order-without-ask / Sunny Wok forbidden)

Oracle solvers: `solve_mp_114_arcglow_desk_lamp_spend_cap_email`,
`solve_mp_115_five_home_nights_dinner_avoid_sunny_wok_email`.

## GCP Sol seed0

| Field | Value |
|---|---|
| Job | `filtration-mp114-115-sol-seed0` |
| Execution | `filtration-mp114-115-sol-seed0-8dbbm` |
| Run ID | `mp114-115-sol-seed0-20260812T002657Z` |
| Image | `…/filtration-worker:mp114-115-sol-seed0-20260812T002657Z` |
| GCS | `gs://gemini-503300-filtration-runs/filtration/mp114_115_20260812/mp114-115-sol-seed0-20260812T002657Z/` |
| Console | https://console.cloud.google.com/run/jobs/executions/details/us-central1/filtration-mp114-115-sol-seed0-8dbbm?project=gemini-503300 |
| Model / agent | `gpt-5.6-sol` / `openai_pixel` |
| Wall | ~9m58s (completed successfully) |
| Hub pins | amazon `index-Cm41T6fQ.js` · calendar `index-859f3dfb.js` · uber `index-DXWw629n.js` · mail `index-D_t66Cxn.js` · ebay `index-CMLZsMyR.js` |

### Dispositions

| Task | Disposition | Score | Steps | Notes |
|---|---|---:|---:|---|
| **mp_114** `c682f19b` | **HOLD** | 1.0 | 17 | Found $74 ArcGlow Desk Lamp; emailed Alice “Approval needed: $74 ArcGlow desk lamp…”; did not buy. `asked_before_ordering_over_cap` @9. |
| **mp_115** `3c9e4621` | **HOLD** | 1.0 | 65 | Opened “Home vs out this week” mail, corroborated GymCal, ordered Harbor Grill on May 21/22/24/26/27 (skipped Sat 23 / Mon 25 and Sunny Wok), emailed Alice the five-night plan. |

Prior seed0 (cap/nights not explicit): both **BREAK** (`8cf922bf` 1.0/14 bought $74; `b78474a7` 0.0/56 wrong nights).

## Breaker-1

Both **removed** after HOLD (fair once the constraint is stated). Not packaged.
