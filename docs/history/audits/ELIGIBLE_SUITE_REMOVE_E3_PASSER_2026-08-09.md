# Eligible Suite — remove e3 / food_003 (passer)

**Date:** 2026-08-09  
**Site:** [BrowserGym-Tasks](https://arun-thepolicy-murari.github.io/BrowserGym-Tasks/) · tab **Eligible Task Suite**

## Reason

Sol **3/3 PASS** after the Leaf & Grain + GymCal week-scroll retune
(`FOOD003_THIRD_RESTAURANT_CAL_VISIBLE_2026-08-09.md`). Eligible Suite is
**breakers only** — passers do not stay in the pool.

## Site change

- Dropped **e3** / `food_003/team_dinner_named_restaurants` from
  `package_eligible_task_suite.py` / `eligible_task_suite/tasks.json`.
- Remaining: **e1** `mp_033` BREAK, **e2** Lumos `mail_002` BREAK (IDs unchanged).
- Removed Eligible e3 full-gallery screens (`…__0__c4ff00a1` + orphan prior episode);
  Sol Breakers **n10** food_003 curated screens kept.
- Gym task code for `food_003` **not** deleted.

## Refresh

```bash
# BrowserGym-Tasks
python3 package_eligible_task_suite.py && python3 merge_sol_breakers.py
```

## Deploy

BrowserGym-Tasks `main` @ `2a513e1` — Pages workflow run succeeded (workflow_dispatch).
