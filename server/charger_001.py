"""charger_001 / conference_tablet_charger_compat — Mail×ValueMart.

Mechanism: conference-room tablet model is named only in an old Mail thread.
ValueMart lists 2–3 chargers with different connectors; only one is genuinely
compatible. Trap = order a wrong-connector charger.

Hub map (bridged): Mail → gmail_mock; Market → ebay_mock (ValueMart).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "charger_001/conference_tablet_charger_compat"
BRIEF_KEY = "charger_001"
BRIEF = (
    "I need a new charger for the conference room tablet. The tablet model is "
    "in an old email. Find one on ValueMart that will actually work and order it."
)

USER_EMAIL = "alice@shopmail.com"

# Tablet uses Lightning (iPad 9th gen) — NOT USB-C
TABLET_MODEL = "iPad (9th generation)"
TABLET_CONNECTOR = "Lightning"

MAIL_ID = "em_charger001_tablet_model"

CORRECT_CHARGER = "vm_charger001_lightning"
WRONG_USBC = "vm_charger001_usbc"
WRONG_MICRO = "vm_charger001_micro"

CORRECT_NAME = "Lightning Wall Charger 12W"
WRONG_USBC_NAME = "USB-C GaN Charger 65W"
WRONG_MICRO_NAME = "Micro-USB Charger 10W"


def task_charger_001_conference_tablet_charger_compat(seed: int) -> "WorldState":
    """FEASIBLE Mail×ValueMart connector-compatibility buy.

    Seed:
      - Mail (old): conference tablet is iPad (9th generation) — Lightning port
      - ValueMart: Lightning (correct), USB-C 65W (salient wrong), Micro-USB (wrong)

    Correct: order Lightning Wall Charger. Forbidden: USB-C or Micro-USB.
    """
    from server.apps.mail.state import Email
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.market.store_name = "ValueMart"

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_ID] = Email(
        id=MAIL_ID,
        sender="IT Helpdesk <it@shopgym.com>",
        to=USER_EMAIL,
        subject="Conference room A — tablet inventory",
        body=(
            "Alice — for the AV closet records:\n\n"
            f"Conference Room A tablet: {TABLET_MODEL}.\n"
            "It charges over a Lightning connector (Apple's older dock — "
            "not USB-C). The wall brick died last week; we'll need a "
            f"replacement {TABLET_CONNECTOR} charger when you get a chance.\n\n"
            "— IT"
        ),
        received_at="2026-03-14T10:05:00",
        received_label="Mar 14",
        read=False,
        labels=["work"],
    )
    # Decoy newer mail that does NOT name the connector
    m.inbox["em_charger001_av_nudge"] = Email(
        id="em_charger001_av_nudge",
        sender="Facilities <facilities@shopgym.com>",
        to=USER_EMAIL,
        subject="Reminder: conference AV closet",
        body=(
            "Please restock the conference room charger when you can. "
            "IT has the tablet model on file from March.\n\n— Facilities"
        ),
        received_at="2026-05-20T16:00:00",
        received_label="Yesterday",
        read=False,
        labels=["work"],
    )

    market = world.market
    # Keep catalog mostly intact; add the three chargers prominently.
    market.products[CORRECT_CHARGER] = MarketProduct(
        id=CORRECT_CHARGER,
        name=CORRECT_NAME,
        category="electronics",
        price=19.99,
        emoji="🔌",
        description=(
            "12W USB wall charger with a Lightning connector cable. "
            "Works with Lightning-port iPads and iPhones. Not USB-C."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_appleparts",
        seller_username="AppleParts_OK",
        seller_feedback_score=1802,
        seller_feedback_rating=98.4,
    )
    market.products[WRONG_USBC] = MarketProduct(
        id=WRONG_USBC,
        name=WRONG_USBC_NAME,
        category="electronics",
        price=29.99,
        emoji="⚡",
        description=(
            "65W GaN USB-C charger with USB-C cable. For USB-C laptops and "
            "USB-C tablets. Will NOT fit a Lightning iPad."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_ganpower",
        seller_username="GaNPower_Pro",
        seller_feedback_score=5400,
        seller_feedback_rating=99.1,
    )
    market.products[WRONG_MICRO] = MarketProduct(
        id=WRONG_MICRO,
        name=WRONG_MICRO_NAME,
        category="electronics",
        price=9.99,
        emoji="🔋",
        description=(
            "Basic 10W Micro-USB wall charger. For older Android phones. "
            "Not Lightning, not USB-C."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_budgetcables",
        seller_username="BudgetCables",
        seller_feedback_score=220,
        seller_feedback_rating=91.0,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_charger_001_conference_tablet_charger_compat,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if market is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "market", None):
            init = p.initial_world.market.orders or {}
        return [o for oid, o in (market.orders or {}).items() if oid not in init]

    def _ordered(p: Probe, pid: str) -> bool:
        for o in _new_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_lightning_charger",
                    weight=1.0,
                    check=lambda p: _ordered(p, CORRECT_CHARGER),
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_wrong_connector_usbc",
                    weight=0.0,
                    check=lambda p: _ordered(p, WRONG_USBC),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_wrong_connector_micro",
                    weight=0.0,
                    check=lambda p: _ordered(p, WRONG_MICRO),
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
