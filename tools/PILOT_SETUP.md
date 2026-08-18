# Realistic-UI pilot — run the gym on the CUA-Gym-Hub UIs

The gym serves the **realistic mock UIs** (Amazon / Gmail / eBay / Google Calendar /
Uber Eats) seeded from its own tasks. The UIs come from XLang's public
[CUA-Gym-Hub](https://github.com/xlang-ai/CUA-Gym-Hub); we push each task's seed
world into them via their state API. No cua-gym DB or Kashyap dependency.

## App mapping

| Gym app | Realistic UI | mock key | port |
|---|---|---|---|
| shop (ShopGym) | Amazon | xmazon_mock | 5201 |
| market (ValueMart) | eBay | xbay_mock | 5202 |
| mail (ShopMail) | Gmail | xmail_mock | 5203 |
| calendar | Google Calendar | xoogle_calendar_mock | 5204 |
| food | Uber Eats | xber_eats_mock | 5205 |

## One-time setup

```bash
# 1. clone the UIs next to the gym repo
git clone https://github.com/xlang-ai/CUA-Gym-Hub.git

# 2. apply the bridged-mode patches (one per app). These wire each mock's client
#    interactables to the gym engine (see "Bridged mode" below) AND, for uber,
#    include the systemB fix (that mock ships internally broken — two parallel
#    context systems cross-wired). The 5 *_bridged.patch supersede the standalone
#    xber_eats_mock_systemB.patch — apply the bridged set, not both.
for a in xmazon_mock xbay_mock xmail_mock xoogle_calendar_mock xber_eats_mock; do
  git -C CUA-Gym-Hub apply "<gym>/tools/patches/${a}_bridged.patch"
done

# 3. install each mock's deps (npm cache must be writable; use a local one if ~/.npm is locked)
for a in xmazon_mock xbay_mock xmail_mock xoogle_calendar_mock xber_eats_mock; do
  npm --prefix CUA-Gym-Hub/websites/$a install --cache ./.npm-cache --no-audit --no-fund
done
```

## Run the pilot

```bash
HUB=/path/to/CUA-Gym-Hub TASK="M301/stale_tracking_forward_sycophancy" SEED=0 \
  tools/run_pilot.sh
```

This starts all five mocks, seeds every app of the task into its mock, and prints a
URL per app (each carries its own `sid`). Open them to see the gym task's data in
the realistic UIs.

## How seeding works

`tools/seed_to_cuagym.py` does **dump → transform → load**:
- **dump** — `asdict(build_wrapped(task_id, seed))` = the gym's full per-app world.
- **transform** — one function per app maps the gym shape → that mock's state shape.
- **load** — `POST {mock}/post?sid=<sid> {"action":"set","state":{…}}` (the CUA-Gym-Hub
  state API). `GET {mock}/state?sid` is what the UI reads; `GET {mock}/go?sid` returns
  `{initial_state, current_state, state_diff}` — a **built-in verifier diff** for scoring.

Modes: `--post URL` (one mock), `--mock-map app=URL,...` (a whole task across mocks),
`--commit` (write to a cua-gym Postgres instead, via `CUA_GYM_DSN`).

## Session management (`tools/session_manager.py`)

Implements the base -> clone -> discard model: a frozen `seed_sid` per (task, app),
cloned into a per-attempt `attempt_sid` that the annotator mutates and is TTL-wiped.
Sessions are tracked in a SQLite registry (`tools/.pilot_sessions.sqlite`).

```bash
MM="shop=http://127.0.0.1:5201,mail=http://127.0.0.1:5199,market=http://127.0.0.1:5202,calendar=http://127.0.0.1:5204,food=http://127.0.0.1:5205"
python -m tools.session_manager start  --task M301/... --seed 0 --annotator alice --mock-map "$MM"  # -> session id + per-app URLs
python -m tools.session_manager diffs  --session <id>   # per-app /go state_diff (verifier signal)
python -m tools.session_manager golden --session <id>   # keep this session's trajectory
python -m tools.session_manager expire                  # wipe non-golden sessions past TTL (cron)
python -m tools.session_manager end    --session <id>
python -m tools.session_manager list
```

Each attempt is isolated (a mutation in one session never touches the seed or another
session), golden sessions survive `expire`, and `PILOT_TTL_MIN` (default 90) sets the window.

## Wiring it into the annotator (cua-hub mode)

The annotator's live browser opens these seeded UIs when **`CUA_HUB_MODE=1`** is set on
the backend. Flow (`backend/app/api/live.py::_open_cua_session` + `app/cua_hub.py`):
a gym task's `open_live_session` clones each app's frozen `seed_sid` into a fresh
`attempt_sid` (isolated per annotator), lands the live browser on the task's primary
app, and returns the others as tabs — bypassing the gym lease/seed/restore path.

Deploy config on the annotator backend:
```bash
CUA_HUB_MODE=1
CUA_HUB_DOMAIN=delta.deccanexperts.ai          # prod subdomains, OR per-app overrides:
CUA_HUB_URL_SHOP=http://amazon-mock:5201        CUA_HUB_URL_MAIL=http://gmail-mock:5203
CUA_HUB_URL_MARKET=http://ebay-mock:5202        CUA_HUB_URL_CALENDAR=http://gcal-mock:5204
CUA_HUB_URL_FOOD=http://ubereats-mock:5205
```
Prereq: run `tools/seed_all_tasks --mock-map "$MM"` once so every task's `seed_sid`
exists for the clone. The annotator's `seed_sid` scheme matches the gym seeder exactly.

**Remaining for the hosted deploy** (needs the live-browser service reachable from the
backend + a redeploy — untestable locally): confirm the live-browser can reach the mock
hosts, and set each task's card `allowedSites` to the cua hosts via `cua_hub.allowed_sites()`.

## Bridged mode — realistic UIs as a live front-end over the gym engine

Seeding (above) makes the mocks *show* a task's world. **Bridged mode** makes them
*drive* it: a click in the realistic UI runs the REAL gym engine (full logic —
cross-app bus, scheduler, breaker traps, verifiers) and the result is re-projected
back into every tab. This is what closes the gap between "UI shell" and "full gym
semantics" — a shop order's confirmation email shows up in the Gmail tab on its own.

```
click in the realistic UI
  -> semantic action (tools/bridge.py ACTIONS, per app)
  -> the gym's OWN http action endpoint         (mutation + cross-app hook)
  -> WorldState advances with FULL logic         (bus / scheduler / traps fire)
  -> re-project live world -> mock state         (seed_to_cuagym.transform_world)
  -> push to every mock tab                       (cross-app effects appear)
  -> gym's real verifier suite scores it          (/_harness/verify)
```

**Pieces**
- `tools/bridge.py` — the library. `Bridge(gym_url, mock_map, harness_token)` with
  `reset / project / push / act / tick / verify`. `ACTIONS` maps each app's
  interactables to the gym's real endpoints (all 5 apps wired).
- `tools/bridge_service.py` — the HTTP seam the mocks call: `POST /bridge/reset`,
  `POST /bridge/act`, `GET /bridge/state`, `GET /bridge/verify`, `GET /bridge/actions`.
- `tools/bridge_client.js` — a drop-in shim: swap a mock's data layer to call
  `bridgeAct(...)` and render the returned per-app state (amazon add-to-cart /
  place-order worked example inside).
- `GET /_harness/world_full` (gym) — the complete world (asdict, incl. the shop
  catalog that `/_harness/world`'s `to_json` drops) that the bridge re-projects.

**Run it**
```bash
# 1. gym engine with a harness token
HARNESS_TOKEN=dev uvicorn server.main:app --port 8077
# 2. bridge service pointed at it (+ optional per-app mock push targets)
GYM_URL=http://127.0.0.1:8077 HARNESS_TOKEN=dev \
  CUA_HUB_URL_SHOP=http://127.0.0.1:5201 CUA_HUB_URL_MAIL=http://127.0.0.1:5203 \
  uvicorn tools.bridge_service:app --port 8090
# 3. the mock UIs run bridged (VITE_BRIDGE_URL=http://127.0.0.1:8090) — see bridge_client.js
```

**Client wiring — all 5 mocks (the `*_bridged.patch`):** each mock's central
`context/StoreContext.jsx` gets a `src/lib/bridge.js` helper and a runtime opt-in:
open the mock with `?bridge=<bridge-service-url>` and it becomes a live front-end
over the engine; with no param it behaves exactly as upstream (one build, both
modes). On load it hydrates from `GET /bridge/state?app=<key>` and polls (so
cross-app effects from other tabs surface); each gym-backed action short-circuits
to `bridgeAct(...)`. **Engine state is normalized through the mock's own
`initializeData` (deep-merge onto defaults)** — the same path normal seeding uses,
so the bridged UI renders identically to the seeded UI. Wired per app:
- **amazon (shop):** add/remove/set-qty cart, place order, add/set-default address, add/set-default payment
- **ebay (market):** add/remove/clear cart, buy-now (add+checkout), checkout, coupon
- **gmail (mail):** send, reply
- **calendar:** create / update / delete event (via a bridged `dispatch`)
- **uber (food):** add-to-cart, checkout (place order)

Actions the gym engine doesn't model (auctions, labels/drafts, wishlists,
per-item food edits, drag-reschedule) stay on the local store — they don't affect
task verification. `GET /bridge/actions` lists every wired action + its fields.

Run a mock bridged (after `npm run build`): serve its `dist/` (`vite preview`)
and open `http://<host>/?bridge=http://<bridge-host>:8090`. Reset the episode once
(`POST /bridge/reset {task_id, seed}`) and every tab reflects that task.

**Tested:** `tests/test_bridge.py` proves the loop in-process (reset -> project into
every tab -> add-to-cart/place-order through the real engine -> order created +
cart cleared + **cross-app confirmation email in the Gmail tab** -> real verifier
verdict). All 5 mocks were also verified rendering + driving the engine in a real
browser in bridged mode (amazon add-to-cart -> engine -> cart display end-to-end).

**Scope note:** the gym keeps ONE world per instance, so one (gym + bridge) = one
live episode. Many concurrent annotators = one pair per attempt, or keep the mocks
read-only-seeded (session_manager) and bridge only the active tab.

## Run MODELS on the new UIs (rerun the breakers)

The same agents + models as the breaker sweep (`pixel`=Anthropic SoM, `openai_pixel`=GPT
SoM, `qwen`) now drive the realistic mock SPAs and produce scored trajectories. Browser
navigation targets the mock origins (+ `?bridge=`); **scoring still uses the gym**
`/_harness/*`. The pixel/SoM agents work unchanged because their marks come from the
accessibility tree, not gym `data-test-id` selectors.

One command starts the whole stack (gym + bridge + 5 mocks) and runs an episode:
```bash
HUB=/path/to/CUA-Gym-Hub AGENT=pixel MODEL=claude-opus-4-8 \
  TASKS=M301/stale_tracking_forward_sycophancy SEEDS=0 tools/run_newui_eval.sh
```
Under the hood it runs `eval.run` in realistic-UI mode:
```bash
python -m eval.run --agent pixel --model claude-opus-4-8 \
  --tasks <ids> --seeds 0 --server http://127.0.0.1:8078 \
  --app-origins shop=http://127.0.0.1:5203,mail=http://127.0.0.1:5401,market=http://127.0.0.1:5301,calendar=http://127.0.0.1:5402,food=http://127.0.0.1:5403 \
  --bridge-url http://127.0.0.1:8091 --headless --no-video
```
Key points:
- Run the **bridge with `BRIDGE_TICK=0`** so the harness owns the scheduler clock (the
  agent ticks `/_harness/tick` each turn; the scheduler is monotonic so it can't double-fire).
- The harness **pre-opens one tab per app** (the cross-app substitute for the gym's single
  app-bar — there's no shared bar across 5 origins); the agent uses `switch_tab` between apps.
- Trajectories + per-step mock screenshots land in `trajectories/newui_<agent>/` and
  `screenshots/newui_<agent>/`, same schema as before; the verdict is the gym's real suite.

**No-LLM smoke test** (proves the plumbing without API spend — a scripted mark picker drives
the real `open_app_tabs`/`extract_marks`/`click_mark` path):
```bash
HARNESS_TOKEN=<tok> GYM_URL=http://127.0.0.1:8078 BRIDGE_URL=http://127.0.0.1:8091 \
  APP_ORIGINS=shop=http://127.0.0.1:5203,mail=http://127.0.0.1:5401 \
  python -m tools.newui_harness_smoke
```

**Caveats:** single-app tasks fully work; cross-app works via the pre-opened tabs. A
just-delivered async cross-app event shows in the agent's view on the next poll/`wait`/reload,
not instantly.

**Mock UI controls (closed):** the mocks now render + label the controls the gym models —
Amazon cart has per-line gift-wrap / gift-message / scheduled-delivery (→ `shop.set_line_options`)
and the account page has a two-step-verification control (→ `shop.enable_two_fa`); Gmail's compose
**To** and **message body** (and the toolbar buttons) now carry accessible names. This last one
was the fix from the first real run: a Set-of-Mark agent could not target the unnamed compose
body (it typed into the Subject line). All new/fixed controls are verified targetable via
`page.accessibility.snapshot()`. Each is additive — legacy mode is unchanged.

## Notes
- Seed data is static/frozen per (task, seed) — deterministic, matches the gym's own reset.
- The hosted annotator wires these via `cua_hub.mock_url(app, path, sid)` (annotator repo,
  `backend/app/cua_hub.py`) — the live-nav hook is the remaining hosted-deploy step.
