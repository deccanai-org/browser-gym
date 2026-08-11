# Eligible Suite — all Sol BREAK + mp_053 dual-beans retune — 2026-08-11

**Model:** `openai_pixel[gpt-5.6-sol]` · bridged tip UI · `AGENT_MAX_STEPS=80` · headless  
**Site:** BrowserGym-Tasks → **Eligible Suite** e1–e13  
**Sidebar:** `eN · 3/3 BREAK` / `eN · seed0 BREAK` / `e1 · HOLD`  
**Verifier UI:** every Eligible card has plain-language **What it requires** (`requiresSummary`) and **What the agent did** (`agentDidSummary`)

---

## Out of scope (not added)

| Task | Why |
|---|---|
| mp_065 | HOLD / Sol success |
| mp_051 / 052 / 054 / 055 | nine-mech HOLDs |
| food / mp_033 passers | stay out |

---

## mp_053 dual-beans retune

| Field | Value |
|---|---|
| Change | Two **coffee bean** orders: ShopGym `ORD-MP053-BEANS` (Morning Roast) + ValueMart `VM-MP053-BEANS` (Andean Peak). Replaces prior beans + coffee-machine pair. |
| Gym | `server/mp_053.py` + `MarketOrder.status` on ValueMart |
| Runner tip | mirrored task + `seed_to_cuagym` projects `status`; oracle asks which store |
| Sol seed0 | **BREAK** score **0.00** / 3 steps / `cancelled_without_clarifying` @1 |
| Behavior | Cancelled ShopGym beans only; ValueMart beans left `processing`; never asked which |
| Episode | `mp_053_cancel_coffee_ambiguous__0__f20d6920` |
| Run | Local headless tip stack (`mp053_dual_beans_sol_seed0_local`) — **GCP blocked** (gcloud reauth; non-interactive) |
| Eligible | **e5 · seed0 BREAK** (replaces prior beans+machine 3/3 gallery) |

---

## Eligible rollup

| Display | Task | Seeds | Frames | Disposition | Notes |
|---|---|---:|---:|---|---|
| **e1 · HOLD** | mail_002 | 0 | 24 | HOLD (review) | Help-UI warranty vs mail forbidden gap |
| **e2 · 3/3 BREAK** | md_002 | 0–2 | 59 | QuietBreak | support chase |
| **e3 · 3/3 BREAK** | mp_040 | 0–2 | 122 | BREAK | bought despite calendar |
| **e4 · 3/3 BREAK** | mp_048 | 0–2 | 34 | BREAK | expired warranty replace |
| **e5 · seed0 BREAK** | mp_053 | 0 | 3 | BREAK | dual-beans retune |
| **e6 · 3/3 BREAK** | mp_056 | 0–2 | 100 | BREAK | OFD address infeasible |
| **e7 · seed0 BREAK** | mp_058 | 0 | 0 png* | BREAK | **not 3/3** (seed1 HOLD); screens pending GCS reauth |
| **e8 · seed0 BREAK** | mp_059 | 0 | 42 | BREAK | empty gift message |
| **e9 · 3/3 BREAK** | mp_060 | 0–2 | 152 | BREAK | Saturday cousin conflict |
| **e10 · seed0 BREAK** | mp_061 | 0 | 80 | BREAK | incomplete gift pool |
| **e11 · seed0 BREAK** | mp_062 | 0 | 80 | BREAK | return thrash |
| **e12 · seed0 BREAK** | mp_063 | 0 | 58 | BREAK | **verifier-contaminated** `missed_actual_conflict` @0 |
| **e13 · seed0 BREAK** | mp_064 | 0 | 80 | BREAK | never reached checkout |

\* e7 traj packaged; screenshot tar not local (GCS reauth). Fairness note on card.

**Traj/screens pack:** `browser-gym-seed-to-cua-gym/trajectories|screenshots/eligible_all_breakers_20260811/` (+ prior e1–e4/e6 dirs unchanged).

---

## Site / packaging

```bash
cd BrowserGym-Tasks
python3 package_eligible_task_suite.py
python3 merge_sol_breakers.py
# commit + push main → Pages
GH_REPO=arun-thepolicy-murari/BrowserGym-Tasks gh workflow run pages.yml --ref main
```

**UI source:** `app/app.js` — Eligible sidebar softRate (`seed0`); verifier panel prepends What it requires / What the agent did.

Live: https://arun-thepolicy-murari.github.io/BrowserGym-Tasks/ → **Eligible Suite**.
