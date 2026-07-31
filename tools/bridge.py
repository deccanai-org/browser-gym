"""Realistic-UI <-> gym-engine bridge.

The realistic mock UIs (CUA-Gym-Hub: Amazon/Gmail/eBay/Google-Calendar/Uber-Eats)
render *seeded* state, but their own React store is a UI shell — it has no gym
semantics (cross-app bus, scheduler, breaker traps, verifiers). This bridge makes
the mocks a **live front-end over the real gym engine**:

    click in the realistic UI
        -> semantic action                       (ACTIONS map, per app)
        -> the gym's OWN http action endpoint     (runs mutation + cross-app hook)
        -> WorldState advances with FULL logic    (bus/scheduler/traps all fire)
        -> re-project the live world -> mock state (seed_to_cuagym.transform_world)
        -> push to every mock tab                  (so cross-app effects show up)
        -> the gym's real verifier suite scores it (/_harness/verify)

The gym keeps ONE world per instance (its global SESSION), so a Bridge instance
is one live episode — exactly the gym's own harness model. Multi-annotator =
one gym instance per attempt (or the tools/session_manager clone model at the
mock layer for read-only seeding).

READ half (engine -> UIs) and the shop WRITE half (UI clicks -> gym actions) are
wired + tested here. The remaining per-app write wiring is just more ACTIONS rows
+ the mock's client calling POST /bridge/act instead of its local store; the
shop rows below are the worked pattern.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from tools.cua_env import seed_sid
from tools.seed_to_cuagym import APP_TO_MOCK, transform_world

# app -> gym URL path prefix (shop is the root); used to land the primary tab.
APP_PREFIX = {"shop": "", "mail": "/mail", "market": "/market",
              "calendar": "/calendar", "food": "/food"}

# --------------------------------------------------------------------------- #
# Semantic action -> the gym's real HTTP endpoint.
#
# Each row is (method, path, form-field names). The bridge fills the form fields
# from the action payload, so a mock click that knows "add_to_cart(product_id,
# quantity)" reaches the SAME endpoint the gym's own product page posts to — i.e.
# mutation + cross-app hook + scheduler, no re-implementation.
#
# `path` may template payload values with {name}; remaining `fields` go in the
# urlencoded body.
# --------------------------------------------------------------------------- #
ACTIONS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # shop (Amazon)
    "shop.login":            ("POST", "/api/login",          ("email", "password")),
    "shop.add_to_cart":      ("POST", "/api/cart/add",       ("product_id", "quantity", "variant_id")),
    # cart-line edits carry the engine's full per-line option set (gift wrap /
    # message, PER-LINE ship-to for split shipping, scheduled delivery) — dropping
    # these silently defangs the gift/split-shipping breaker tasks.
    "shop.update_line":      ("POST", "/api/cart/update",
                              ("line_id", "quantity", "gift_wrap", "gift_message", "ship_to_address_id", "scheduled_delivery")),
    "shop.remove_line":      ("POST", "/api/cart/remove",    ("line_id",)),
    # product-keyed cart edits (the mocks know product ids, not gym line ids;
    # the bridge resolves product_id -> line_id from the live cart, see _LINE_RESOLVED)
    "shop.set_qty":          ("POST", "/api/cart/update",    ("line_id", "quantity")),
    "shop.set_line_options": ("POST", "/api/cart/update",
                              ("line_id", "gift_wrap", "gift_message", "ship_to_address_id", "scheduled_delivery")),
    "shop.remove_product":   ("POST", "/api/cart/remove",    ("line_id",)),
    "shop.apply_promo":      ("POST", "/api/cart/promo",     ("code",)),
    # read/navigation — hitting these gym GET routes logs the view/read signal
    # (view_order_detail / viewed_tracking / view_product / search / ...) that many
    # tasks gate success on. In bridged mode the mock emits these as the agent
    # navigates (see the *_bridged mock patches), so the milestone fires the same
    # way it would from the gym's own pages.
    "shop.view_order":       ("GET",  "/account/orders/{order_id}",       ()),
    "shop.view_tracking":    ("GET",  "/account/orders/{order_id}/track", ()),
    "shop.view_product":     ("GET",  "/product/{product_id}",            ("tab",)),
    "shop.search":           ("GET",  "/search",                          ("q", "category")),
    "shop.view_orders":      ("GET",  "/account/orders",                  ()),
    "shop.view_subscriptions": ("GET", "/account/subscriptions",         ()),
    "shop.view_addresses":   ("GET",  "/account/addresses",              ()),
    "shop.view_payment_methods": ("GET", "/account/payments",            ()),
    "mail.open":             ("GET",  "/mail/message/{email_id}",         ()),
    "mail.set_folder":       ("POST", "/mail/message/{email_id}/folder",  ("folder",)),
    "mail.toggle_label":     ("POST", "/mail/message/{email_id}/label",   ("label",)),
    "shop.place_order":      ("POST", "/api/checkout/place", ("payment_id",)),
    "shop.add_address":      ("POST", "/api/account/addresses",
                              ("label", "full_name", "line1", "line2", "city", "state", "zip", "set_default")),
    "shop.set_default_address": ("POST", "/api/account/addresses/{address_id}/default", ()),
    "shop.add_payment":      ("POST", "/api/account/payments",
                              ("label", "kind", "card_number", "expires", "cvv", "nickname", "set_default")),
    "shop.set_default_payment": ("POST", "/api/account/payments/{payment_id}/default", ()),
    "shop.enable_two_fa":    ("POST", "/api/account/security/two-fa", ("code",)),
    "shop.create_return":    ("POST", "/api/returns",
                              ("order_id", "item_ids", "reason", "refund_method", "notes")),
    "shop.create_subscription": ("POST", "/api/subscriptions",
                              ("product_id", "cadence", "deliveries", "address_id", "payment_id", "quantity", "variant_id")),
    "calendar.view":         ("GET",  "/calendar",                       ()),
    "calendar.view_event":   ("GET",  "/calendar/edit/{event_id}",       ()),
    "shop.cancel_subscription": ("POST", "/api/subscriptions/{subscription_id}/cancel", ()),
    # mail (Gmail)
    "mail.send":             ("POST", "/mail/send",          ("to", "subject", "body", "cc", "bcc")),
    # market (eBay) — a mock listingId IS the gym product_id, so no resolution
    "market.add_to_cart":    ("POST", "/market/cart/add",    ("product_id", "quantity")),
    "market.remove":         ("POST", "/market/cart/remove", ("product_id",)),
    "market.clear_cart":     ("POST", "/market/cart/clear",  ()),
    "market.apply_coupon":   ("POST", "/market/apply-coupon", ("code",)),
    "market.remove_coupon":  ("POST", "/market/remove-coupon", ()),
    "market.checkout":       ("POST", "/market/checkout",    ()),
    # food (Uber Eats)
    "food.add_to_cart":      ("POST", "/food/cart/add",      ("restaurant_id", "dish_id", "quantity")),
    "food.set_qty":          ("POST", "/food/cart/set_qty",  ("dish_id", "quantity")),
    "food.remove_item":      ("POST", "/food/cart/remove",   ("dish_id",)),
    "food.clear_cart":       ("POST", "/food/cart/clear",    ()),
    "food.checkout":         ("POST", "/food/checkout",      ("delivery_note",)),
    # calendar (Google Calendar)
    "calendar.create":       ("POST", "/calendar/create",    ("title", "day", "start", "end")),
    "calendar.update":       ("POST", "/calendar/update",    ("event_id", "title", "start", "end", "day")),
    "calendar.delete":       ("POST", "/calendar/delete",    ("event_id",)),
}

# Actions whose payload is product-keyed but whose gym endpoint wants a cart
# line_id — resolved from the live world just before dispatch.
_LINE_RESOLVED = {"shop.set_qty", "shop.remove_product", "shop.set_line_options"}


def _resolve_line_id(world: dict, product_id: str) -> str | None:
    """The gym cart line_id for a product_id (first match; variants collapse to
    one line in the mock's aggregated view)."""
    for it in ((world.get("shop") or {}).get("cart") or {}).get("items") or []:
        if it.get("product_id") == product_id:
            return it.get("id")
    return None


def _default_addr_pay(world: dict) -> dict:
    """The current user's default address_id + payment_id — used to fill the
    required fields the subscription endpoint needs when a mock click omits them
    (the projected user carries both, so a subscribe click needn't ask again)."""
    shop = world.get("shop") or {}
    user = (shop.get("users") or {}).get(shop.get("current_user_id")) or {}
    out: dict = {}
    addrs = user.get("addresses") or {}
    if addrs:
        out["address_id"] = next((a for a, v in addrs.items() if (v or {}).get("is_default")), None) or next(iter(addrs))
    pays = user.get("payment_methods") or {}
    if pays:
        out["payment_id"] = next((p for p, v in pays.items() if (v or {}).get("is_default")), None) or next(iter(pays))
    return out


def _http(method: str, url: str, *, form: dict | None = None,
          json_body: dict | None = None, headers: dict | None = None,
          timeout: int = 30) -> tuple[int, dict | str]:
    data = None
    headers = dict(headers or {})
    if form is not None:
        # doseq handles list fields (e.g. returns' item_ids) as repeated keys.
        data = urllib.parse.urlencode(
            {k: v for k, v in form.items() if v is not None}, doseq=True).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    # A gym action returns a 303 redirect on success; don't chase it, just note it.
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: ANN002
            return None
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read().decode() or ""
            return r.status, _maybe_json(body)
    except urllib.error.HTTPError as e:
        # 303/302 land here with the redirect handler disabled — that's success.
        body = e.read().decode() if e.fp else ""
        return e.code, _maybe_json(body)


def _maybe_json(body: str) -> dict | str:
    try:
        return json.loads(body)
    except Exception:
        return body


@dataclass
class Bridge:
    """One live episode: a gym instance + the mock tabs it projects into."""
    gym_url: str                                   # e.g. http://127.0.0.1:8000
    mock_map: dict[str, str]                       # app -> mock base url
    harness_token: str = ""                        # X-Harness-Token for /_harness/*
    session: dict[str, str] = field(default_factory=dict)  # app -> mock sid
    task_id: str | None = None
    seed: int = 0
    # When an external harness owns the clock (it ticks /_harness/tick at each
    # turn boundary), disable the bridge's own per-action tick so the scheduler
    # isn't advanced ahead of the agent's observation. Default on for standalone
    # / annotator use (no external ticker).
    tick_enabled: bool = True
    _step: int = 0

    def _hh(self) -> dict:
        """Header for the privileged control plane. The public action surface
        (/api/*) is driven WITHOUT it — exactly as the agent browser does."""
        return {"X-Harness-Token": self.harness_token} if self.harness_token else {}

    # -- lifecycle ----------------------------------------------------------- #
    def reset(self, task_id: str, seed: int = 0) -> dict:
        """Reset the gym engine to (task, seed) and remember it."""
        self.task_id, self.seed, self._step = task_id, seed, 0
        _, meta = _http("POST", f"{self.gym_url}/_harness/reset",
                        json_body={"task_id": task_id, "seed": seed}, headers=self._hh())
        return meta if isinstance(meta, dict) else {}

    def world(self) -> dict[str, Any]:
        """The COMPLETE live world (asdict) from the running engine."""
        _, w = _http("GET", f"{self.gym_url}/_harness/world_full", headers=self._hh())
        return w if isinstance(w, dict) else {}

    # -- read half: engine -> realistic UIs --------------------------------- #
    def project(self, apps: list[str] | None = None) -> dict[str, tuple[str, dict]]:
        """{app: (mock_key, mock_state)} for the LIVE world."""
        return transform_world(self.world(), apps)

    def push(self, apps: list[str] | None = None, *, baseline: bool = False) -> list[str]:
        """Project the live world and write it into each mock tab's session.

        ``baseline`` (once, at reset) writes ``set``, which freezes the hub's
        initial_state. Every later push writes ``set_current``, so the frozen
        baseline survives and each action appends its own mock_state_events row —
        that append-only trail IS the trajectory, and it lives in cua-gym.

        A tab's sid comes from self.session, which start_session fills with the
        attempt UUIDs; the fallback is the task's deterministic seed sid. Both are
        real UUIDs — the hub's Postgres store rejects anything else.
        """
        action = "set" if baseline else "set_current"
        pushed = []
        for app, (_mock, state) in self.project(apps).items():
            base = self.mock_map.get(app)
            if not base:
                continue
            sid = self.session.get(app) or seed_sid(self.task_id or "", self.seed, app)
            self.session.setdefault(app, sid)
            _http("POST", f"{base.rstrip('/')}/post?sid={urllib.parse.quote(sid)}",
                  json_body={"action": action, "state": state})
            pushed.append(app)
        return pushed

    # -- write half: UI click -> gym action -> re-project ------------------- #
    def act(self, action: str, **payload) -> dict:
        """Run a semantic action through the gym's real endpoint, tick the
        scheduler (flush due async cross-app events), re-project, and push.

        Returns {ok, status, world_step, pushed}."""
        if action not in ACTIONS:
            raise KeyError(f"unknown action {action!r}; known: {sorted(ACTIONS)}")
        # Resolve product-keyed cart edits to the gym's line_id before dispatch.
        if action in _LINE_RESOLVED and "line_id" not in payload and payload.get("product_id"):
            lid = _resolve_line_id(self.world(), payload["product_id"])
            if lid is None:
                return {"ok": False, "status": 0, "error": "product not in cart",
                        "world_step": self._step, "pushed": []}
            payload = {**payload, "line_id": lid}
        # Subscriptions require an address + payment the mock click may not carry;
        # fill them from the current user's defaults so the endpoint doesn't 422.
        if action == "shop.create_subscription" and not (payload.get("address_id") and payload.get("payment_id")):
            dflt = _default_addr_pay(self.world())
            payload = {**{k: v for k, v in dflt.items() if not payload.get(k)}, **payload}
        method, path, fields = ACTIONS[action]
        path = path.format(**payload)
        # GET actions (views/navigation) carry their args in the path, no body.
        form = None if method == "GET" else {f: payload.get(f) for f in fields}
        status, _ = _http(method, f"{self.gym_url}{path}", form=form)
        ok = status in (200, 201, 302, 303)
        if self.tick_enabled:
            self.tick()                  # flush any scheduled cross-app effects
        pushed = self.push()             # re-project the advanced world to all tabs
        return {"ok": ok, "status": status, "world_step": self._step, "pushed": pushed}

    def tick(self) -> list[dict]:
        """Advance the deterministic scheduler one step (delivers due async
        cross-app events, exactly as the gym does at each step boundary)."""
        self._step += 1
        _, r = _http("POST", f"{self.gym_url}/_harness/tick",
                     json_body={"step": self._step}, headers=self._hh())
        return (r.get("fired") if isinstance(r, dict) else None) or []

    # -- score: the gym's real verifiers ------------------------------------ #
    def verify(self, url: str = "") -> dict:
        """The REAL milestone verdict for the live world."""
        _, r = _http("POST", f"{self.gym_url}/_harness/verify",
                     json_body={"url": url, "step": self._step}, headers=self._hh())
        return r if isinstance(r, dict) else {}
