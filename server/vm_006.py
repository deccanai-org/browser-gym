"""vm_006 / new_hire_monitor_three_constraints — Mail×Xbay spec conjunction.

Mechanism: three constraint emails (VESA 100, budget under $150, DisplayPort)
plus six Xbay monitor listings. Exactly one listing satisfies all three.
Salient wrong picks each fail on a different email's constraint.

Family: ``spec_conjunction_listing`` — distinct from seller-rating (vm_001),
fair-price sell (vm_002), already-fulfilled dock (vm_003), condition lie
(vm_004), and shipping-promise lie (vm_005).

Hub map (bridged): Mail → gmail_mock; Market → ebay_mock (Xbay).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "vm_006/new_hire_monitor_three_constraints"
BRIEF_KEY = "vm_006"
BRIEF = (
    "Jordan Reyes starts Monday and needs a monitor at his desk. Order one "
    "from Xbay — the requirements came in by email."
)

USER_EMAIL = "alice@shopmail.com"

MAIL_FACILITIES = "em_vm006_facilities_vesa"
MAIL_FINANCE = "em_vm006_finance_budget"
MAIL_IT = "em_vm006_it_displayport"
MAIL_NOISE_DESK = "em_vm006_noise_desk"
MAIL_NOISE_ONBOARD = "em_vm006_noise_onboard"

CORRECT = "vm_006_mon_office_ips"
TRAP_BUDGET_UW = "vm_006_mon_ultrawide"
TRAP_BUDGET_PRO = "vm_006_mon_pro_ips"
TRAP_VESA = "vm_006_mon_curved"
TRAP_INPUT = "vm_006_mon_budget_led"
TRAP_BOTH = "vm_006_mon_portable"

CORRECT_NAME = "24-inch Office IPS"
FORBIDDEN = (
    TRAP_BUDGET_UW,
    TRAP_BUDGET_PRO,
    TRAP_VESA,
    TRAP_INPUT,
    TRAP_BOTH,
)


def task_vm_006_new_hire_monitor_three_constraints(seed: int) -> "WorldState":
    """FEASIBLE Mail×Xbay three-constraint monitor buy."""
    from server.apps.mail.state import Email
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_FACILITIES] = Email(
        id=MAIL_FACILITIES,
        sender="Facilities <facilities@shopgym.com>",
        to=USER_EMAIL,
        subject="Sit-stand desks — mount note for new hires",
        body=(
            "Heads-up for anyone buying monitors for the new sit-stand fleet:\n\n"
            "The arms only take VESA 100×100 mounts. Anything with VESA 75 or "
            "no VESA won't clamp on.\n\n"
            "— Facilities"
        ),
        received_at="2026-05-08T09:40:00",
        received_label="May 8",
        read=False,
        labels=["work"],
    )
    m.inbox[MAIL_FINANCE] = Email(
        id=MAIL_FINANCE,
        sender="Finance Ops <finance@shopgym.com>",
        to=USER_EMAIL,
        subject="Reminder: monitor purchases under $150",
        body=(
            "Alice — quick policy ping for desk hardware:\n\n"
            "Anything at or over $150 needs a PO before you order. Under $150 "
            "you can buy on Xbay with the usual card.\n\n"
            "— Finance"
        ),
        received_at="2026-05-14T11:05:00",
        received_label="May 14",
        read=False,
        labels=["work"],
    )
    m.inbox[MAIL_IT] = Email(
        id=MAIL_IT,
        sender="IT Helpdesk <it@shopgym.com>",
        to=USER_EMAIL,
        subject="Jordan Reyes dock — DisplayPort only",
        body=(
            "Jordan's docking station outputs DisplayPort only (no HDMI on "
            "the dock). Please make sure whatever monitor you get for his "
            "desk has a DisplayPort input.\n\n"
            "— IT"
        ),
        received_at="2026-05-19T14:20:00",
        received_label="May 19",
        read=False,
        labels=["work"],
    )
    m.inbox[MAIL_NOISE_DESK] = Email(
        id=MAIL_NOISE_DESK,
        sender="Facilities <facilities@shopgym.com>",
        to=USER_EMAIL,
        subject="Desk delivery confirmed — bay 4B",
        body=(
            "Jordan's sit-stand desk is staged in bay 4B. No action needed "
            "from you on furniture.\n\n— Facilities"
        ),
        received_at="2026-05-20T08:15:00",
        received_label="May 20",
        read=False,
        labels=["work"],
    )
    m.inbox[MAIL_NOISE_ONBOARD] = Email(
        id=MAIL_NOISE_ONBOARD,
        sender="IT Helpdesk <it@shopgym.com>",
        to=USER_EMAIL,
        subject="Onboarding checklist — Jordan Reyes",
        body=(
            "Standard IT onboarding checklist attached in the wiki. Laptop "
            "image is ready; peripherals are your call this week.\n\n— IT"
        ),
        received_at="2026-05-20T16:40:00",
        received_label="May 20",
        read=False,
        labels=["work"],
    )

    listings = (
        {
            "id": TRAP_BUDGET_UW,
            "name": "34-inch UltraWide 4K",
            "price": 329.00,
            "description": (
                "34-inch ultrawide 4K monitor. VESA 100×100. Inputs: "
                "DisplayPort + HDMI. Premium panel — over the $150 PO threshold."
            ),
        },
        {
            "id": TRAP_BUDGET_PRO,
            "name": "27-inch Pro IPS",
            "price": 189.00,
            "description": (
                "27-inch IPS productivity monitor. VESA 100×100. Inputs: "
                "DisplayPort + HDMI. Priced at $189 — needs a PO (≥ $150)."
            ),
        },
        {
            "id": TRAP_VESA,
            "name": "27-inch Curved",
            "price": 139.00,
            "description": (
                "27-inch curved monitor under budget. Mount: VESA 75×75 only "
                "(not 100×100). Inputs: DisplayPort. Will not fit the new "
                "sit-stand arms."
            ),
        },
        {
            "id": TRAP_INPUT,
            "name": "24-inch Budget LED",
            "price": 89.00,
            "description": (
                "24-inch budget LED. VESA 100×100. Inputs: HDMI only — no "
                "DisplayPort. Cheap, but Jordan's dock has no HDMI."
            ),
        },
        {
            "id": CORRECT,
            "name": CORRECT_NAME,
            "price": 129.00,
            "description": (
                "24-inch Office IPS. VESA 100×100. Inputs: DisplayPort + HDMI. "
                "Priced at $129 (under the $150 PO line). Fits the new "
                "sit-stand arms and Jordan's DP-only dock."
            ),
        },
        {
            "id": TRAP_BOTH,
            "name": "15-inch Portable",
            "price": 119.00,
            "description": (
                "15-inch portable USB-C display. No VESA mount. Input: USB-C "
                "only (no DisplayPort). Fine for travel, wrong for Jordan's desk."
            ),
        },
    )

    market = world.market
    for row in listings:
        market.products[row["id"]] = MarketProduct(
            id=row["id"],
            name=row["name"],
            category="electronics",
            price=row["price"],
            emoji="🖥️",
            description=row["description"],
            in_stock=True,
            shop_sku=None,
            seller_id="seller_officeav",
            seller_username="OfficeAV_Supply",
            seller_feedback_score=3100,
            seller_feedback_rating=99.1,
            condition="New",
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_vm_006_new_hire_monitor_three_constraints,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
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

    def _ordered_any_forbidden(p: Probe) -> bool:
        return any(_ordered(p, pid) for pid in FORBIDDEN)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_correct_office_ips",
                    weight=1.0,
                    check=lambda p: _ordered(p, CORRECT),
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_wrong_monitor",
                    weight=0.0,
                    check=_ordered_any_forbidden,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
