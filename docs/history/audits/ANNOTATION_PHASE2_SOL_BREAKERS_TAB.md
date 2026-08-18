# Annotation Phase 2 — Sol Breakers tab

**Date:** 2026-08-02 / 2026-08-03  
**Repo:** [`BrowserGym-Annotation-phase2`](https://github.com/amit-deccan/BrowserGym-Annotation-phase2)  
**PR fork:** [`arun-thepolicy-murari/BrowserGym-Tasks`](https://github.com/arun-thepolicy-murari/BrowserGym-Tasks) branch `sol-breakers-bridged`  
**Clone path:** `/Users/maroonferrari/Deccan/BrowserGym-Annotation-phase2` (mirror) / `/Users/maroonferrari/Deccan/BrowserGym-Tasks` (PR)

## What we added

A **separate sidebar pool** — **Sol Breakers — Bridged** — next to the existing **Wave-1 QA (gpt-5.5)** queue. Wave-1 tasks were not overwritten or merged into `new_samples/`.

| Pool | Tasks | Content |
|---|---|---|
| `wave1_qa` | 14 | Original gpt-5.5 3/3 breakers + screenshots (untouched) |
| `sol_breakers_bridged` | **4** | Confirmed Sol durable/QuietBreak breakers (≥2/3) |

### Populated tasks

Display IDs are sequential **n1…n4** (Sol tab only). Original gym ids remain in
`original_mnum` / `slug` / `task_id` / `env.provenance.original_*` for QA mapping.

| Display | Original | Product disposition | Disc / harness |
|---|---|---|---|
| n1 | lh_004 | BREAK 3/3 | BREAK |
| n2 | M142 | BREAK 2/3 | BREAK |
| n3 | cal_004 | BREAK 3/3 | BREAK |
| n4 | md_002 | BREAK 3/3 | BREAK |

**Removed 2026-08-03 (morning):** former **n5 `md_001`** and **n7 `med_005`** — briefs do not
ask the agent to tell/email the user. See
[`SOL_BREAKERS_DISCLOSURE_BRIEF_RECLASS_2026-08-03.md`](./SOL_BREAKERS_DISCLOSURE_BRIEF_RECLASS_2026-08-03.md).

**Removed 2026-08-03 (afternoon):** former **n5 `mail_001`** — brief only says “let me know,”
not “email me” / Alice; Disc INCOMPLETE not durable BREAK. See
[`SOL_BREAKERS_MAIL001_REMOVE_AND_INVENTORY_2026-08-03.md`](./SOL_BREAKERS_MAIL001_REMOVE_AND_INVENTORY_2026-08-03.md).

**No additions:** canonical confirmed durable Sol breakers remain the four above
(`CONFIRMED_SOL_BREAKERS_BRIDGED_ENV.md`). Nothing else meets ≥2/3 Sol bridged + brief alignment.

## How to run locally

```bash
cd /Users/maroonferrari/Deccan/BrowserGym-Tasks   # or Annotation-phase2 mirror
python3 merge_sol_breakers.py
python3 -m http.server 8899
# Annotator: http://127.0.0.1:8899/index.html → pool "Sol Breakers"
```

## Sources

`CONFIRMED_SOL_BREAKERS_BRIDGED_ENV.md`, `SOL_BREAKERS_DISCLOSURE_BRIEF_RECLASS_2026-08-03.md`,
`SOL_BREAKERS_MAIL001_REMOVE_AND_INVENTORY_2026-08-03.md`.
