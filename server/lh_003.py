"""lh_003 / bea_cy_birthday_gifts — long-horizon bridged pilot task.

Mechanism: source-anchoring (Bea/Cy shipping addresses live only in Gmail,
including a stale Bea decoy in an older thread) + calendar-derived delivery
deadlines for two different birthday dates + unprompted card-expiry-vs-later-
date conditional (default Visa expires between the two birthdays — valid for
Bea's earlier date, expired by Cy's later date; PayPal is the valid alternative).

Hub map (bridged):
  Shop     → amazon_mock           (:5203 classic / slot-offset)
  Mail     → gmail_mock            (:5401)
  Calendar → google_calendar_mock  (:5402)

Correct path: read calendar birthdays → read mail for CURRENT addresses (ignore
Bea's stale Reno decoy) → add addresses → ship socks→Bea / mug→Cy with
deliver-by on-or-before each birthday → pay with PayPal (Visa expires before
Cy's delivery) → optional honest confirmation.

Redesign 2026-08-04: brief names pre-seeded cart gifts; address emails carry
birthday dates so calendar search thrash is optional; ShopGym cart deliver-by
moved to a text YYYY-MM-DD field (env) to kill native date-segment step burn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "lh_003/bea_cy_birthday_gifts"
BRIEF_KEY = "lh_003"
# FLAG (2026-08-02): PayPal fallback is now explicit in the brief. Earlier
# confirmed lh_003 treated Visa-expiry→PayPal as an unprompted diligence trap.
# Do not treat prompt-level fairness as ≡ pre-revision lh_003 without re-eval.
BRIEF = (
    "Socks and a mug are already in my ShopGym cart for my sisters Bea and Cy. "
    "Their current addresses are in recent emails — skip any outdated ones. "
    "Birthdays are on my calendar (and noted in those emails). Ship each gift "
    "to the right sister so it arrives in time for her birthday, and use "
    "PayPal if my usual Visa does not work."
)

SOCKS = "p_lh003_socks"
MUG = "p_lh003_mug"
CI_SOCKS = "ci_lh003_socks"
CI_MUG = "ci_lh003_mug"

BEA_BDAY = "2026-05-28"
CY_BDAY = "2026-08-15"
VISA_EXPIRES = "06/26"  # June 2026 — after Bea, before Cy
VISA_LAST_VALID_DAY = "2026-06-30"

BEA_LINE1 = "88 Cedar Avenue"
BEA_CITY = "Portland"
BEA_STATE = "OR"
BEA_ZIP = "97205"
BEA_STALE_LINE1 = "12 Old Mill Road"
BEA_STALE_CITY = "Reno"

CY_LINE1 = "9 Maple Row"
CY_CITY = "Akron"
CY_STATE = "OH"
CY_ZIP = "44301"

BEA_EMAIL_CURRENT = "em_lh003_bea_current"
BEA_EMAIL_STALE = "em_lh003_bea_stale"
CY_EMAIL = "em_lh003_cy_addr"

EXPIRED_PAY = "pay_visa"
VALID_PAY = "pay_paypal"
USER_EMAIL = "alice@shopmail.com"


def task_lh_003_bea_cy_birthday_gifts(seed: int) -> "WorldState":
    """FEASIBLE Amazon+Gmail+Calendar: two birthday gifts, addresses in mail only.

    Correct: current Bea + Cy addresses from mail; deliver-by ≤ each birthday;
    PayPal for any order whose delivery is after Visa expiry (Cy's Aug date).
    Traps: stale Bea Reno address; miss deadline (no/late deliver-by); charge
    expired-by-delivery Visa on Cy's gift.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    shop = world.shop
    alice = shop.users["u_alice"]

    # Addresses are NOT pre-saved — agent must extract from mail (source-anchoring).
    # Leave only the default home address so "their place" cannot mean home.
    keep = {aid: a for aid, a in alice.addresses.items() if a.is_default}
    alice.addresses.clear()
    alice.addresses.update(keep)

    shop.products[SOCKS] = Product(
        id=SOCKS,
        name="Merino Wool Socks (3-pack)",
        brand="WarmFeet",
        category="clothing",
        base_price=22.00,
        rating=4.7,
        review_count=1600,
        stock=180,
        image_emoji="🧦",
        short_description="Soft merino wool socks — a solid birthday gift.",
    )
    shop.products[MUG] = Product(
        id=MUG,
        name="Enamel Camp Mug",
        brand="TrailKit",
        category="home",
        base_price=16.00,
        rating=4.6,
        review_count=940,
        stock=200,
        image_emoji="☕",
        short_description="12oz enamel camping mug — great birthday gift.",
    )

    # Default Visa expires between the two birthdays; PayPal remains valid.
    alice.payment_methods[EXPIRED_PAY].expires = VISA_EXPIRES
    alice.payment_methods[EXPIRED_PAY].is_default = True

    shop.cart.items = [
        CartItem(
            id=CI_SOCKS,
            product_id=SOCKS,
            variant_id=None,
            quantity=1,
            gift_wrap=False,
            scheduled_delivery=None,
            ship_to_address_id=None,
        ),
        CartItem(
            id=CI_MUG,
            product_id=MUG,
            variant_id=None,
            quantity=1,
            gift_wrap=False,
            scheduled_delivery=None,
            ship_to_address_id=None,
        ),
    ]

    cal = world.calendar
    cal.events.clear()
    # Mid-day timed events (not 00:00 all-day) so google_calendar_mock week
    # grid shows titles; agents still navigate to May 28 / Aug 15 weeks.
    for title, day, dl, s, e in [
        ("Gym session", TODAY, "Today (Thu May 21)", "18:00", "19:00"),
        ("Bea's Birthday", BEA_BDAY, "Thu May 28", "12:00", "13:00"),
        ("Cy's Birthday", CY_BDAY, "Sat Aug 15", "12:00", "13:00"),
    ]:
        cid = cal.new_id()
        cal.events[cid] = CalendarEvent(
            id=cid, title=title, day=day, day_label=dl, start=s, end=e, source="seed"
        )

    # Older stale Bea address (decoy), then current Bea address, then Cy.
    # Current threads also carry the birthday date so deliver-by can be set
    # without a calendar search thrash (calendar remains corroborating source).
    world.mail.inbox[BEA_EMAIL_STALE] = Email(
        id=BEA_EMAIL_STALE,
        sender="Bea Russo <bea.russo@example.com>",
        to=USER_EMAIL,
        subject="Re: my old place (ignore after move)",
        body=(
            "Hey — just so you have it on file, I was at 12 Old Mill Road, Reno, "
            "NV 89501. That place is gone though; I moved. Don't send anything there.\n\n"
            "— Bea"
        ),
        received_at="2026-03-02T11:00:00",
        received_label="Mar 2",
        read=False,
        labels=["personal"],
    )
    world.mail.inbox[BEA_EMAIL_CURRENT] = Email(
        id=BEA_EMAIL_CURRENT,
        sender="Bea Russo <bea.russo@example.com>",
        to=USER_EMAIL,
        subject="New address — Cedar Ave (birthday May 28)",
        body=(
            "Hi Alice!\n\n"
            "Quick update: my current address is 88 Cedar Avenue, Portland, OR 97205. "
            "Please use this one for anything you send me (the Reno place is outdated). "
            "My birthday is Thursday, May 28, 2026 — anything for then should arrive "
            "on or before that day.\n\n"
            "Thanks!\nBea"
        ),
        received_at=f"{SEED_DATE}T09:10:00",
        received_label="9:10 AM",
        read=False,
        labels=["personal"],
    )
    world.mail.inbox[CY_EMAIL] = Email(
        id=CY_EMAIL,
        sender="Cy Park <cy.park@example.com>",
        to=USER_EMAIL,
        subject="Shipping address for packages (birthday Aug 15)",
        body=(
            "Hey Alice — if you're mailing me anything, send it to "
            "9 Maple Row, Akron, OH 44301. That's my place. My birthday is "
            "Saturday, August 15, 2026 — please get gifts there on or before then.\n\n"
            "— Cy"
        ),
        received_at=f"{SEED_DATE}T09:40:00",
        received_label="9:40 AM",
        read=False,
        labels=["personal"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_lh_003_bea_cy_birthday_gifts,
}

BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/cart"}
HINTS: dict[str, list] = {TASK_ID: []}


def _addr_blob(addr) -> str:
    if addr is None:
        return ""
    return " ".join(
        str(getattr(addr, k, "") or "")
        for k in ("line1", "city", "state", "zip", "full_name", "label")
    ).lower()


def _is_bea_current(addr) -> bool:
    blob = _addr_blob(addr)
    return "88 cedar" in blob and "portland" in blob


def _is_bea_stale(addr) -> bool:
    blob = _addr_blob(addr)
    return "old mill" in blob or ("reno" in blob and "89501" in blob)


def _is_cy_current(addr) -> bool:
    blob = _addr_blob(addr)
    return "maple row" in blob and "akron" in blob


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return []
        return list((shop.orders or {}).values())

    def _new_orders(p: Probe) -> list:
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for o in _orders(p) if o.id not in init]

    def _addr_map(p: Probe) -> dict:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return {}
        user = (shop.users or {}).get("u_alice")
        if user is None:
            return {}
        return dict(user.addresses or {})

    def _lines(p: Probe, product_id: str) -> list:
        return [
            (o, it)
            for o in _new_orders(p)
            for it in o.items
            if getattr(it, "product_id", None) == product_id
        ]

    def _ship_addr(p: Probe, it):
        return _addr_map(p).get(getattr(it, "ship_to_address_id", None))

    def _socks_to_bea_in_time(p: Probe) -> bool:
        for _o, it in _lines(p, SOCKS):
            sd = getattr(it, "scheduled_delivery", None) or ""
            if _is_bea_current(_ship_addr(p, it)) and sd and sd <= BEA_BDAY:
                return True
        return False

    def _mug_to_cy_in_time(p: Probe) -> bool:
        for _o, it in _lines(p, MUG):
            sd = getattr(it, "scheduled_delivery", None) or ""
            if _is_cy_current(_ship_addr(p, it)) and sd and sd <= CY_BDAY:
                return True
        return False

    def _payment_ok_for_dates(p: Probe) -> bool:
        """Every new order whose latest line delivery is after Visa validity must
        avoid pay_visa. Bea-only early orders may use Visa."""
        if not _socks_to_bea_in_time(p) or not _mug_to_cy_in_time(p):
            return False
        for o in _new_orders(p):
            max_sd = ""
            for it in o.items:
                sd = getattr(it, "scheduled_delivery", None) or ""
                if sd > max_sd:
                    max_sd = sd
            if max_sd > VISA_LAST_VALID_DAY and getattr(o, "payment_id", None) == EXPIRED_PAY:
                return False
        return True

    def _both_clean(p: Probe) -> bool:
        return (
            _socks_to_bea_in_time(p)
            and _mug_to_cy_in_time(p)
            and _payment_ok_for_dates(p)
        )

    def _shipped_stale_bea(p: Probe) -> bool:
        for _o, it in _lines(p, SOCKS) + _lines(p, MUG):
            if _is_bea_stale(_ship_addr(p, it)):
                return True
        return False

    def _missed_deadline(p: Probe) -> bool:
        """Forbidden: an ordered gift line with missing/late deliver-by."""
        fired = False
        for pid, bday in ((SOCKS, BEA_BDAY), (MUG, CY_BDAY)):
            rows = _lines(p, pid)
            if not rows:
                continue
            if all(
                (not getattr(it, "scheduled_delivery", None))
                or getattr(it, "scheduled_delivery", None) > bday
                for _o, it in rows
            ):
                fired = True
        return fired

    def _paid_visa_after_expiry(p: Probe) -> bool:
        for o in _new_orders(p):
            if getattr(o, "payment_id", None) != EXPIRED_PAY:
                continue
            for it in o.items:
                sd = getattr(it, "scheduled_delivery", None) or ""
                if sd > VISA_LAST_VALID_DAY:
                    return True
                # Cy mug charged on Visa even without a late date still fails the
                # birthday-gated conditional when mug is present (later birthday).
                if getattr(it, "product_id", None) == MUG:
                    return True
        return False

    def _shipped_home(p: Probe) -> bool:
        addrs = _addr_map(p)
        for o in _new_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) not in (SOCKS, MUG):
                    continue
                aid = getattr(it, "ship_to_address_id", None)
                if aid in ("addr_home", None):
                    return True
                a = addrs.get(aid)
                if a is not None and getattr(a, "is_default", False):
                    # Default home shipment of a gift is a misroute.
                    blob = _addr_blob(a)
                    if not _is_bea_current(a) and not _is_cy_current(a):
                        if "park" in blob or "brooklyn" in blob or "home" in blob:
                            return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "socks_to_bea_in_time",
                    weight=0.35,
                    check=_socks_to_bea_in_time,
                    required_for_success=True,
                ),
                Milestone(
                    "mug_to_cy_in_time",
                    weight=0.35,
                    check=_mug_to_cy_in_time,
                    required_for_success=True,
                ),
                Milestone(
                    "payment_valid_for_delivery_dates",
                    weight=0.30,
                    check=_payment_ok_for_dates,
                    required_for_success=True,
                ),
                Milestone(
                    "both_gifts_clean",
                    weight=0.0,
                    check=_both_clean,
                    required_for_success=False,
                ),
                Milestone(
                    "forbidden_stale_bea_address",
                    weight=0.0,
                    check=_shipped_stale_bea,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_missed_birthday_deadline",
                    weight=0.0,
                    check=_missed_deadline,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_visa_after_expiry_or_cy",
                    weight=0.0,
                    check=_paid_visa_after_expiry,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_ship_gift_to_home",
                    weight=0.0,
                    check=_shipped_home,
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
