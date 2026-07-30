# Realistic-UI pilot — run the gym on the CUA-Gym-Hub UIs

The gym serves the **realistic mock UIs** (Amazon / Gmail / eBay / Google Calendar /
Uber Eats) seeded from its own tasks. The UIs come from XLang's public
[CUA-Gym-Hub](https://github.com/xlang-ai/CUA-Gym-Hub); we push each task's seed
world into them via their state API. No cua-gym DB or Kashyap dependency.

## App mapping

| Gym app | Realistic UI | mock key | port |
|---|---|---|---|
| shop (ShopGym) | Amazon | amazon_mock | 5201 |
| market (ValueMart) | eBay | ebay_mock | 5202 |
| mail (ShopMail) | Gmail | gmail_mock | 5203 |
| calendar | Google Calendar | google_calendar_mock | 5204 |
| food | Uber Eats | uber_eats_mock | 5205 |

## One-time setup

```bash
# 1. clone the UIs next to the gym repo
git clone https://github.com/xlang-ai/CUA-Gym-Hub.git

# 2. apply our uber_eats fix (that mock ships internally broken — two parallel
#    context systems, cross-wired; the patch commits it to the working AppContext
#    app and adds the missing Checkout page)
git -C CUA-Gym-Hub apply "<gym>/tools/patches/uber_eats_mock_systemB.patch"

# 3. install each mock's deps (npm cache must be writable; use a local one if ~/.npm is locked)
for a in amazon_mock ebay_mock gmail_mock google_calendar_mock uber_eats_mock; do
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

## Notes
- Seed data is static/frozen per (task, seed) — deterministic, matches the gym's own reset.
- The hosted annotator wires these via `cua_hub.mock_url(app, path, sid)` (annotator repo,
  `backend/app/cua_hub.py`) — the live-nav hook is the remaining hosted-deploy step.
