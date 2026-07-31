"""Where the CUA-Gym-Hub mocks live.

One place that answers two different questions, because they have two different
answers on the hosted stack:

  api_base(app)  -> the state API we seed and read      (one shared backend)
  ui_base(app)   -> the SPA an annotator/agent opens    (one host PER mock)

Conflating them is a real bug: handing someone an api_base URL opens JSON, not a
storefront.

Environments (CUA_ENV, default "delta"):
  delta   the hosted staging stack — this is production for us
  local   vite dev servers, for offline work only (tools/run_pilot.sh)

Per-app overrides win over everything: CUA_UI_URL_SHOP, CUA_API_URL_SHOP, ...
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import quote

from tools.seed_to_cuagym import APP_TO_MOCK

# The hub stores state in Postgres and rejects any sid that isn't a real UUID, so
# seed sids are UUIDv5: deterministic (the same task resolves to the same sid on
# any machine, in any language) but legal for the `uuid` column.
NS_GYM = uuid.uuid5(uuid.NAMESPACE_URL, "https://gym.deccanexperts.ai/cua-seed/v1")

# Bump to mint a fresh sid family when a projection change means the frozen
# initial_state must be re-cut: `set` will NOT re-freeze a non-NULL initial_state,
# so a new rev is cheaper and safer than repairing every sid in place.
SEED_REV = 1


def seed_sid(task_id: str, seed: int, app: str, rev: int = SEED_REV) -> str:
    return str(uuid.uuid5(NS_GYM, f"{task_id}|{seed}|{app}|r{rev}"))

# The Postgres-backed hub. NOT cua-gym-hub.soulhq.ai — that one is a separate
# file-backed instance that records no events and writes to no database.
DELTA_API_ROOT = "https://cua-gym-hub.delta.soulhq.ai"

# Each mock is served from its own static host; the slug is the mock key without
# the _mock suffix and with underscores hyphenated (google_calendar_mock -> google-calendar).
DELTA_UI_TMPL = "https://cua-hub-{slug}.delta.deccanexperts.ai"

LOCAL_PORTS = {"shop": 5201, "mail": 5203, "market": 5202, "calendar": 5204, "food": 5205}


def _slug(mock_key: str) -> str:
    return mock_key.removesuffix("_mock").replace("_", "-")


def env_name() -> str:
    return os.environ.get("CUA_ENV", "delta").strip().lower()


def api_base(app: str, env: str | None = None) -> str:
    """State-API base for an app, i.e. the thing you POST /post?sid= to."""
    override = os.environ.get(f"CUA_API_URL_{app.upper()}")
    if override:
        return override.rstrip("/")
    mock = APP_TO_MOCK[app]
    if (env or env_name()) == "local":
        return f"http://127.0.0.1:{LOCAL_PORTS[app]}"
    root = os.environ.get("CUA_API_ROOT", DELTA_API_ROOT).rstrip("/")
    return f"{root}/api/{mock}"


def ui_base(app: str, env: str | None = None) -> str:
    """SPA base for an app — what a human or a browser agent actually opens."""
    override = os.environ.get(f"CUA_UI_URL_{app.upper()}")
    if override:
        return override.rstrip("/")
    if (env or env_name()) == "local":
        return f"http://127.0.0.1:{LOCAL_PORTS[app]}"
    return DELTA_UI_TMPL.format(slug=_slug(APP_TO_MOCK[app]))


def ui_url(app: str, sid: str, path: str = "/", env: str | None = None,
           bridge: str | None = None, session: str | None = None) -> str:
    """Openable URL for (app, sid).

    The query must precede any hash — gmail routes on the fragment, and a sid
    parked after '#' never reaches getSessionId().

    Pass ``bridge`` to put the tab in bridged mode, where its clicks drive the
    real gym engine (cross-app bus included) instead of the mock's local store.
    ``session`` picks which episode: every tab of one session must carry the same
    value or their cross-app effects land in different engines.
    """
    base = ui_base(app, env)
    path = path or "/"
    if not path.startswith("/"):
        path = "/" + path
    frag = ""
    if "#" in path:
        path, frag = path.split("#", 1)
        frag = "#" + frag
    q = [f"sid={sid}"]
    if bridge:
        q.append(f"bridge={quote(bridge.rstrip('/'), safe='')}")
    if session:
        q.append(f"session={quote(session, safe='')}")
    sep = "&" if "?" in path else "?"
    return f"{base}{path}{sep}{'&'.join(q)}{frag}"


def api_map(env: str | None = None) -> dict[str, str]:
    return {app: api_base(app, env) for app in APP_TO_MOCK}


def ui_map(env: str | None = None) -> dict[str, str]:
    return {app: ui_base(app, env) for app in APP_TO_MOCK}
