"""intern_001 / intern_care_packages_by_office — Calendar×Mail×Amazon.

Mechanism: care packages for interns finishing THIS month. Last-day dates live
on Calendar; office locations live in Mail (with a stale-office mismatch for
one intern). Trap = wrong office assignment OR including an intern whose last
day is next month.

Hub map (bridged): Calendar → google_calendar_mock; Mail → gmail_mock;
Shop → amazon_mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "intern_001/intern_care_packages_by_office"
BRIEF_KEY = "intern_001"
BRIEF = (
    "Put together care packages for the interns finishing this month. Their "
    "last days and office locations should be in Calendar and Mail. Send each "
    "package to the right office and email me the order numbers."
)

USER_EMAIL = "alice@shopmail.com"
CARE_KIT = "p_intern001_care_kit"
CARE_KIT_NAME = "Intern Farewell Care Package"
CARE_KIT_PRICE = 28.00

# Finishing this month (May 2026; TODAY=2026-05-21)
PRIYA_NAME = "Priya Shah"
PRIYA_LAST = "2026-05-26"
PRIYA_EVENT = "ev_intern001_priya_last"
# Stale vs current office (mismatch trap)
PRIYA_STALE_ADDR = "addr_sf_office"
PRIYA_CUR_ADDR = "addr_austin_office"
PRIYA_STALE_LINE = "88 Market Street"
PRIYA_CUR_LINE = "401 Congress Avenue"
PRIYA_STALE_CITY = "San Francisco"
PRIYA_CUR_CITY = "Austin"

MARCUS_NAME = "Marcus Webb"
MARCUS_LAST = "2026-05-29"
MARCUS_EVENT = "ev_intern001_marcus_last"
MARCUS_ADDR = "addr_chicago_office"
MARCUS_LINE = "233 S Wacker Drive"
MARCUS_CITY = "Chicago"

# Finishing NEXT month — must NOT get a package
ELENA_NAME = "Elena Cho"
ELENA_LAST = "2026-06-04"
ELENA_EVENT = "ev_intern001_elena_last"
ELENA_ADDR = "addr_nyc_office"
ELENA_LINE = "1 World Trade Center"
ELENA_CITY = "New York"

THIS_MONTH = "2026-05"


def task_intern_001_intern_care_packages_by_office(seed: int) -> "WorldState":
    """FEASIBLE Calendar×Mail×Amazon care-package routing.

    Seed (today Thu May 21):
      - Calendar last days: Priya May 26, Marcus May 29, Elena Jun 4 (next month)
      - Mail: Priya older SF office + newer Austin office; Marcus Chicago; Elena NYC
      - Amazon: Intern Farewell Care Package; office addresses pre-saved

    Correct: order care kits to Austin (Priya current) + Chicago (Marcus); email
    order numbers. Forbidden: SF (stale), NYC / Elena (not this month).
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Address, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.addresses[PRIYA_STALE_ADDR] = Address(
        id=PRIYA_STALE_ADDR,
        label="SF Office (old)",
        full_name="ShopGym SF Office",
        line1=PRIYA_STALE_LINE,
        city=PRIYA_STALE_CITY,
        state="CA",
        zip="94105",
        is_default=False,
    )
    alice.addresses[PRIYA_CUR_ADDR] = Address(
        id=PRIYA_CUR_ADDR,
        label="Austin Office",
        full_name="ShopGym Austin Office",
        line1=PRIYA_CUR_LINE,
        city=PRIYA_CUR_CITY,
        state="TX",
        zip="78701",
        is_default=False,
    )
    alice.addresses[MARCUS_ADDR] = Address(
        id=MARCUS_ADDR,
        label="Chicago Office",
        full_name="ShopGym Chicago Office",
        line1=MARCUS_LINE,
        city=MARCUS_CITY,
        state="IL",
        zip="60606",
        is_default=False,
    )
    alice.addresses[ELENA_ADDR] = Address(
        id=ELENA_ADDR,
        label="NYC Office",
        full_name="ShopGym NYC Office",
        line1=ELENA_LINE,
        city=ELENA_CITY,
        state="NY",
        zip="10007",
        is_default=False,
    )

    shop.products[CARE_KIT] = Product(
        id=CARE_KIT,
        name=CARE_KIT_NAME,
        brand="ShopGym Care",
        category="home",
        base_price=CARE_KIT_PRICE,
        rating=4.6,
        review_count=210,
        stock=80,
        image_emoji="🎁",
        short_description="Snacks, notebook, and a thank-you note for departing interns.",
        tags=["gift", "care-package", "intern"],
    )
    shop.cart.items.clear()

    cal = world.calendar
    cal.events.clear()
    cal.events[PRIYA_EVENT] = CalendarEvent(
        id=PRIYA_EVENT,
        title=f"{PRIYA_NAME} — Last Day",
        day=PRIYA_LAST,
        day_label="Tue May 26",
        start="09:00",
        end="17:00",
        source="seed",
    )
    cal.events[MARCUS_EVENT] = CalendarEvent(
        id=MARCUS_EVENT,
        title=f"{MARCUS_NAME} — Last Day",
        day=MARCUS_LAST,
        day_label="Fri May 29",
        start="09:00",
        end="17:00",
        source="seed",
    )
    cal.events[ELENA_EVENT] = CalendarEvent(
        id=ELENA_EVENT,
        title=f"{ELENA_NAME} — Last Day",
        day=ELENA_LAST,
        day_label="Thu Jun 4",
        start="09:00",
        end="17:00",
        source="seed",
    )
    # Ambient decoy
    cal.events["ev_intern001_gym"] = CalendarEvent(
        id="ev_intern001_gym",
        title="Gym session",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="18:00",
        end="19:00",
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    # Older / stale Priya office
    m.inbox["em_intern001_priya_sf"] = Email(
        id="em_intern001_priya_sf",
        sender=f"{PRIYA_NAME} <priya.shah@shopgym.com>",
        to=USER_EMAIL,
        subject="My desk / office for packages",
        body=(
            f"Hi Alice — I'm based at the San Francisco office for now "
            f"({PRIYA_STALE_LINE}, {PRIYA_STALE_CITY}, CA 94105). "
            "Send any mail there.\n\n— Priya"
        ),
        received_at="2026-04-02T11:00:00",
        received_label="Apr 2",
        read=False,
        labels=["team"],
    )
    # Current Priya office (must win)
    m.inbox["em_intern001_priya_austin"] = Email(
        id="em_intern001_priya_austin",
        sender=f"{PRIYA_NAME} <priya.shah@shopgym.com>",
        to=USER_EMAIL,
        subject="UPDATE: I transferred to Austin",
        body=(
            f"Quick correction — I moved offices. Please use the Austin office "
            f"going forward: {PRIYA_CUR_LINE}, {PRIYA_CUR_CITY}, TX 78701. "
            "The SF address is outdated; don't send packages there anymore.\n\n— Priya"
        ),
        received_at=f"{SEED_DATE}T09:20:00",
        received_label="9:20 AM",
        read=False,
        labels=["team"],
    )
    m.inbox["em_intern001_marcus"] = Email(
        id="em_intern001_marcus",
        sender=f"{MARCUS_NAME} <marcus.webb@shopgym.com>",
        to=USER_EMAIL,
        subject="Chicago office address",
        body=(
            f"Hey — I'm in Chicago for the rest of my internship. Office is "
            f"{MARCUS_LINE}, {MARCUS_CITY}, IL 60606.\n\n— Marcus"
        ),
        received_at=f"{SEED_DATE}T09:35:00",
        received_label="9:35 AM",
        read=False,
        labels=["team"],
    )
    m.inbox["em_intern001_elena"] = Email(
        id="em_intern001_elena",
        sender=f"{ELENA_NAME} <elena.cho@shopgym.com>",
        to=USER_EMAIL,
        subject="NYC office for shipping",
        body=(
            f"If anyone needs my office address: {ELENA_LINE}, {ELENA_CITY}, "
            "NY 10007. Still here through early June.\n\n— Elena"
        ),
        received_at=f"{SEED_DATE}T09:50:00",
        received_label="9:50 AM",
        read=False,
        labels=["team"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_intern_001_intern_care_packages_by_office,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _addr_blob(addr) -> str:
    if addr is None:
        return ""
    return " ".join(
        str(getattr(addr, k, "") or "")
        for k in ("id", "label", "line1", "city", "state", "zip")
    ).lower()


def _is_austin(addr) -> bool:
    b = _addr_blob(addr)
    return "austin" in b or "401 congress" in b or PRIYA_CUR_ADDR in b


def _is_chicago(addr) -> bool:
    b = _addr_blob(addr)
    return "chicago" in b or "wacker" in b or MARCUS_ADDR in b


def _is_sf_stale(addr) -> bool:
    b = _addr_blob(addr)
    return "san francisco" in b or "market street" in b or PRIYA_STALE_ADDR in b


def _is_nyc_elena(addr) -> bool:
    b = _addr_blob(addr)
    return "world trade" in b or (
        "new york" in b and "10007" in b
    ) or ELENA_ADDR in b


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _addr_map(p: Probe) -> dict:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return {}
        user = (shop.users or {}).get("u_alice")
        return dict(user.addresses or {}) if user else {}

    def _new_orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for o in (shop.orders or {}).values() if o.id not in init]

    def _kit_lines(p: Probe) -> list:
        rows = []
        addrs = _addr_map(p)
        for o in _new_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) != CARE_KIT:
                    continue
                aid = getattr(it, "ship_to_address_id", None)
                rows.append((o, it, addrs.get(aid)))
        return rows

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _priya_austin_kit(p: Probe) -> bool:
        return any(_is_austin(addr) for _o, _it, addr in _kit_lines(p))

    def _marcus_chicago_kit(p: Probe) -> bool:
        return any(_is_chicago(addr) for _o, _it, addr in _kit_lines(p))

    def _emailed_order_numbers(p: Probe) -> bool:
        oids = [o.id for o in _new_orders(p)]
        if len(oids) < 1:
            return False
        for se in _sent(p):
            to = (getattr(se, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(se, 'subject', '')} {getattr(se, 'body', '')}"
            # At least one new order id mentioned, plus care/package/office signal
            if any(oid in text for oid in oids):
                return True
        return False

    def _success(p: Probe) -> bool:
        return (
            _priya_austin_kit(p)
            and _marcus_chicago_kit(p)
            and _emailed_order_numbers(p)
        )

    def _shipped_stale_sf(p: Probe) -> bool:
        return any(_is_sf_stale(addr) for _o, _it, addr in _kit_lines(p))

    def _shipped_elena_or_nyc(p: Probe) -> bool:
        return any(_is_nyc_elena(addr) for _o, _it, addr in _kit_lines(p))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "care_kits_this_month_correct_offices",
                    weight=0.7,
                    check=lambda p: _priya_austin_kit(p) and _marcus_chicago_kit(p),
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_order_numbers",
                    weight=0.3,
                    check=_emailed_order_numbers,
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_stale_sf_office",
                    weight=0.0,
                    check=_shipped_stale_sf,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_elena_next_month",
                    weight=0.0,
                    check=_shipped_elena_or_nyc,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}


_SUITE_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_CACHE
    if _SUITE_CACHE is None:
        _SUITE_CACHE = _build_suites()
    return _SUITE_CACHE
