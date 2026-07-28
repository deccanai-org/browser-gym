"""FastAPI server — multi-page e-commerce app + harness endpoints.

Two route families:

  Pages (HTML responses, what the browser agent renders + clicks):
    GET  /                           home / featured products
    GET  /search                     search results with filters
    GET  /product/{product_id}       product detail page (variants, tabs)
    GET  /cart                       cart with line-level options
    GET  /checkout/address           checkout step 1: pick address
    GET  /checkout/payment           checkout step 2: pick payment
    GET  /checkout/review            checkout step 3: review (coupon) + place
    GET  /order/{order_id}           order confirmation page
    GET  /login                      login form
    GET  /account                    account hub
    GET  /account/addresses          manage addresses
    GET  /account/payments           manage payment methods
    GET  /account/orders             order history
    GET  /account/orders/{order_id}  order detail with tracking modal trigger
    GET  /account/returns            list of returns
    GET  /account/returns/new        initiate-return form
    GET  /account/security           2FA / security
    GET  /account/subscriptions      subscriptions list / confirmation

  Form POST endpoints (browser submits land here, mutations applied):
    POST /api/login
    POST /api/logout
    POST /api/cart/add
    POST /api/cart/update
    POST /api/cart/remove
    POST /api/cart/promo
    POST /api/checkout/place
    POST /api/account/addresses
    POST /api/account/addresses/{address_id}/default
    POST /api/account/payments
    POST /api/account/payments/{payment_id}/default
    POST /api/account/security/two-fa
    POST /api/returns
    POST /api/subscriptions

  Harness-only (for the verifier; not used by the UI):
    POST /_harness/reset             reset gym for (task_id, seed)
    GET  /_harness/state             dump GymState
    GET  /_harness/snapshot          minimal snapshot (URL-agnostic)
    POST /_harness/verify            evaluate the suite given current URL

The browser agent uses the same routes a human would. Forms are
standard HTML form submissions with redirects — no JavaScript app
required (though the UI uses fetch for some nicer interactions).
"""

from __future__ import annotations

import copy
import hmac
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    Cookie, FastAPI, Form, HTTPException, Query, Request, Response,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from server import mutations, verifiers
from server.state import GymState, flash, log_action
from server.tasks import TASKS, make_task, START_PATHS
from server.apps.world import WorldState
from server.apps import statecodec
from server.apps.mail.state import make_mailstate
from server.apps.mail import routes as mail_routes
from server.apps.food.state import make_foodstate
from server.apps.food import routes as food_routes
from server.apps.calendar.state import make_calendarstate
from server.apps.calendar import routes as calendar_routes
from server.apps.market.state import make_marketstate
from server.apps.market import routes as market_routes
from server.apps import wiring as apps_wiring
from server.apps import shop_hooks
from server.apps import bus
from server.apps import scheduler
from harness.auth import HARNESS_TOKEN_HEADER, get_harness_token


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = REPO_ROOT / "ui"

app = FastAPI(
    title="ecommerce-browser-gym",
    version="0.1.0",
    description=(
        "Production-grade browser-agent RL gym for e-commerce. Agents "
        "drive a real Chromium browser through a multi-page e-commerce "
        "site; a per-step milestone verifier grades progress."
    ),
)
app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")
templates = Jinja2Templates(directory=UI_DIR / "pages")


# --------------------------------------------------------------------------- #
# Single-tenant session
# --------------------------------------------------------------------------- #

class Session:
    initial: GymState | None = None
    current: GymState | None = None
    suite: verifiers.TaskSuite | None = None
    # Multi-app wrapper. ``world.shop`` IS ``current`` (same object), so every
    # existing shop mutation is reflected in the world with zero extra wiring;
    # the new apps (mail, +food/calendar) own their own isolated stores.
    world: "WorldState | None" = None
    initial_world: "WorldState | None" = None    # snapshot for cross-app verifiers
    # Named UI perturbation(s) for this episode (comma-separated, e.g.
    # "modal_interruption,decoy_clutter"). Deterministic + fully functional —
    # every button still works; the page is just harder to perceive/sequence.
    # Recorded in trajectory metadata so failures can be sliced by variant.
    ui_variant: str = "normal"


SESSION = Session()


@app.middleware("http")
async def authenticate_harness_control_plane(request: Request, call_next):
    """Keep privileged harness routes unavailable to the agent browser.

    Trusted control clients receive the per-run token through their process
    environment. Browser contexts receive no token or extra HTTP headers.
    """
    if request.url.path.startswith("/_harness"):
        supplied = request.headers.get(HARNESS_TOKEN_HEADER, "")
        try:
            expected = get_harness_token()
        except RuntimeError:
            return JSONResponse(
                {"detail": "Harness control plane is unavailable"},
                status_code=503,
            )
        if not supplied or not hmac.compare_digest(supplied, expected):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# --------------------------------------------------------------------------- #
# Global exception handlers — make 404s recoverable for the agent
# --------------------------------------------------------------------------- #

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """When a page doesn't exist, render an HTML recovery page instead of
    JSON. This is critical for agents: they can READ HTML and find the
    link back home, but a JSON 404 is a dead-end."""
    if exc.status_code == 404:
        # Don't 404-render for harness or API endpoints — they should
        # stay as JSON so the harness/agent code can detect failure.
        path = request.url.path
        if path.startswith("/_harness") or path.startswith("/api"):
            return JSONResponse(
                {"detail": exc.detail or "Not Found"},
                status_code=exc.status_code,
            )
        try:
            return templates.TemplateResponse(
                request, "not_found.html",
                _ctx(request, attempted_path=path,
                     detail=exc.detail or "Page not found"),
                status_code=404,
            )
        except Exception:
            # If template rendering itself fails, fall back to JSON.
            return JSONResponse(
                {"detail": exc.detail or "Not Found"},
                status_code=exc.status_code,
            )
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code,
    )


def _state() -> GymState:
    if SESSION.current is None:
        # Default to the easiest task so the UI doesn't crash if a human
        # opens the site without hitting reset.
        _reset_inline("A1/buy_wireless_mouse", 0)
    assert SESSION.current is not None
    return SESSION.current


def _reset_inline(task_id: str, seed: int, ui: str = "normal") -> None:
    # The seed baseline comes from seed.db when SEEDDB_MODE is on and the pool
    # covers this (task, seed); otherwise from the factory (the default, and the
    # fallback). Imported lazily so the seed-db layer never loads at import time.
    from server.seeddb.runtime import seed_source
    built = seed_source(task_id, seed)
    # Cross-app (category M) factories return a fully-built WorldState;
    # single-app factories return a GymState we wrap with default stores.
    if isinstance(built, WorldState):
        world = built
        if world.mail is None:
            world.mail = make_mailstate(seed)
        if world.food is None:
            world.food = make_foodstate(seed)
        if world.calendar is None:
            world.calendar = make_calendarstate(seed)
        if world.market is None:
            world.market = make_marketstate(seed)
    else:
        world = WorldState(
            shop=built, mail=make_mailstate(seed), food=make_foodstate(seed),
            calendar=make_calendarstate(seed), market=make_marketstate(seed),
        )
    shop = world.shop
    # ``current`` IS ``world.shop`` (same object), so shop routes (which use
    # ``_state()``) and the world stay in sync automatically.
    SESSION.current = shop
    SESSION.initial = copy.deepcopy(shop)
    SESSION.world = world
    SESSION.initial_world = copy.deepcopy(world)
    SESSION.suite = verifiers.build_suite(task_id)
    SESSION.ui_variant = ui or "normal"


def _world() -> WorldState:
    if SESSION.world is None:
        _reset_inline("A1/buy_wireless_mouse", 0)
    assert SESSION.world is not None
    return SESSION.world


# --------------------------------------------------------------------------- #
# Common context for templates
# --------------------------------------------------------------------------- #

def _ctx(request: Request, **extra: Any) -> dict[str, Any]:
    s = _state()
    user = None
    if s.current_user_id:
        user = s.users[s.current_user_id]
    flashes = list(s.flash_messages)
    s.flash_messages.clear()
    cart_count = sum(i.quantity for i in s.cart.items)
    mail_unread = 0
    if SESSION.world is not None and SESSION.world.mail is not None:
        mail_unread = SESSION.world.mail.unread_count()
    return {
        "request": request, "state": s, "user": user,
        "task_brief": s.task_brief,
        "task_id": s.task_id,
        "task_difficulty": s.task_difficulty,
        "task_category": s.task_category,
        "cart_count": cart_count,
        "flashes": flashes,
        # Multi-app chrome (app-switcher bar). Routes for other apps pass
        # active_app="mail" etc. via **extra, which overrides this default.
        "active_app": "shop",
        "mail_unread": mail_unread,
        "ui_variant": SESSION.ui_variant,
        **extra,
    }


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    s = _state()
    # Show a diverse set across categories so the featured rail is varied.
    featured = sorted(
        s.products.values(), key=lambda p: -p.rating,
    )[:12]
    return templates.TemplateResponse(request, "home.html", _ctx(request, featured=featured))


@app.get("/bulk", response_class=HTMLResponse)
async def bulk_order(request: Request):
    """Dense 'Quick Order' grid — every electronics item as a small tile with a
    generically-labelled Add button. The button-density + small targets are a
    deliberate perception stress (used by M12 + the small_targets variant)."""
    s = _state()
    prods = sorted(
        (p for p in s.products.values() if p.category == "electronics"),
        key=lambda p: p.name,
    )
    return templates.TemplateResponse(request, "bulk.html", _ctx(request, products=prods))


# --- Sort helpers for search/category pages --------------------------------
def _sort_products(items: list, sort: str) -> list:
    if sort == "price_asc":
        return sorted(items, key=lambda p: p.base_price)
    if sort == "price_desc":
        return sorted(items, key=lambda p: -p.base_price)
    if sort == "rating":
        return sorted(items, key=lambda p: -p.rating)
    if sort == "reviews":
        return sorted(items, key=lambda p: -p.review_count)
    # default: featured (rating desc with mild stock bias)
    return sorted(items, key=lambda p: (-p.rating, -p.stock))


@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = "",
    category: str = "",
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    in_stock: bool = False,
    sort: str = "featured",
):
    s = _state()
    products = list(s.products.values())
    q_low = (q or "").lower()
    results = []
    for p in products:
        if q_low and q_low not in p.name.lower() \
                and q_low not in p.brand.lower() \
                and not any(q_low in t.lower() for t in p.tags):
            continue
        if category and p.category != category:
            continue
        if max_price is not None and p.base_price > max_price:
            continue
        if min_rating is not None and p.rating < min_rating:
            continue
        if in_stock and p.stock <= 0:
            continue
        results.append(p)
    results = _sort_products(results, sort)
    log_action(s, "search", q=q, category=category,
               max_price=max_price, min_rating=min_rating,
               in_stock=in_stock, sort=sort, n_results=len(results))
    return templates.TemplateResponse(
        request, "search.html",
        _ctx(request, results=results, q=q, category=category,
             max_price=max_price, min_rating=min_rating,
             in_stock=in_stock, sort=sort),
    )


# Subcategory taxonomy — a product belongs to a subcategory if any of its
# tags intersect the subcategory's tag set. Lets the agent drill
# category -> subcategory -> product, the way a real shopper browses,
# instead of jumping straight to the search bar.
SUBCATEGORIES: dict[str, dict[str, set[str]]] = {
    "electronics": {
        "laptops":     {"laptop"},
        "mice":        {"mouse"},
        "keyboards":   {"keyboard"},
        "monitors":    {"monitor"},
        "accessories": {"charger", "usb-c", "watch", "fitness", "trackpad"},
    },
    "audio": {
        "headphones": {"headphones"},
        "speakers":   {"speaker"},
    },
    "books": {
        "fiction":    {"fiction", "sci-fi"},
        "nonfiction": {"nonfiction", "history", "biography", "cookbook"},
    },
    "clothing": {
        "tops":      {"tshirt", "polo", "tank"},
        "outerwear": {"hoodie", "jacket"},
    },
    "home": {
        "lighting": {"lamp"},
        "kitchen":  {"mug"},
        "decor":    {"candle"},
    },
    "pet": {
        "food":   {"dog"},
        "treats": {"treats"},
    },
    "office": {
        "displays":  {"display"},
        "furniture": {"chair"},
    },
}


def _in_subcategory(product: Any, cat: str, sub: str) -> bool:
    tagset = SUBCATEGORIES.get(cat, {}).get(sub, set())
    if not tagset:
        return False
    return bool(set(product.tags) & tagset)


@app.get("/category/{cat}", response_class=HTMLResponse)
async def category_page(
    request: Request, cat: str,
    sub: str = "",
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    in_stock: bool = False,
    sort: str = "featured",
):
    """Category landing page — same backend as /search but with a
    category-specific hero, breadcrumbs, and subcategory drill-down.
    Browsing via the mega-menu lands here. With ``?sub=`` the page
    narrows to one subcategory (laptops, headphones, keyboards, ...),
    the way a real shopper drills down a taxonomy."""
    s = _state()
    products = list(s.products.values())
    results = [p for p in products if p.category == cat]
    if sub:
        results = [p for p in results if _in_subcategory(p, cat, sub)]
    if max_price is not None:
        results = [p for p in results if p.base_price <= max_price]
    if min_rating is not None:
        results = [p for p in results if p.rating >= min_rating]
    if in_stock:
        results = [p for p in results if p.stock > 0]
    results = _sort_products(results, sort)
    # Log distinct events for category vs subcategory navigation so
    # taxonomy-navigation verifiers can confirm the agent drilled down
    # rather than searching.
    if sub:
        log_action(s, "view_subcategory", category=cat, sub=sub,
                   n_results=len(results))
    else:
        log_action(s, "view_category", category=cat,
                   max_price=max_price, min_rating=min_rating,
                   in_stock=in_stock, sort=sort, n_results=len(results))
    subcats = sorted(SUBCATEGORIES.get(cat, {}).keys())
    return templates.TemplateResponse(
        request, "category.html",
        _ctx(request, results=results, cat=cat, sub=sub, subcats=subcats,
             max_price=max_price, min_rating=min_rating,
             in_stock=in_stock, sort=sort),
    )


@app.get("/deals", response_class=HTMLResponse)
async def deals_page(request: Request):
    """Today's deals page — highlights the discounted items."""
    s = _state()
    # Pick lower-priced, high-rated items as the "deals" set.
    deals = sorted(
        [p for p in s.products.values() if p.stock > 0],
        key=lambda p: (-p.rating, p.base_price),
    )[:12]
    log_action(s, "view_deals")
    return templates.TemplateResponse(
        request, "deals.html",
        _ctx(request, deals=deals),
    )


# --------------------------------------------------------------------------- #
# Safety-net alias routes — catch URL patterns agents commonly hallucinate
# and redirect to the canonical route. Real e-commerce sites do this; it
# also prevents the agent from getting stuck on a 404 mid-episode.
# --------------------------------------------------------------------------- #

@app.get("/products", include_in_schema=False)
@app.get("/products/", include_in_schema=False)
@app.get("/items", include_in_schema=False)
@app.get("/shop", include_in_schema=False)
@app.get("/store", include_in_schema=False)
@app.get("/catalog", include_in_schema=False)
@app.get("/browse", include_in_schema=False)
async def alias_to_search():
    """Catch /products, /items, /shop etc. — agent meant /search."""
    return RedirectResponse("/search", 303)


@app.get("/products/{product_id}", include_in_schema=False)
@app.get("/item/{product_id}", include_in_schema=False)
@app.get("/p/{product_id}", include_in_schema=False)
async def alias_product_detail(product_id: str):
    """Catch /products/{id} → /product/{id} (singular vs plural)."""
    return RedirectResponse(f"/product/{product_id}", 303)


@app.get("/checkout", include_in_schema=False)
async def alias_checkout():
    """Catch bare /checkout — route based on cart state."""
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    if not s.cart.items:
        return RedirectResponse("/cart", 303)
    return RedirectResponse("/checkout/address", 303)


@app.get("/orders", include_in_schema=False)
@app.get("/my-orders", include_in_schema=False)
async def alias_orders():
    return RedirectResponse("/account/orders", 303)


@app.get("/returns", include_in_schema=False)
async def alias_returns():
    return RedirectResponse("/account/returns", 303)


@app.get("/subscriptions", include_in_schema=False)
@app.get("/subs", include_in_schema=False)
async def alias_subscriptions():
    return RedirectResponse("/account/subscriptions", 303)


@app.get("/profile", include_in_schema=False)
@app.get("/me", include_in_schema=False)
async def alias_account():
    return RedirectResponse("/account", 303)


@app.get("/signin", include_in_schema=False)
@app.get("/sign-in", include_in_schema=False)
@app.get("/log-in", include_in_schema=False)
async def alias_login():
    return RedirectResponse("/login", 303)


# Form POST endpoints sometimes get GETted by hallucinating agents.
# Redirect them to the page they belong on.
@app.get("/cart/add", include_in_schema=False)
@app.get("/cart/add/{sku}", include_in_schema=False)
@app.get("/api/cart/add", include_in_schema=False)
async def alias_cart_add(sku: str = ""):
    """The agent tried to GET /cart/add/{sku}. The real flow is:
    click the [data-test-id='btn-add-to-cart'] button on a product page."""
    s = _state()
    # If sku looks like a product_id, send them to the product page
    if sku and sku in s.products:
        return RedirectResponse(f"/product/{sku}", 303)
    return RedirectResponse("/search", 303)


@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_page(request: Request, product_id: str,
                       tab: str = "description"):
    s = _state()
    p = s.products.get(product_id)
    if p is None:
        # Smart 404 recovery — try to find similar products by ID or
        # name so a hallucinating agent gets a useful suggestion instead
        # of a dead end. Same idea Amazon's "Did you mean..." pages use.
        import difflib
        candidates = list(s.products.keys())
        # Fuzzy by ID
        id_matches = difflib.get_close_matches(
            product_id.lower(), [c.lower() for c in candidates], n=5, cutoff=0.4,
        )
        # Also search by tokens in product names (e.g. "shirt cotton" → tshirt)
        query_tokens = set(
            tok for tok in product_id.replace("p_", "").lower().split("_")
            if len(tok) > 2
        )
        name_matches: list[str] = []
        for pid, prod in s.products.items():
            name_lower = prod.name.lower()
            if any(t in name_lower for t in query_tokens):
                name_matches.append(pid)
        # Dedupe, preserve order
        suggestions: list[str] = []
        for m in id_matches + name_matches:
            real_id = next((c for c in candidates if c.lower() == m), m)
            if real_id in s.products and real_id not in suggestions:
                suggestions.append(real_id)
        suggested_products = [s.products[sid] for sid in suggestions[:6]]
        return templates.TemplateResponse(
            request, "product_not_found.html",
            _ctx(request,
                 attempted_id=product_id,
                 suggested_products=suggested_products),
            status_code=404,
        )
    log_action(s, "view_product", product_id=product_id, tab=tab)
    return templates.TemplateResponse(request, "product.html", _ctx(request, p=p, tab=tab))


@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    return templates.TemplateResponse(request, "cart.html", _ctx(request))


@app.get("/checkout/address", response_class=HTMLResponse)
async def checkout_address(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    if not s.cart.items:
        return RedirectResponse("/cart", 303)
    log_action(s, "checkout_step", step="address")
    # Cross-app trigger: the agent has COMMITTED to a ShopGym purchase. Some
    # tasks (M18 async coupon-flip) schedule an event relative to this moment.
    if SESSION.world is not None:
        shop_hooks.emit_shop_checkout_reached(SESSION.world)
    return templates.TemplateResponse(request, "checkout_address.html", _ctx(request))


@app.get("/checkout/payment", response_class=HTMLResponse)
async def checkout_payment(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    log_action(s, "checkout_step", step="payment")
    return templates.TemplateResponse(request, "checkout_payment.html", _ctx(request))


@app.get("/checkout/review", response_class=HTMLResponse)
async def checkout_review(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    log_action(s, "checkout_step", step="review")
    return templates.TemplateResponse(request, "checkout_review.html", _ctx(request))


@app.get("/order/{order_id}", response_class=HTMLResponse)
async def order_confirmation(request: Request, order_id: str):
    s = _state()
    o = s.orders.get(order_id)
    if o is None:
        raise HTTPException(404, "order not found")
    return templates.TemplateResponse(request, "order_confirmation.html", _ctx(request, order=o))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", _ctx(request))


@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    return templates.TemplateResponse(request, "account_hub.html", _ctx(request))


@app.get("/account/addresses", response_class=HTMLResponse)
async def account_addresses(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    # Log the view so a verifier can credit the safe "checked the real saved addresses"
    # path (e.g. M67, where a spoofed email claims the default address changed).
    log_action(s, "view_addresses")
    return templates.TemplateResponse(request, "account_addresses.html", _ctx(request))


@app.get("/account/payments", response_class=HTMLResponse)
async def account_payments(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    # Log the view so a verifier can credit the safe "checked the card's validity" path
    # (e.g. M61, where the default card is expired and the agent should notice here).
    log_action(s, "view_payment_methods")
    return templates.TemplateResponse(request, "account_payments.html", _ctx(request))


@app.get("/account/orders", response_class=HTMLResponse)
async def account_orders(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    user_orders = [o for o in s.orders.values()
                   if o.user_id == s.current_user_id]
    # Log the list view so verifiers can confirm (state-based, robust to where the
    # agent ends up) that the agent actually looked at its orders.
    log_action(s, "view_orders")
    return templates.TemplateResponse(request, "account_orders.html", _ctx(request, orders=user_orders))


@app.get("/account/orders/{order_id}", response_class=HTMLResponse)
async def account_order_detail(request: Request, order_id: str):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    o = s.orders.get(order_id)
    if o is None or o.user_id != s.current_user_id:
        raise HTTPException(404, "order not found")
    log_action(s, "view_order_detail", order_id=order_id)
    return templates.TemplateResponse(request, "account_order_detail.html", _ctx(request, order=o))


@app.get("/account/orders/{order_id}/track", response_class=HTMLResponse)
async def view_tracking(request: Request, order_id: str):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    o = s.orders.get(order_id)
    if o is None or o.user_id != s.current_user_id:
        raise HTTPException(404, "order not found")
    log_action(s, "viewed_tracking", order_id=order_id)
    return templates.TemplateResponse(request, "tracking_modal.html", _ctx(request, order=o))


@app.get("/account/returns", response_class=HTMLResponse)
async def account_returns(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    user_returns = [r for r in s.returns.values()
                    if r.user_id == s.current_user_id]
    return templates.TemplateResponse(request, "account_returns.html", _ctx(request, returns=user_returns))


@app.get("/account/returns/new", response_class=HTMLResponse)
async def new_return(request: Request, order_id: str = Query(...)):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    o = s.orders.get(order_id)
    if o is None or o.user_id != s.current_user_id:
        raise HTTPException(404, "order not found")
    # Log the intent to return THIS specific order, so verifiers can see a blind
    # return attempt even when the agent never completes the (multi-field) form.
    log_action(s, "view_return_form", order_id=order_id)
    return templates.TemplateResponse(request, "return_form.html", _ctx(request, order=o))


@app.get("/account/security", response_class=HTMLResponse)
async def account_security(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    return templates.TemplateResponse(request, "account_security.html", _ctx(request))


@app.get("/account/subscriptions", response_class=HTMLResponse)
async def account_subscriptions(request: Request):
    s = _state()
    if s.current_user_id is None:
        return RedirectResponse("/login", 303)
    log_action(s, "view_subscriptions")
    user_subs = [sub for sub in s.subscriptions.values()
                 if sub.user_id == s.current_user_id]
    return templates.TemplateResponse(request, "account_subscriptions.html", _ctx(request, subscriptions=user_subs))


# --------------------------------------------------------------------------- #
# Form POST endpoints
# --------------------------------------------------------------------------- #

@app.post("/api/login")
async def api_login(email: str = Form(""), password: str = Form("")):
    s = _state()
    r = mutations.login(s, email, password)
    if r.get("ok"):
        return RedirectResponse("/account", 303)
    return RedirectResponse("/login?err=1", 303)


@app.post("/api/logout")
async def api_logout():
    s = _state()
    mutations.logout(s)
    return RedirectResponse("/", 303)


@app.post("/api/cart/add")
async def api_add_to_cart(
    product_id: str = Form(...),
    quantity: int = Form(1),
    variant_id: Optional[str] = Form(None),
    redirect: Optional[str] = Form(None),
):
    s = _state()
    result = mutations.add_to_cart(
        s, product_id=product_id,
        quantity=quantity, variant_id=variant_id,
    )
    # If add-to-cart failed (e.g. variant required), stay on the
    # product page so the agent sees both the error flash AND the
    # variant picker. Don't honor the form's `redirect` field in this
    # case — that would silently land the agent on /cart with only a
    # toast that's easy to miss in a heavy observation.
    if not result.get("ok"):
        return RedirectResponse(f"/product/{product_id}", 303)
    return RedirectResponse(redirect or f"/product/{product_id}", 303)


@app.post("/api/cart/update")
async def api_update_line(
    line_id: str = Form(...),
    quantity: Optional[int] = Form(None),
    gift_wrap: Optional[bool] = Form(None),
    gift_message: Optional[str] = Form(None),
    ship_to_address_id: Optional[str] = Form(None),
    scheduled_delivery: Optional[str] = Form(None),
):
    s = _state()
    mutations.update_line(
        s, line_id=line_id, quantity=quantity,
        gift_wrap=gift_wrap, gift_message=gift_message,
        ship_to_address_id=ship_to_address_id,
        scheduled_delivery=(scheduled_delivery or None),   # blank date input = no change
    )
    return RedirectResponse("/cart", 303)


@app.post("/api/cart/remove")
async def api_remove_line(line_id: str = Form(...)):
    s = _state()
    mutations.remove_line(s, line_id=line_id)
    return RedirectResponse("/cart", 303)


@app.post("/api/cart/promo")
async def api_apply_promo(
    code: str = Form(""),
    action: str = Form("apply"),
):
    s = _state()
    if action == "remove":
        mutations.remove_promo(s)
    else:
        mutations.apply_promo(s, code=code)
    return RedirectResponse("/checkout/review", 303)


@app.post("/api/checkout/place")
async def api_place_order(payment_id: str = Form(...)):
    s = _state()
    r = mutations.place_order(s, payment_id=payment_id)
    if r.get("ok"):
        # Cross-app effect: a confirmation email (with the tracking link)
        # lands in Mail. Harmless for single-app tasks (they ignore mail).
        shop_hooks.emit_shop_order_placed(_world(), r["order_id"])
        return RedirectResponse(f"/order/{r['order_id']}", 303)
    return RedirectResponse("/checkout/review?err=1", 303)


@app.post("/api/account/addresses")
async def api_add_address(
    label: str = Form(...),
    full_name: str = Form(...),
    line1: str = Form(...),
    line2: str = Form(""),
    city: str = Form(...),
    state: str = Form(...),
    zip: str = Form(...),
    set_default: bool = Form(False),
):
    s = _state()
    mutations.add_address(s, label=label, full_name=full_name,
                          line1=line1, line2=line2, city=city,
                          st=state, zip_=zip, set_default=set_default)
    return RedirectResponse("/account/addresses", 303)


@app.post("/api/account/addresses/{address_id}/default")
async def api_set_default_address(address_id: str):
    s = _state()
    mutations.set_default_address(s, address_id=address_id)
    return RedirectResponse("/account/addresses", 303)


@app.post("/api/account/payments")
async def api_add_payment(
    label: str = Form(""),
    kind: str = Form("credit_card"),
    card_number: str = Form(""),
    expires: str = Form(""),
    cvv: str = Form(""),
    nickname: str = Form(""),
    set_default: bool = Form(False),
):
    s = _state()
    mutations.add_payment_method(
        s, label=label, kind=kind, card_number=card_number,
        expires=expires, cvv=cvv, nickname=nickname,
        set_default=set_default,
    )
    return RedirectResponse("/account/payments", 303)


@app.post("/api/account/payments/{payment_id}/default")
async def api_set_default_payment(payment_id: str):
    s = _state()
    mutations.set_default_payment(s, payment_id=payment_id)
    return RedirectResponse("/account/payments", 303)


@app.post("/api/account/security/two-fa")
async def api_enable_two_fa(code: str = Form(...)):
    s = _state()
    mutations.enable_two_fa(s, code=code)
    return RedirectResponse("/account/security", 303)


@app.post("/api/returns")
async def api_create_return(
    order_id: str = Form(...),
    item_ids: list[str] = Form(...),
    reason: str = Form(...),
    refund_method: str = Form(...),
    notes: str = Form(""),
):
    s = _state()
    r = mutations.initiate_return(
        s, order_id=order_id, item_ids=item_ids,
        reason=reason, refund_method=refund_method, notes=notes,
    )
    # Cross-app TRIGGER: a successfully-filed return is what a scheduled async
    # "refund approved" email resolves its due step against (server.apps.
    # scheduler). Emits a ReturnFiled WorldEvent into the log; no subscriber.
    if r.get("ok") and SESSION.world is not None:
        shop_hooks.emit_return_filed(
            SESSION.world, return_id=r.get("return_id", ""), order_id=order_id)
    return RedirectResponse("/account/returns", 303)


@app.post("/api/subscriptions")
async def api_create_subscription(
    product_id: str = Form(...),
    cadence: str = Form("weekly"),
    deliveries: int = Form(4),
    address_id: str = Form(...),
    payment_id: str = Form(...),
    quantity: int = Form(1),
    variant_id: Optional[str] = Form(None),
):
    s = _state()
    r = mutations.create_subscription(
        s, product_id=product_id, cadence=cadence,
        deliveries=deliveries, address_id=address_id,
        payment_id=payment_id, quantity=quantity, variant_id=variant_id,
    )
    return RedirectResponse("/account/subscriptions", 303)


@app.post("/api/subscriptions/{subscription_id}/cancel")
async def api_cancel_subscription(subscription_id: str):
    """Cancel an active subscription. Idempotent — cancelling an
    already-cancelled subscription returns ok without erroring."""
    s = _state()
    mutations.cancel_subscription(s, subscription_id=subscription_id)
    return RedirectResponse("/account/subscriptions", 303)


# --------------------------------------------------------------------------- #
# Harness endpoints
# --------------------------------------------------------------------------- #

class HarnessResetRequest(BaseModel):
    task_id: str
    seed: int = 0
    ui: str = "normal"
    brief: str | None = None  # annotator prompt edit → render this brief in-page


class HarnessVerifyRequest(BaseModel):
    url: str = ""
    step: int = 0


@app.get("/_harness/tasks")
def harness_tasks() -> dict[str, list[str]]:
    return {"tasks": list(TASKS)}


@app.post("/_harness/reset")
def harness_reset(req: HarnessResetRequest) -> dict[str, Any]:
    if req.task_id not in TASKS:
        raise HTTPException(404, "unknown task")
    _reset_inline(req.task_id, req.seed, ui=req.ui)
    s = _state()
    # Annotator prompt edit: render the NEW brief in-page (banner + screenshots),
    # not just what the agent is told — so the reviewed run is self-consistent.
    if req.brief:
        s.task_brief = req.brief
    return {"ok": True, "task_id": s.task_id, "seed": s.seed,
            "task_brief": s.task_brief,
            "task_category": s.task_category,
            "task_difficulty": s.task_difficulty,
            "ui_variant": SESSION.ui_variant,
            "start_path": START_PATHS.get(s.task_id, "/"),
            "current_user_id": s.current_user_id}


class HarnessLoadStateRequest(BaseModel):
    task_id: str
    seed: int = 0
    ui: str = "normal"
    state: dict = {}
    step: int | None = None


@app.post("/_harness/load_state")
def harness_load_state(req: HarnessLoadStateRequest) -> dict[str, Any]:
    """Resume from a corrected mid-episode state. Resets to the seed baseline —
    rebuilding every catalog and keeping SESSION.initial / initial_world pristine
    so delta & cross-app verifiers still compare against the seed — then OVERLAYS
    the supplied mutable slice (cart / orders / account / sub-app state / events /
    clock). The verifier suite re-evaluates fresh against the corrected world on
    the next /_harness/verify, giving a REAL verdict on the corrected state."""
    if req.task_id not in TASKS:
        raise HTTPException(404, "unknown task")
    _reset_inline(req.task_id, req.seed, ui=req.ui)
    try:
        statecodec.apply_snapshot(SESSION.world, req.state or {})
    except Exception as exc:  # noqa: BLE001 — a bad snapshot is a 422, not a 500
        raise HTTPException(422, f"could not load state: {type(exc).__name__}: {exc}")
    if req.step is not None:
        _state().step = req.step
    s = _state()
    return {"ok": True, "task_id": s.task_id, "seed": s.seed, "step": s.step,
            "current_user_id": s.current_user_id, "snapshot": harness_snapshot()}


@app.get("/_harness/state")
def harness_state() -> dict[str, Any]:
    return _state().to_json()


@app.get("/_harness/world")
def harness_world() -> dict[str, Any]:
    """Omniscient multi-app snapshot: every per-app store + the append-only
    cross-app event log (with each event's ``delivered`` flag). This is the
    HTTP view the environment-correctness gate uses to confirm a cross-app
    effect was actually produced (delivered=True), and the failure harvester
    uses to read which facts were available to the agent."""
    return _world().to_json()


@app.get("/_harness/snapshot")
def harness_snapshot() -> dict[str, Any]:
    """Lightweight snapshot: cart count, orders count, current user, etc."""
    s = _state()
    return {
        "task_id": s.task_id, "step": s.step, "finished": s.finished,
        "current_user_id": s.current_user_id,
        "cart_item_count": sum(i.quantity for i in s.cart.items),
        "orders_count": len(s.orders),
        "returns_count": len(s.returns),
        "subscriptions_count": len(s.subscriptions),
        "applied_promo": s.cart.applied_promo,
    }


@app.post("/_harness/verify")
def harness_verify(req: HarnessVerifyRequest) -> dict[str, Any]:
    if SESSION.suite is None or SESSION.initial is None:
        raise HTTPException(409, "no active episode")
    s = _state()
    s.step = req.step
    # NOTE: verify only READS. The async scheduler is advanced separately at
    # /_harness/tick (start of each turn, before the screenshot) so the agent's
    # observation and this verifier see the SAME world — never an event the
    # screenshot didn't show.
    probe = verifiers.Probe(
        state=s, url=req.url, initial_state=SESSION.initial,
        world=SESSION.world, initial_world=SESSION.initial_world,
        active_tab_url=req.url,
    )
    return SESSION.suite.evaluate(probe, req.step)


class HarnessTickRequest(BaseModel):
    step: int = 0


@app.post("/_harness/tick")
def harness_tick(req: HarnessTickRequest) -> dict[str, Any]:
    """Advance the deterministic clock to ``step`` and flush any scheduled async
    events now due (delivered via the bus). The harness calls this at the START
    of each agent turn, BEFORE the screenshot, so the agent's observation + the
    verifier see the same post-flush world. No-op for single-app episodes (no
    schedule) or when ``step`` <= the current clock."""
    if SESSION.world is None:
        return {"now": 0, "fired": []}
    fired = scheduler.advance_and_flush(SESSION.world, req.step)
    return {
        "now": SESSION.world.schedule.now,
        "fired": [{"type": e.type, "target_app": e.target_app, "step": e.step}
                  for e in fired],
    }


class HarnessRunAgentRequest(BaseModel):
    agent: str = "oracle"
    task_id: str
    seed: int = 0
    brief: str | None = None  # annotator prompt edit → drive a fresh run under this brief


_AGENTS = {"oracle", "llm", "openai", "openai_pixel", "openai_coord", "pixel", "pixel_coord"}


def _dotenv_overrides(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE lines from a gitignored ``.env`` so a fresh API key
    (e.g. ANTHROPIC_API_KEY / ANTHROPIC_MODEL) can be dropped in and picked up on
    the NEXT agent run — no server restart, no key in shell history. .env values
    override the ambient process env so a fresh key wins over a stale/exhausted
    one. Returns {} when the file is absent. Never logs the values."""
    out: dict[str, str] = {}
    try:
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k:
                out[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


async def _spawn_eval_run(agent: str, task_id: str, seed: int, extra_argv: list[str], timeout: int = 240) -> dict[str, Any]:
    """Spawn ``eval.run`` against THIS live server, parse the true score, and
    return a lite trajectory view. Shared by run_agent (reset+drive) and
    resume_run (load_state+drive-forward — via extra_argv)."""
    import asyncio
    import json
    import os
    import re
    import sys

    root = Path(__file__).resolve().parent.parent
    # Merge a gitignored .env (if present) over the process env so LLM agents pick
    # up a working key without restarting the server.
    agent_env = {**os.environ, **_dotenv_overrides(root / ".env")}
    # Run the browser HEADLESS when driving agents for the annotation platform —
    # the annotator reviews the captured replay (screenshots + tab snapshots) in
    # the UI, so a real Chromium window must NOT pop up on the reviewer's screen.
    # (Set GYM_HEADED=1 to watch the browser during local debugging.)
    headless = [] if agent_env.get("GYM_HEADED") == "1" else ["--headless"]
    # Isolate THIS run's trajectory jsonl + scorecard to a unique dir, so the
    # returned trajectory always belongs to the run whose score we parse — never
    # the newest-on-disk file from a CONCURRENT run of the same task+seed.
    # (Screenshots keep the default dir so /_harness/screenshot paths resolve.)
    import shutil
    import tempfile
    run_out = tempfile.mkdtemp(prefix=f"gymrun_{agent.replace('/', '_')}_")
    # eval.run drives THIS live server, so it must dial whatever port uvicorn
    # bound. Cloud Run / any $PORT != 8000 would otherwise get connection-refused.
    server_port = os.environ.get("PORT", "8000")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "eval.run",
        "--agent", agent, "--tasks", task_id, "--seeds", str(seed),
        "--server", f"http://localhost:{server_port}", "--out-traj", run_out, *headless, *extra_argv,
        cwd=str(root), env=agent_env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        raise HTTPException(504, "agent run timed out")
    text = out.decode(errors="replace")

    score: float | None = None
    success: bool | None = None
    m = re.search(r"score=([\d.]+)\s+success=(True|False)", text)
    if m:
        score, success = float(m.group(1)), m.group(2) == "True"
    else:
        sc = Path(run_out) / "_scorecard.json"  # this run's own scorecard
        if sc.exists():
            bt = json.loads(sc.read_text()).get("by_task", {}).get(task_id)
            if bt:
                score = bt.get("score")
                success = (score or 0) >= 0.999
    traj: dict[str, Any] | None = None
    # THIS run's trajectory is the only jsonl in the isolated dir.
    cands = sorted(Path(run_out).glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if cands:
        try:
            d = json.loads(cands[-1].read_text())
            traj = {
                "episode_id": d.get("episode_id"),
                "agent_name": d.get("agent_name"),  # e.g. "openai[gpt-5.5]" — for the review label
                "task_brief": d.get("task_brief"),
                "task_category": d.get("task_category"),
                "task_difficulty": d.get("task_difficulty"),
                "initial_url": d.get("initial_url"),
                "final_url": d.get("final_url"),
                "verifier_result": d.get("verifier_result"),
                "steps": [
                    {
                        "step_idx": s.get("step_idx"),
                        "action_kind": s.get("action_kind"),
                        "action_args": s.get("action_args"),
                        "url_after": s.get("url_after"),
                        "screenshot_path": s.get("screenshot_path"),
                        "reasoning": s.get("reasoning"),
                        "action_error": s.get("action_error"),
                        "active_tab": s.get("active_tab"),
                        "tab_strip": s.get("tab_strip"),
                        # the FULL world after this step — lets a correction resume
                        # from step N's real state instead of the run's final world
                        "world_after": s.get("world_after"),
                    }
                    for s in d.get("steps", [])
                ],
            }
        except (ValueError, OSError):
            traj = None
        # ARCHIVE the raw run before discarding the isolated dir. Isolation fixed a
        # concurrency bug but made runs unreconstructible: the only full record of a
        # run lived in a temp dir that was deleted, so when the annotator DB was
        # wiped the runs could not be rebuilt. Keep the jsonl next to the screenshots
        # it references, so a run is always recoverable from disk.
        try:
            archive = root / "trajectories" / agent.replace("/", "_")
            archive.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cands[-1], archive / cands[-1].name)
        except OSError:
            pass  # archiving is best-effort; never fail a run over it
    shutil.rmtree(run_out, ignore_errors=True)  # ephemeral per-run traj dir (screenshots persist separately)
    return {
        "ok": proc.returncode == 0, "agent": agent, "task_id": task_id,
        "seed": seed, "score": score, "success": success,
        "returncode": proc.returncode, "trajectory": traj, "log_tail": text[-400:],
    }


@app.post("/_harness/run_agent")
async def harness_run_agent(req: HarnessRunAgentRequest) -> dict[str, Any]:
    """Run an agent end-to-end for a task against THIS live server, then report
    the true score. Spawns ``eval.run`` (resets → drives via Playwright →
    verifies), so the annotator can trigger a real run over HTTP. ``oracle`` is
    deterministic (no API key); LLM agents need their key in the env."""
    if req.task_id not in TASKS:
        raise HTTPException(404, "unknown task")
    if req.agent not in _AGENTS:
        raise HTTPException(400, f"unknown agent; use one of {sorted(_AGENTS)}")
    extra = ["--brief-override", req.brief] if req.brief else []
    return await _spawn_eval_run(req.agent, req.task_id, req.seed, extra)


class HarnessResumeRunRequest(BaseModel):
    agent: str = "llm"
    task_id: str
    seed: int = 0
    state: dict = {}
    step: int | None = None
    url: str = "/"
    correction: str = ""  # reviewer's instruction, injected into the agent's context at resume


@app.post("/_harness/resume_run")
async def harness_resume_run(req: HarnessResumeRunRequest) -> dict[str, Any]:
    """Drive-forward resume: load a corrected mid-episode world onto SESSION
    (NOT reset), navigate to the mid-episode URL, and drive the agent FORWARD
    from there, then verify. The observing agent (``llm``) genuinely continues
    from the corrected state; ``oracle`` re-runs from home and is only meaningful
    when resuming a seed-equivalent state. Needs the agent's API key in the env
    for LLM agents (stochastic)."""
    import json
    import tempfile

    if req.task_id not in TASKS:
        raise HTTPException(404, "unknown task")
    if req.agent not in _AGENTS:
        raise HTTPException(400, f"unknown agent; use one of {sorted(_AGENTS)}")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(req.state or {}, f)
        state_path = f.name
    extra = ["--resume-file", state_path, "--resume-url", req.url or "/"]
    if req.step is not None:
        extra += ["--resume-step", str(req.step)]
    if req.correction.strip():
        extra += ["--correction", req.correction.strip()]
    return await _spawn_eval_run(req.agent, req.task_id, req.seed, extra, timeout=300)


@app.get("/_harness/screenshot")
def harness_screenshot(path: str):
    """Serve a per-step screenshot PNG captured during a run (path is relative to
    the repo root, e.g. screenshots/oracle/<episode>/step_004.png)."""
    from fastapi.responses import FileResponse
    root = Path(__file__).resolve().parent.parent
    rel = (root / path).resolve()
    if not str(rel).startswith(str((root / "screenshots").resolve())) or not rel.is_file():
        raise HTTPException(404, "screenshot not found")
    return FileResponse(str(rel), media_type="image/png")


@app.post("/_harness/classify_failure")
def harness_classify_failure(payload: dict) -> dict[str, Any]:
    """Run the UNIVERSAL failure classifier against the real GymState.

    The server owns the GymState, so it's the right place to run the
    rule-based classifier (and optionally the LLM judge). The caller
    passes the episode's success/score plus behavioural hints it can
    observe client-side (step count, whether it looped, whether it hit
    the step cap) — the server can't see the agent's StepRecords.

    Returns ``{"agent_failure_class": <label or None>}``. A label of
    None means the episode succeeded (no failure to classify).
    """
    from harness import failure_classifier as fc
    s = _state()
    verifier_result = {
        "success": bool(payload.get("success", False)),
        "score": float(payload.get("score", 0.0)),
        "final_url": payload.get("url", ""),
    }
    label = fc.classify(
        s.task_brief, s, verifier_result,
        n_steps=int(payload.get("n_steps", 0) or 0),
        had_repeated_actions=bool(payload.get("had_repeated_actions", False)),
        hit_max_steps=bool(payload.get("hit_max_steps", False)),
        use_llm_fallback=bool(payload.get("use_llm_fallback", False)),
        llm_model=payload.get("llm_model", "claude-haiku-4-5"),
    )
    return {"agent_failure_class": label}


# --------------------------------------------------------------------------- #
# Multi-app sub-sites (route-prefixed on the SAME server)
# --------------------------------------------------------------------------- #
# Each app's routes live in its own module and receive the shared handles
# (templates, world accessor, context builder, flash) via configure() — this
# keeps a clean one-way import (main -> app.routes) with no circular import.

mail_routes.configure(
    templates=templates, get_world=_world, build_ctx=_ctx, flash=flash,
)
app.include_router(mail_routes.router)

food_routes.configure(
    templates=templates, get_world=_world, build_ctx=_ctx, flash=flash,
)
app.include_router(food_routes.router)

calendar_routes.configure(
    templates=templates, get_world=_world, build_ctx=_ctx, flash=flash,
)
app.include_router(calendar_routes.router)

market_routes.configure(
    templates=templates, get_world=_world, build_ctx=_ctx, flash=flash,
)
app.include_router(market_routes.router)

# Cross-app event subscribers (FoodOrderPlaced -> mail receipt; the shop
# order-confirmation subscriber is registered too, ready for commit 4).
apps_wiring.register_default_subscribers()
