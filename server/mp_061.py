"""mp_061 / coworker_gift_pool_deadline_and_budget — ShopMail×GymCal×ShopGym.

Extended: two gift-pool threads (Priya going-away + Sam birthday), shared $50
cap, GymCal dates for both (not restated in mail), ShopGym gift SKUs with
price-tier + shipping-ETA traps. Combined spend and both arrival windows must
clear independently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_061/coworker_gift_pool_deadline_and_budget"
BRIEF_KEY = "mp_061"
BRIEF = (
    "A few of us are chipping in for Priya's going-away gift, can you handle "
    "my part? Check the thread for the details."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

PRIYA_THREAD = "em_mp061_priya_gift"
SAM_THREAD = "em_mp061_sam_birthday"
CAP_THREAD = "em_mp061_shared_cap"

PRIYA_DAY = "2026-05-28"  # last day — gifts must arrive on/before
SAM_DAY = "2026-05-30"    # birthday party date

# Gold SKUs (under per-thread contrib + arrive before deadlines)
PRIYA_GOLD = "p_mp061_priya_journal"       # $24.99 ≤ $25, arrives May 26
PRIYA_OVER = "p_mp061_priya_basket"        # $32 > $25 contrib
PRIYA_LATE = "p_mp061_priya_keychain"      # $9.99 but arrives Jun 2 (late)

SAM_GOLD = "p_mp061_sam_mug"               # $17.50 ≤ $18, arrives May 28
SAM_OVER = "p_mp061_sam_watchbox"          # $29 > $18
SAM_LATE = "p_mp061_sam_slow_mug"          # $16 but arrives Jun 5 (late)

COMBINED_CAP = 50.0
PRIYA_CONTRIB = 25.0
SAM_CONTRIB = 18.0


def task_mp_061_coworker_gift_pool_deadline_and_budget(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Shop: two gift pools under shared $50 cap.

    Seed (gym clock Thu May 21 noon):
      - Mail: Priya thread ($25 each, no date), Sam birthday thread ($18 each),
        earlier note capping both at $50 combined
      - Cal: Priya's last day May 28; Sam's birthday May 30
      - Shop: price-tier + late-ship traps per recipient
    Correct: order PRIYA_GOLD + SAM_GOLD (total ≤ $50, both arrive in time).
    """
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events["ev_mp061_priya_last"] = CalendarEvent(
        id="ev_mp061_priya_last",
        title="Priya's last day",
        day=PRIYA_DAY,
        day_label="Thu May 28",
        start="09:00",
        end="17:00",
        source="seed",
        description="Priya's final day in the office — farewell lunch at noon.",
    )
    cal.events["ev_mp061_sam_bday"] = CalendarEvent(
        id="ev_mp061_sam_bday",
        title="Sam's birthday",
        day=SAM_DAY,
        day_label="Sat May 30",
        start="18:00",
        end="21:00",
        source="seed",
        description="Sam's birthday get-together — gift needed before this.",
    )

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()

    def _gift(pid, name, price, emoji, short, tags):
        shop.products[pid] = Product(
            id=pid, name=name, brand="ShopGym Gifts", category="gifts",
            base_price=price, rating=4.5, review_count=120, stock=40,
            image_emoji=emoji, short_description=short, long_description=short,
            tags=tags,
        )

    _gift(
        PRIYA_GOLD, "Farewell Keepsake Journal", 24.99, "📓",
        "Going-away gift journal. Ships express — arrives by May 26, 2026.",
        ["gift", "priya", "journal", "express"],
    )
    _gift(
        PRIYA_OVER, "Deluxe Farewell Gift Basket", 32.00, "🎁",
        "Premium farewell basket. Ships express — arrives by May 26, 2026.",
        ["gift", "priya", "basket", "express"],
    )
    _gift(
        PRIYA_LATE, "Farewell Desk Keychain", 9.99, "🔑",
        "Budget farewell keychain. Economy ship — arrives June 2, 2026.",
        ["gift", "priya", "keychain", "economy"],
    )
    _gift(
        SAM_GOLD, "Birthday Ceramic Mug Set", 17.50, "☕",
        "Two-pack birthday mugs. Ships standard — arrives by May 28, 2026.",
        ["gift", "sam", "mug", "birthday"],
    )
    _gift(
        SAM_OVER, "Birthday Watch Gift Box", 29.00, "⌚",
        "Fancy watch gift box. Ships standard — arrives by May 28, 2026.",
        ["gift", "sam", "watch", "birthday"],
    )
    _gift(
        SAM_LATE, "Birthday Mug (economy ship)", 16.00, "mug",
        "Single birthday mug. Slow ship — arrives June 5, 2026.",
        ["gift", "sam", "mug", "economy"],
    )
    # emoji fix for SAM_LATE
    shop.products[SAM_LATE].image_emoji = "🧉"

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[PRIYA_THREAD] = Email(
        id=PRIYA_THREAD,
        sender="jordan.lee@office.example.com",
        to=USER_EMAIL,
        subject="Re: Priya going-away gift pool",
        body=(
            "hey all — looping alice in since she offered to handle ordering.\n\n"
            "ok so quick recap of the chat from earlier this week:\n"
            "jamie: should we do a group card too or just the gift?\n"
            "morgan: card is covered, I'm printing it Friday\n"
            "jordan: cool. for the gift itself let's keep it simple — "
            "let's do $25 each so nobody feels squeezed, and I'll venmo "
            "people after if needed\n"
            "jamie: works for me\n"
            "morgan: same\n\n"
            "alice — whenever you grab something, just keep it in that ballpark "
            "for your share. we want it on her desk before she actually leaves.\n"
            "thx!!"
        ),
        received_at=f"{SEED_DATE}T09:20:00",
        received_label="9:20 AM",
        read=False,
        labels=["work", "unread"],
    )
    mail.inbox[SAM_THREAD] = Email(
        id=SAM_THREAD,
        sender="morgan.park@office.example.com",
        to=USER_EMAIL,
        subject="Sam birthday — are we still chipping in?",
        body=(
            "hi — almost forgot this is the same week as Priya's thing lol.\n\n"
            "thread from last Friday:\n"
            "sam's roommate asked if we wanted to throw in on a gift\n"
            "jamie said sure\n"
            "I said putting in $18 each feels right for a birthday, nothing crazy\n"
            "jordan: +1\n\n"
            "alice if you're already ordering for Priya maybe just grab Sam's "
            "too so we don't do two separate checkouts? whatever works.\n"
            "no date in here — check the calendar invite for when we need it by."
        ),
        received_at="2026-05-20T16:40:00",
        received_label="May 20",
        read=False,
        labels=["work", "unread"],
    )
    mail.inbox[CAP_THREAD] = Email(
        id=CAP_THREAD,
        sender="jordan.lee@office.example.com",
        to=USER_EMAIL,
        subject="fyi on the two gift pools",
        body=(
            "one more thing before I forget — between Priya's going-away and "
            "Sam's birthday we're keeping it under fifty between the two "
            "(your combined spend). don't want May to wreck anyone's budget.\n\n"
            "— jordan"
        ),
        received_at="2026-05-19T11:05:00",
        received_label="May 19",
        read=False,
        labels=["work"],
    )
    mail.inbox["em_mp061_noise"] = Email(
        id="em_mp061_noise",
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Gift guide: spend $75 get free wrap",
        body="Unrelated promo — ignore for the office pools.",
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_061_coworker_gift_pool_deadline_and_budget,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    GOLD = {PRIYA_GOLD, SAM_GOLD}
    LATE = {PRIYA_LATE, SAM_LATE}
    OVER = {PRIYA_OVER, SAM_OVER}

    def _mail_read(p: Probe, eid: str) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(eid)
        return bool(e and getattr(e, "read", False))

    def _new_orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return []
        init = set()
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = set((p.initial_world.shop.orders or {}) or {})
        return [
            o for oid, o in (shop.orders or {}).items()
            if oid not in init and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _new_lines(p: Probe) -> list:
        return [it for o in _new_orders(p) for it in (o.items or [])]

    def _pids(p: Probe) -> set[str]:
        return {getattr(it, "product_id", "") for it in _new_lines(p)}

    def _spend(p: Probe) -> float:
        return sum(
            float(getattr(it, "unit_price", 0) or 0) * int(getattr(it, "quantity", 1) or 1)
            for it in _new_lines(p)
            if getattr(it, "product_id", "") in (
                PRIYA_GOLD, PRIYA_OVER, PRIYA_LATE, SAM_GOLD, SAM_OVER, SAM_LATE
            )
        )

    def _found_both_threads(p: Probe) -> bool:
        return _mail_read(p, PRIYA_THREAD) and _mail_read(p, SAM_THREAD)

    def _extracted_amounts(p: Probe) -> bool:
        # Proxy: read both gift threads + the shared-cap note (amounts live there).
        return _found_both_threads(p) and _mail_read(p, CAP_THREAD)

    def _extracted_dates(p: Probe) -> bool:
        if _log_has(p, "viewed_calendar"):
            return True
        url = (p.active_tab_url or p.url or "")
        return "/calendar" in url

    def _ordered_gift_a(p: Probe) -> bool:
        return PRIYA_GOLD in _pids(p)

    def _ordered_gift_b(p: Probe) -> bool:
        return SAM_GOLD in _pids(p)

    def _combined_under_cap(p: Probe) -> bool:
        lines = [
            it for it in _new_lines(p)
            if getattr(it, "product_id", "") in GOLD
        ]
        if len({getattr(it, "product_id", "") for it in lines}) < 2:
            return False
        return _spend(p) <= COMBINED_CAP + 1e-6

    def _both_shipping_ok(p: Probe) -> bool:
        pids = _pids(p)
        return PRIYA_GOLD in pids and SAM_GOLD in pids and not (pids & LATE)

    def _combined_over(p: Probe) -> bool:
        if not _new_lines(p):
            return False
        return _spend(p) > COMBINED_CAP + 1e-6

    def _shipping_missed(p: Probe) -> bool:
        return bool(_pids(p) & LATE)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_both_gift_threads", weight=0.15,
                          check=_found_both_threads, required_for_success=True),
                Milestone("extracted_both_contribution_amounts", weight=0.15,
                          check=_extracted_amounts, required_for_success=True),
                Milestone("extracted_both_dates_from_calendar", weight=0.15,
                          check=_extracted_dates, required_for_success=True),
                Milestone("ordered_gift_a_correct_tier", weight=0.15,
                          check=_ordered_gift_a, required_for_success=True),
                Milestone("ordered_gift_b_correct_tier", weight=0.15,
                          check=_ordered_gift_b, required_for_success=True),
                Milestone("combined_total_under_cap", weight=0.15,
                          check=_combined_under_cap, required_for_success=True),
                Milestone("both_shipping_windows_valid", weight=0.1,
                          check=_both_shipping_ok, required_for_success=True),
                Milestone("combined_total_exceeds_cap", weight=0.0,
                          check=_combined_over, required_for_success=False,
                          forbidden=True),
                Milestone("either_shipping_window_missed", weight=0.0,
                          check=_shipping_missed, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
