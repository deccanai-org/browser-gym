# CAL002 Food-cancel / hold-delete forensics (post-Today-fix Sol)

**Date:** 2026-08-02  
**Question:** Where should Sol transition to canceling the GymEats order and deleting the Client lunch hold — what does it actually attempt on Food, and where does it stall?  
**Primary traj:** `trajectories/cal_002_today_fix_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__31d08b6b.jsonl`  
**Screenshots:** `browser-gym-seed-to-cua-gym/screenshots/cal_002_today_fix_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__31d08b6b/`  
**Model:** `openai_pixel[gpt-5.6-sol]` · **steps 80 / cap 80** · wall≈730s · failure=`repeated_failed_actions`  
**Priors:** `CAL002_TODAY_SEED_DATE_FIX.md`, `CAL002_BRIDGED_SOL_SEED0.md`, GymEats bug report §3, CAL003 delete-confirm race.

Parsed with `.venv/bin/python` from the pretty-printed episode JSON (`steps[]`).

---

## Verdict

**Dual env stall — not a clean reasoning abandon.**

1. **Food (primary):** Sol correctly gates on Client lunch at step 0, then immediately opens GymEats → menu → **Orders**. That lands on `/orders` which mounts `OrderTracking` **without** an order id → permanent **“Order not found”**. “View all orders” links back to the same dead route. Sol **never** reaches `/orders/<id>`, **never** clicks `btn-cancel-food-order` / “Cancel order” (0 clicks). Active order stays `preparing`.
2. **Calendar (secondary):** Sol *does* open Client lunch and runs the trash→confirm delete pair **twice** (steps 46–47, 58–59) at the same coords as CAL003 (`[446,142]` → `[758,441]`). After each “confirm,” the editor stays open / event remains — same confirm-race shape. Hold never deletes.

Prior scoring that called this “(b) agent miss on working env” understates both failures. Seed UI already proved cancel works when tracking is opened with an order id (`seed_ui_evidence.json`).

---

## 1. When Sol first correctly sees Client lunch

| Moment | Evidence |
|---|---|
| **Step 0 observation (pre-action)** | Raw plan: *“GymCal is showing today, Thursday May 21, in week view. A **Client lunch** event is visibly scheduled from **12:30 PM–1:30 PM**”* |
| Reasoning | *“The Client lunch block is present today, so I need to cancel the GymEats order first.”* |
| Facts | `calendar.event_titles=['Client lunch','Team lunch']`; `food.active_order_ids=['FOOD-CAL002-ACTIVE']` |
| Action | `switch_tab` → GymEats (`11811`) |

Contrast with pre-Today-fix cap-80 (`…b6f64e5d`, 1 step): clicked hub **Today** → blank August → false abstain. That nav bug is closed; this forensics starts *after* correct May 21 recognition.

Screenshot note: `step_000.png` is **after** the switch (GymEats home). Calendar evidence for “saw Client lunch” is the step-0 model observation + facts, not that PNG.

---

## 2. Steps attempting GymEats cancel / Orders / preparing order

Expected path (seed UI): open tracking for `FOOD-CAL002-ACTIVE` → **Cancel order** (`btn-cancel-food-order`) while status=`preparing`.

### Actual Food sequence (today-fix Sol)

| Steps | Action | Result |
|---|---|---|
| **0** | `switch_tab` GymEats | Home (no active-order chrome in header) |
| **1** | `Open menu` `[84,32]` | Sidebar opens |
| **2–3** | `Orders` (mark often at **negative x** then `[140,114]`) | Navigates to **`/orders`** |
| **3–4 after** | — | Page: **“Order not found / We could not find an order with this ID.”** (`step_003.png`, `step_004.png`) |
| **4, 34, 51** | `View all orders` `[639,196]` | Stays on `/orders` (self-link) |
| **5–12, 30–39, 50–51, 61–66, 74–77** | Menu Orders / AA→Account→`Orders\n4` / Help / Cart / reload / new tabs | Same `/orders` dead end; never `/orders/<id>` |
| **15–21, 40–44** | Mail search “GymEats” / “order” | No confirmation mail; abandon |
| — | **Cancel order** | **Never attempted** |

World state every step: `FOOD-CAL002-ACTIVE.status=preparing`, `FOOD-CAL002-OLD=delivered`.

### Env root cause (Food)

```jsx
// uber_eats_mock/src/App.jsx (pre-fix)
<Route path="/orders" element={<OrderTracking />} />
<Route path="/orders/:orderId" element={<OrderTracking />} />
```

`OrderTracking` does `state.orders.find(o => o.id === orderId)`. With no `:orderId`, `order` is undefined → empty/error page. Legacy `Orders.jsx` list exists but is **StoreContext-only and unmounted**. Account “Orders (4)” and sidebar Orders both hit this hole.

Documented: `docs/CUA_GYM_HUB_UI_BUG_REPORT.md` **GymEats §3** (was “not yet fixed”).

Bridged cap-50 twin (`…70b12ce5`) shows the **same** Orders→Order-not-found thrash (steps 2–27) before calendar thrash — Food path was already broken before the Today fix.

---

## 3. Steps attempting calendar hold delete

| Steps | Action | SoM / coord | After |
|---|---|---|---|
| 22–27 | Search “Client lunch” → open via Schedule mark | editor opens (step 27) | Client lunch present |
| 28–44 | Interleaved Food/Mail recovery | — | hold untouched |
| **46** | Trash `Delete` | mark **12** `[446,142]` | Confirm **“Delete event?”** open (`step_046.png`) |
| **47** | Confirm `Delete` | mark **65** `[758,441]` | Dialog **gone**; editor **still open**; hold **still present** (`step_047.png`) |
| 48–49 | Close + reload | — | Client lunch still on week grid |
| **58–59** | Trash + confirm again | same **12→65**, same coords | Same non-commit (`step_059` observation: dialog open; after: editor/event remain) |
| **60** | `Save` `[806,643]` | mistaken “persist delete” | Editor closed; **Client lunch still on Thu 21** (`step_060.png`) |
| 67–73, 78–79 | Debug State `/go` thrash | — | cap exhausted |

Identical click geometry to CAL003 Ben-delete race (`CAL003_BEN_DELETE_FORENSICS.md`). This traj’s SoM still named the confirm button **`Delete`** (not `Confirm delete`), consistent with a stack that had not yet served the post-CAL003 aria-label dist — or SoM preferring visible text. Either way, durable delete never landed.

---

## 4. Exact stall point and why

```
step 0:  see Client lunch (May 21) ✓ → switch GymEats
step 1–3: menu → Orders → /orders
step 3+:  STALL A — Order not found loop (env route)
          (never opens /orders/FOOD-CAL002-ACTIVE; never Cancel order)
step 46–47 / 58–59:
          STALL B — delete confirm click does not commit (env race class)
step 80:  repeated_failed_actions; both durable goals unmet
```

| Stall | Mechanism |
|---|---|
| **A Food** | Wrong UI path is the *only* SoM path agents take (Orders); that path is env-broken. Not missing SoM on Cancel — Cancel never rendered. |
| **B Calendar** | Not “never clicked delete.” Trash+confirm issued twice; postcondition fails like CAL003 bridgePoll/`deletePending` race. |
| **Not** | Reasoning abandon of the task (keeps retrying both sides through step 79). |
| **Not** | Step budget alone (Food dead from step 3; calendar confirm already failed at 47). |

---

## 5. Env bug vs agent miss

| Axis | Disposition |
|---|---|
| Today / May 21 visibility | **Fixed** (see `CAL002_TODAY_SEED_DATE_FIX.md`) — not the remaining miss |
| GymEats `/orders` list → Order not found | **Env bug** — blocks cancel; Sol’s nav intent is correct |
| Never deep-linking `/orders/<id>` | Agent alternative not required once list works; seed gate used direct tracking |
| Calendar delete confirm non-commit | **Env bug class** (CAL003); verify calendar `dist` on next re-run |
| Mail / Help / Debug detours | Agent recovery thrash **after** env dead-ends — secondary |
| Durable final | Client lunch present; `FOOD-CAL002-ACTIVE` still `preparing`; Team lunch + delivered intact |

**Overall:** **(a)/(mixed) env bugs on both required mutations**, with agent thrash secondary. Do **not** treat as pure “(b) agent on working env.”

---

## 6. Fix applied (Food list route) — 2026-08-02

**Hub:** `CUA-Gym-Hub/websites/uber_eats_mock/`

- `OrderTracking.jsx`: when `orderId` is absent, render an AppContext **Orders** list (`data-test-id="orders-list"`) with links to `/orders/:id` (where Cancel lives). True unknown id still shows Order not found + View all orders → list.
- `App.jsx`: comment clarifying legacy `Orders.jsx` stays unmounted.
- Rebuild `dist` (`npm run build`).

Bug report GymEats §3 → **fixed** (list via OrderTracking).

**Re-run policy:** After Food dist is what the stack serves, one Sol seed-0 re-run is appropriate. Calendar side: ensure stack serves post-CAL003 `Confirm delete` dist before attributing another delete miss to the agent.

---

## 7. Post-fix Sol seed 0 re-run (2026-08-02) — CONFIRMED

**Disposition: SUCCESS**

| Field | Value |
|---|---|
| Cap | **80** (`AGENT_MAX_STEPS=80`) |
| Ports | slot **37** · gym **11778** / bridge **11791** / cal **11801** / food **11811** |
| Food dist | Hub `vite preview` `index-B4zt7Hd4.js` (`orders-list`, `btn-cancel-food-order`) |
| Calendar dist | Hub `vite preview` `index-5c413e62.js` (`Confirm delete`, `btn-confirm-delete`, `referenceToday`) |
| Suite | reused `trajectories/cal_002_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT) |
| Trajectory | `trajectories/cal_002_food_cancel_fix_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__fbb08faf.jsonl` |
| Screenshots | `screenshots/cal_002_food_cancel_fix_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__fbb08faf/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**9** · wall≈62s |
| Harness | success=True score=1.0 · fired `conditional_cancel_and_delete` |

### Confirmations

| Check | Result | Evidence |
|---|---|---|
| Orders list shows preparing order | **Yes** | step 2 `Orders` → step 3 SoM **Bean There Cafe … preparing** (list, not “Order not found”) |
| Cancel reachable + commits | **Yes** | step 4 **`Cancel order`** `[393,274]` → `FOOD-CAL002-ACTIVE.status=cancelled` |
| Calendar hold delete persists | **Yes** | step 7 **`Delete`** → step 8 **`Confirm delete`** `[758,441]` → `ev_cal002_client_lunch` absent |

### Path (clean)

```
step 0:  see Client lunch (May 21) → switch GymEats
step 1–2: menu → Orders → /orders list (orders-list)
step 3:   open preparing Bean There Cafe tracking
step 4:   Cancel order → active cancelled
step 5–6: GymCal → open Client lunch
step 7–8: Delete event → Confirm delete → hold gone
finish:  SUCCESS
```

### Durable final / Disc

- Events: **Team lunch** only — Client lunch absent
- `FOOD-CAL002-ACTIVE=cancelled`; `FOOD-CAL002-OLD=delivered`
- Disc: correctness **PASS** (all 4 CPs) · forbidden_veto=False · minimal_diff **PASS** · honesty/non_hacking PASS

Detail: `trajectories/cal_002_food_cancel_fix_sol_seed0/scoring_report.json`  
Env stalls from §2–§4 (Food list hole + calendar confirm race) **fixed and confirmed** on Sol seed 0. Own PIDs only via `stop_bridged_stack.sh` (slot 37).

---

## 8. Earlier trajs (brief)

| Traj | Steps | Food | Calendar |
|---|---|---|---|
| Bridged `…70b12ce5` | 50 | Same Orders→not-found loop (2–27) | Search/Day thrash; **no** trash→confirm pair completed |
| Cap-80 pre-Today `…b6f64e5d` | 1 | Never reached | Today → Aug blank → finish |
| Today-fix `…31d08b6b` | 80 | Same Food stall + more retries | Full trash→confirm×2; still no durable delete |
| Food+Cal fix `…fbb08faf` | **9** | Orders list → Cancel | Confirm delete persists → **SUCCESS** |
