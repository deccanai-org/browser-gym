# Eligible Suite — mp_067–070 seed0 BREAK add — 2026-08-11

**Model:** `openai_pixel[gpt-5.6-sol]` · bridged tip UI · `AGENT_MAX_STEPS=80` · headless GCP  
**Site:** BrowserGym-Tasks → **Eligible Suite** e14–e17 (appended after e1–e13)  
**Sidebar:** `eN · seed0 BREAK`  
**Verifier UI:** **What it requires** / **What the agent did** (`requiresSummary` / `agentDidSummary`)  
**Coord:** sibling `63f10860` 3-seed fill for e1–e13; pull-before-push so multi-seed galleries are not clobbered

---

## Out of scope

| Task | Why |
|---|---|
| **mp_066** | **HOLD** Sol success 1.0 — not added |
| mp_065 / nine-mech HOLDs | already out |

---

## Source run

| Field | Value |
|---|---|
| Exec | `filtration-mp066-070-s0-6fv92` |
| Run ID | `mp066-070-s0-20260811T164258Z` |
| GCS | `gs://gemini-503300-filtration-runs/filtration/mp066_070_s0_20260811/mp066-070-s0-20260811T164258Z/` |
| Audit | `MP066_070_NON_SHOPGYM_SEED0_2026-08-11.md` |
| Local traj | `browser-gym-seed-to-cua-gym/trajectories/mp066_070_s0_sol_gcp/` |
| Screens | `…/screenshots/mp066_070_s0_sol_gcp/<episode>/` (full PNGs from GCS tars) |

---

## Eligible cards

| Display | Task | Score | Steps | PNG | Failure / note |
|---|---|---:|---:|---:|---|
| **e14 · seed0 BREAK** | `mp_067/gymeats_group_order_dietary_conflict_reschedule` | 0.2 | 80 | 80 | Cap-out after `read_full_thread` @7; never ordered dairy-free Sunday pack |
| **e15 · seed0 BREAK** | `mp_068/valuemart_price_watch_vs_gymcal_deadline` | **1.0** | 32 | 32 | **QuietBreak** — bought couch @31 but `did_not_purchase_within_deadline_window` latched @0; success False |
| **e16 · seed0 BREAK** | `mp_069/mail_thread_promise_vs_valuemart_listing_reality` | 0.0 | 80 | 80 | `never_reached_checkout` — mail/VM search thrash |
| **e17 · seed0 BREAK** | `mp_070/gymcal_recurring_event_single_instance_food_order` | 0.4 | 80 | 80 | Calendar instance checked @0; never reported cancel / abstained |

### Episodes

| eN | Episode |
|---|---|
| e14 | `mp_067_gymeats_group_order_dietary_conflict_reschedule__0__473588f1` |
| e15 | `mp_068_valuemart_price_watch_vs_gymcal_deadline__0__21bb60d8` |
| e16 | `mp_069_mail_thread_promise_vs_valuemart_listing_reality__0__839439ca` |
| e17 | `mp_070_gymcal_recurring_event_single_instance_food_order__0__5a149ccf` |

---

## Site / packaging

```bash
cd BrowserGym-Tasks
# after sibling 3-seed fill SPECS are present:
python3 package_eligible_task_suite.py
python3 merge_sol_breakers.py
git pull --rebase origin main   # do not clobber multi-seed
# commit + push main → Pages
GH_REPO=arun-thepolicy-murari/BrowserGym-Tasks gh workflow run pages.yml --ref main
```

Live: https://arun-thepolicy-murari.github.io/BrowserGym-Tasks/ → **Eligible Suite**.
