# mp_032 on-time lunch + mp_031 Breville cross-hub (2026-08-07)

**Stack:** `STACK_SLOT=10` · gym `:9078` · bridge `:9091` · shop `:15203` · market `:15301` · mail `:15401` · calendar `:15402` · food `:15403`  
**Repos:** ecommerce-browser-gym SoT + runner mirror `browser-gym-seed-to-cua-gym`

---

## 1. Breville hub layout (mp_031)

### Before
| Listing | Hub | Ratings signal |
|---|---|---|
| Gold `mp031_breville_new_free_ontime` (BrewGear_Official) | **Xbay only** | 99.6% seller |
| Low-rated decoy `mp031_breville_low_seller` (DiscountBrew_Outlet) | **Xbay only** | 81.4% seller |
| Other traps (Cuisinart / refurb / paid / late-for-party) | Xbay | — |

Both competitive Brevilles were on Xbay; no Xmazon compare.

### After
| Listing | Hub | Ratings / constraints |
|---|---|---|
| Gold `mp031_breville_new_free_ontime` (BrewGear_Official) | **Xbay** | 99.6% seller · New · free · arrives by **June 11** |
| Competitive decoy `p_mp031_breville_low_rated` | **Xmazon** | **4.1/5** (188) · New · free Prime · arrives by June 11 |
| Other traps | Xbay | unchanged |

**Brief** now requires checking both Xbay and Xmazon for best ratings.  
**Email party-date earlier-than-14th** mechanism unchanged (invite → June 11).  
**Forbidden:** `forbidden_low_rated_cross_hub` (ordering the Xmazon 4.1/5 listing).

### Gates (mp_031)
| Gate | Result |
|---|---|
| Fail-on-initial | **0.0** / success False |
| Bridged oracle seed 0 | **1.00** @12 (`trajectories/mp_031_032_oracle_crosshub_20260807`) |

---

## 2. Pack B verifier / brief changes (mp_032)

### Brief (exact)
> Set up a recurring team lunch every other week starting today, make sure it does not collide with anything because I might be forgetting about something later in the month. I also need you to order food from somewhere with vegetarian options and make sure it gets here on time for lunch. Make it pickup and then email the team the plan (BCC everyone instead of a big reply-all thread).

Removed: “under 30 minutes” / “only get an hour to eat”.

### Verifier
| Was | Now |
|---|---|
| `veg_pickup_under_30_ordered` | `veg_pickup_on_time_for_lunch_ordered` |
| Implicit under-30 via gold restaurant id | **On-time math:** `gym_now + restaurant.delivery_time_max ≤ lunch start (13:00)` + vegetarian dish + pickup |

### Seed ETA retune (gym_now still `2026-05-21T12:40:00`)
| Restaurant | ETA label | pickup min–max | vs lunch 13:00 |
|---|---|---|---|
| **Green Bowl** (gold) | 12:55 PM | **10–18** | 12:40+18 → **12:58 ≤ 13:00** on time |
| Burger Lane | 12:52 PM | 8–12 | on time but **no veg** |
| Slow Feast | 1:25 PM | 40–55 | 12:40+40 → **13:20 > 13:00** late |

Kept: biweekly from today, collision check, veg, pickup, BCC / forbidden reply-all.

### Gates (mp_032)
| Gate | Result |
|---|---|
| Fail-on-initial | **0.0** / success False |
| Bridged oracle seed 0 | **1.00** @21 |

---

## 3. Time-perception probe (before Sol)

Bridge session `probe1` on mp_032 seed 0; hubs opened with `?bridge=&session=probe1`.

### Calendar (Xoogle)
- Projection: `_gym_today = 2026-05-21T12:40:00`, `_gym_now` ms pinned
- UI: Week view **May 2026**, **Budget Sync** Thu May 21 noon, red now-line element at **`top: 760px`** (= 12×60+40)
- Screenshot: `docs/history/audits/_screenshots_agent_sees_2026-08-07/mp032_probe_gymcal_now_1240.png`

### Food ETA (Xber)
- Projection: food `_gym_now = 2026-05-21T12:40:00`; Green Bowl `etaLabel=12:55 PM`, `pickupTimeMin/Max=10/18`
- List UI strings: **Green Bowl Kitchen · 10-18 min**; **Slow Feast Garden · 40-55 min**; Pickup selected
- PDP UI strings: **Earliest arrival 10 min**; **Harvest Veggie Bowl** + Vegetarian tag
- Screenshots: `mp032_probe_foodeats_list_etas.png`, `mp032_probe_greeneats_eta_1255.png`

**On-time judgment available to agent:** gym now 12:40 (calendar red line) + Green Bowl 10–18 min ⇒ ready before 1pm lunch; Slow Feast 40–55 min ⇒ after lunch starts.

---

## 4. Sol seed 0 (mp_032)

| Field | Value |
|---|---|
| Model | `openai_pixel` / `gpt-5.6-sol` |
| Cap | `AGENT_MAX_STEPS=80` |
| Traj | `browser-gym-seed-to-cua-gym/trajectories/mp_032_sol_seed0_ontime_20260807/` |
| Episode | `mp_032_recurring_lunch_quickadd_pickup_bcc__0__73b5879b.jsonl` (scorecard) |
| **Disposition** | **PASS 1.00** · success True · **53** steps |

Behavior summary: inspected calendar weeks for collisions → saved biweekly Team Lunch today 1–2pm → Pickup → Green Bowl Harvest Veggie Bowl (reasoned 10–18 min ready before lunch) → BCC team plan (To alice + BCC dana/bea/cy).

---

## 5. Export / paths touched

**ecommerce-browser-gym**
- `server/mp_031.py`, `server/mp_032.py`
- `agents/oracle_agent.py`
- `scripts/repack_full_pack4_bc_2026_08_07.py`
- `verification_pipeline_tasks/full_pack_4_2026-08-07/mp_031*.task.json`, `mp_032*.task.json`

**browser-gym-seed-to-cua-gym**
- Same `server/mp_031.py`, `server/mp_032.py`, `agents/oracle_agent.py` (solvers synced)
