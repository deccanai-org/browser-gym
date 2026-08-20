"""WorldState — the multi-app world for one episode.

The shop's "database" IS the existing :class:`server.state.GymState`. It is
*wrapped* here, NOT renamed or modified, so every existing single-app task,
verifier, oracle and test keeps working untouched. Each NEW app owns its
own isolated store (``mail`` / ``food`` / ``calendar``); the only channel
for cross-app effects is the append-only event log in
:mod:`server.apps.bus`.

Episode metadata (``task_id`` / ``seed`` / ``step`` / ``finished``)
delegates to the shop store, which is always present. That means the
harness's verify/snapshot pipeline — which already reads those fields off
whatever state object it is handed — works unchanged whether it receives a
bare ``GymState`` (single-app episode) or a ``WorldState`` (cross-app
episode).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from server.state import GymState
from server.apps.bus import WorldEvent
from server.apps.scheduler import ScheduleState

if TYPE_CHECKING:                      # Phase-2 stores; not imported at runtime
    from server.apps.mail.state import MailState
    from server.apps.food.state import FoodState
    from server.apps.calendar.state import CalendarState
    from server.apps.market.state import MarketState


@dataclass
class WorldState:
    """One instance of every app's store + the cross-app event log."""

    shop: GymState                                       # existing model, UNCHANGED
    mail: Optional["MailState"] = None
    food: Optional["FoodState"] = None
    calendar: Optional["CalendarState"] = None
    market: Optional["MarketState"] = None               # 2nd e-commerce store (Xbay)
    events: list[WorldEvent] = field(default_factory=list)   # append-only
    # Deterministic async event injector — scheduled future cross-app effects
    # (emails/price-changes/notifications) that fire on the step clock, not on
    # the agent's action. Task factories seed ``schedule.queue``; the harness
    # ticks the clock at each step boundary (see server.apps.scheduler).
    schedule: ScheduleState = field(default_factory=ScheduleState)

    # ----- episode metadata: single source of truth is the shop store ----- #
    @property
    def task_id(self) -> str:
        return self.shop.task_id

    @property
    def seed(self) -> int:
        return self.shop.seed

    @property
    def step(self) -> int:
        return self.shop.step

    @property
    def finished(self) -> bool:
        return self.shop.finished

    # ----- snapshot ------------------------------------------------------- #
    def to_json(self) -> dict[str, Any]:
        """Compact omniscient snapshot across every app's store + the
        cross-app event log. Mirrors :meth:`GymState.to_json` so verifier
        and debugging tooling read a single, predictable shape."""
        return {
            "task_id": self.task_id,
            "seed": self.seed,
            "step": self.step,
            "finished": self.finished,
            "shop": self.shop.to_json(),
            "mail": self.mail.to_json() if self.mail is not None else None,
            "food": self.food.to_json() if self.food is not None else None,
            "calendar": (
                self.calendar.to_json() if self.calendar is not None else None
            ),
            "market": self.market.to_json() if self.market is not None else None,
            "events": [asdict(e) for e in self.events],
            "schedule": self.schedule.to_json(),
        }
