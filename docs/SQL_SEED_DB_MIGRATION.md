# SQL Seed-DB Migration — Architecture & Plan

*Branch: `feat/sql-seed-db`. Status: Phase 0 in progress. This document is the
plan of record; nothing here changes runtime behaviour until the equivalence gate
(below) is green and the `SEEDDB_MODE` flag is flipped.*

## Why

Shravan's research doc specifies the WebArena/WorkArena pattern —
`base_seed_db → task_setup_overlay → rollout_runtime_clone` — as the foundation
for scalable RL browser-agent training. Today our gym has **no database at all**:
world state is built by ~312 Python factory functions in `server/tasks.py`
(~12.8k lines), held entirely in-memory in one global `SESSION`, and
JSON-serialised via `to_json()`. This migration moves the **seed data** into a
SQL database while changing **nothing** about how the live episode runs.

## The two hard guarantees

The user's mandate: *nothing lost, don't break anything.* Both are made
**mechanical**, not promised:

1. **Nothing lost** — for every `(task_id, seed)`, the SQL-hydrated world must be
   byte-identical to today's code-built world. Enforced by a CI-blocking
   three-level equivalence gate (see [Nothing-Lost Proof](#nothing-lost-proof)).
2. **Nothing breaks** — every `/_harness/*` response stays byte-identical, so the
   annotator platform (workspace isolation, world-preservation, prefix-restore,
   checkpoints, replay) cannot tell the storage changed.

Regression baseline captured before any change: **1497 gym tests pass** (1
pre-existing unrelated failure: `test_generated_matrix_...` `KeyError:
integrity_check_order`, a stale generated artifact — not touched by this work).

## Architecture — "hydrate behind `make_task`"

Adopted design (of two evaluated), hardened by an adversarial loss/break review.

- The seed data becomes **one read-only SQLite file**,
  `fixtures/seed.db.v<N>.sqlite`. It is a **seed source only** — it replaces the
  factory *bodies* as the origin of the reset baseline, and nothing else.
- The live episode stays **100% in-memory dataclasses**, mutated by the unchanged
  `server/mutations.py`, serialised by the unchanged `to_json()`, resumed by the
  unchanged `server/apps/statecodec.py`.
- The only new runtime seam is one function, `seeddb.hydrate_world(task_id, seed)`,
  which `make_task` delegates to **behind a `SEEDDB_MODE` flag**. It returns the
  **same type the factory returns** — a bare `GymState` for single-app A/B/C/D
  tasks, a `WorldState` for cross-app M tasks (driven by a `task.world_kind`
  column) — so it flows through the **unchanged `_reset_inline`**
  (`server/main.py:196-214`): single-app sub-app defaulting, the
  `initial`/`initial_world` deepcopy, `build_suite`, verifiers reading live
  dataclasses, and every `/_harness/*` shape are provably untouched.
- **The DB is generated *from* the factories** by an extractor, never
  hand-authored. The factory stays the source of truth and the runtime fallback,
  so the DB **cannot drift** from the code and no task needs re-expression.
- **Isolation is unchanged.** `seed.db` is baked read-only into the image and
  opened read-only, so it is shared across workspace containers with **zero
  collision risk** — collisions require shared *writes*; hydrate only reads. The
  "clone-per-rollout" is the existing per-reset hydrate + `deepcopy`.

### Determinism preserved exactly

- Entity ids stay their **literal derived string values** — no DB
  autoincrement/UUID ever touches a serialised id.
- `mint_counts` (a `@property`, not a field) is **never persisted** — it is empty
  at the seed baseline and excluded from `asdict()`.
- The per-app `_next` id counters (`MailState em_{n}`, `CalendarState ev_{n}`,
  `FoodState FOOD-{1040+n}`, `MarketState VM-{2200+n}`) **are** restored, so the
  first post-hydrate mint reproduces byte-identically. (This is strictly better
  than `statecodec` resume, which currently drops them.)
- Seed-**dependent** values (A2's PRNG laptop price via `random.Random(seed)`;
  the `seed % 2` "Book club" calendar parity) are **re-computed live by rule** at
  hydrate time — never stored as seed-keyed lookup rows — so **any** seed
  reproduces, including seeds outside the captured set. Seed-**invariant** rows
  are stored once as `scope='base'`.

## The loss-traps the review caught (guard these)

The adversarial pass found the places data would be **silently** lost. Each is
now a design requirement:

| Trap | Why it's silent | Guard |
|---|---|---|
| **Catalog dict insertion order** | Invisible to the hash gate (catalog not in `to_json`, only `products_count`) *and* to the asdict gate (`dict ==` is order-insensitive) — yet pages render `products.values()` in insertion order, so a reorder changes which SKU the agent clicks and diverges trajectories | Explicit `pos` ordinal column + `ORDER BY pos`; **Level-3 render/DOM check** in the gate |
| **Hidden dataclass fields** absent from `to_json` (`armed_*` mail traps, `account_name`, every `_next`, food `defer_receipt_steps`/`enable_delivery_notes`, market `store_name`/`fees`) | Dropped if the extractor sources rows from `to_json()` instead of the live dataclass | Extractor sources from `dataclasses.asdict` + explicit hidden-field reads; **Level-2 asdict gate** is the only one that sees them, so it is mandatory |
| **List order** (`Cart.items`, `Order.items`, `Shipment.events`, variants, reviews) | SQL rows have no inherent order | Mandatory `pos` column + `ORDER BY` on every list relation; `list[str]` fields stored as ordered JSON |
| **Seed-varying baselines** for out-of-set seeds | A seed-keyed lookup table only covers captured seeds | Re-run the exact Python computation at hydrate; gate on an **out-of-set seed** |
| **int vs float** (`5` vs `5.0`) | JSON/REAL columns collapse the distinction | Type columns `INTEGER`/`REAL`; canonicalise integral floats on **both** sides of the gate |
| **4 seed-time wall-clock factories** (`tasks.py:1775, 1915, 2750, 3375`) | `estimated_delivery = datetime.now() - N days` drifts by calendar day | **Phase 0** freezes them to fixed literals (these were already non-reproducible across days) |

## Nothing-Lost Proof

Three levels, run for **every `(task_id, seed)`** over `SEED_SET = {0,1,2,3,42}`
plus an **out-of-set seed (99)**, all CI-blocking, each comparing SQL-hydrate
against **both** the live factory **and** a frozen golden:

- **Level 2 — MASTER (the actual proof).** `asdict_canonical(hydrate) ==
  asdict_canonical(live factory) == golden asdict_hash`. `dataclasses.asdict`
  recurses the **entire** dataclass graph, so it sees everything `to_json` hides
  and everything the hash strips — the full catalog, every non-current user,
  every snapshot field, every hidden field. `canonical` collapses integral floats
  on both sides. Comparing against the **live factory** (not just the golden)
  proves faithfulness for *any* seed, which proves a live **rule engine** — not a
  lookup table — drives the seed-dependent values.
- **Level 1 — annotator-contract corollary.** `hash_world(to_json(hydrate)) ==
  hash_world(to_json(live)) == golden to_json_hash`, using the annotator's oracle
  (`hash_world`/`_normalize`) copied verbatim into `server/seeddb/_equiv.py`.
  Necessary but insufficient (blind to catalog/traps, strips volatile), so it is
  **never** the cutover criterion — but it *is* the exact bytes the annotator's
  checkpoints/replay compare, so we test the real consumer offline.
- **Level 3 — render gate.** Closes the catalog-order gap both other levels are
  provably blind to: assert hydrate's product key-order == golden `product_order`
  **and** the rendered `/catalog` + `/category` + search HTML/DOM hash == golden
  `render_hash`. Plus a pipeline cross-check: two gyms (code vs sql) run the
  built-in oracle for **every** task and assert identical final verdict +
  identical per-step `/_harness/world` hash.

The flag stays **off** until every level is green for all 312 tasks. Factories are
**never deleted** — generator and fallback.

### Anti-drift guards (standing CI, from review)

Two things that are true *today* but silently rot the first time someone edits
either side — so they are permanent tests, not one-time verifications:

- **Cross-repo hash parity.** The gym's `hash_world`/`_normalize` in `_equiv.py` is
  copied verbatim from the annotator's `checkpoints.py`. A test hashes a shared
  fixture with both and asserts equality, so "copied verbatim" cannot quietly
  diverge when someone "improves" one side.
- **`build_wrapped` == real reset.** A test resets the live server and asserts
  `build_wrapped(t, s)` equals `SESSION.world` (asdict + to_json hash) for a
  sample of tasks. If `_reset_inline` gains a line and `build_wrapped` doesn't, the
  goldens would silently start lying — this catches it.

### CI cost tiering (from review)

The gate is not one monolith. Split by cost so the cheap proof runs on every PR
and only the expensive cross-check waits for nightly/release:

- **Per-PR (fast):** Level-2 asdict + Level-1 hash over 312 × SEED_SET — pure
  in-memory factory builds + hashing, no browser (seconds–minutes).
- **Nightly / release (heavy):** the Level-3 render check and the all-task oracle
  per-step cross-check (312 browser-driven episodes ×2, code vs sql) — minutes to
  tens of minutes. Blocks the cutover, not every commit.

## Phased plan (additive, non-destructive)

| Phase | Goal | Exit criterion |
|---|---|---|
| **0 — Stationarise + freeze goldens** | Make `make_task` byte-stationary across calendar days; capture the reference the migration is graded against. Freeze the 4 wall-clock factories to literals; build `server/seeddb/_equiv.py` (`hash_world`, `asdict_canonical`, `build_wrapped`); write `tools/gen_goldens.py`. **No SQL yet.** | `gen_goldens.py` produces a byte-identical `seed_hashes.json` on two runs; full suite green; 4 frozen tasks' date tests updated |
| **1a — Schema + extractor** ✅ | Materialise `seed.db` by mechanically shredding the (stationary) factory output into rows — never hand-authored | **Done.** All 1560 cells reconstruct byte-equivalent (value + order); reproducible content hash; 6 CI tests |
| **1b — Base/overlay + seed_rule** | Store the shared catalog once (`scope='base'`) with per-task overlays; compute seed-dependent values live for out-of-set seeds | File shrinks from ~56 MB to a few MB; an out-of-set seed reconstructs; same round-trip gate stays green |
| **2 — Hydrator + gate (flag OFF)** | Prove `hydrate_world` reproduces byte-equivalent worlds at all three levels, server still on factories | `test_seeddb_equivalence.py` green for all 312 × (SEED_SET + out-of-set) at Levels 1–3; wired CI-blocking |
| **3 — Live cutover (behind flag)** | Gym serves from `seed.db`; annotator observes zero difference | Live smoke (all 312 reset→world==golden) green; all-task oracle per-step cross-check green; annotator e2e green; then `SEEDDB_MODE` defaulted ON |
| **4 — Adjacent determinism** | Close the 2 runtime wall-clock leaks (`mutations.py:521, :651`) the migration surfaced but doesn't own | A checkout- and a subscription-bearing trajectory replay byte-identically across two calendar days; `grep datetime.now server/` → 0 code hits |

## Schema

The full DDL is in `server/seeddb/schema.sql`. Conventions:

- `scope` = `'base'` (shared, in every clone) or a `task_id` (per-task overlay patch).
- `pos` = insertion ordinal **captured from the real built world** — reconstructs
  both list order and dict key-insertion order via `ORDER BY pos`.
- `tombstone` = overlay delete marker (a task that removes a base row).
- `*_json` = typed-as-dict / `list[str]` fields, stored as JSON (order preserved inside).
- `INTEGER` vs `REAL` is deliberate so Python `int 5` round-trips as `5`, not `5.0`.
- **No columns for derived keys** (`products_count`, `unread_count`, `cart_count`,
  `cart_subtotal`, `pending`, calendar `today`/`tomorrow`, `current_user`) —
  recomputed by the unchanged `to_json` from hydrated rows.
- `mint_counts` is **never** stored.

`schema.sql` is the fully field-normalised *target* (one column per field). What
**Phase 1a actually ships** (`server/seeddb/store.py`) is a safer interim that
reaches the same losslessness by a shorter path: one queryable table per entity
type (`shop_product`, `shop_order`, `mail_message`, `market_product`, …) whose
rows carry `(task_id, seed, key, pos, data_json)`, where `data_json` is the
entity's **complete `asdict`** — plus a `task` row holding a `remainder_json` of
everything not lifted into a collection (scalars, carts, schedule, event log,
each sub-app's scalar fields). Reconstruction is `remainder` + collections
re-inserted in `pos` order, so **nothing can be silently dropped**: whatever is
not a collection row stays in the remainder. Hidden fields (`armed_*`, `_next`,
`account_name`) ride along in `asdict` for free; `mint_counts` is a property so
`asdict` excludes it for free. It is genuinely relational — `SELECT
json_extract(data_json,'$.name') FROM shop_product …` works — and field-level
column promotion is a mechanical refinement on top.

The `.sqlite` is a **reproducible build artifact, not committed** (it rebuilds
from the factories in ~4 s via `python -m server.seeddb.build_seed_db`); the
factories remain the source of truth. Phase 1a stores rows per `(task, seed)` for
the captured SEED_SET — the base/overlay de-dup and live `seed_rule` (Phase 1b)
shrink the file and cover arbitrary seeds without changing this contract.
