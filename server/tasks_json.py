"""Data-driven tasks — a task is a JSON file, not a Python factory.

A task has always been three things fused together: a *factory* that builds the
seed world, a *brief* string, and a *suite* of milestones. Writing one meant
editing three registries in two 13k-line modules. This module makes the common
case declarative: drop ``tasks/M401.json`` into the tasks directory and the gym
picks it up — world, brief, start path, verifier suite and all.

What it is NOT: a replacement for the Python factories. The suites in
``verifiers.py`` do money arithmetic, negation-aware claim detection, pairwise
scans over records and bus/scheduler queries; a declarative op compares a field
to a *literal* and cannot do any of that. The vocabulary here is deliberately
small and the escape hatch (``kind: "python"``) is deliberately visible in the
JSON, because a hybrid task that says so is honest and a silently-downgraded one
is not.

The governing rule, learned the expensive way in this codebase: **a verifier
that cannot prove anything must never be counted as proving something.** So
every ambiguity is a load error — an unknown check kind, an unknown collection,
an unknown product category, an unknown entity field, a weight set that does not
sum to 1.0, an id that collides with a Python task. Nothing here degrades to a
no-op predicate that quietly returns False (or, worse, True) forever.

Loading is two-staged on purpose:

* ``specs()`` parses and validates structure and compiles every check. It
  touches no other ``server`` module, so ``tasks.py`` and ``verifiers.py`` can
  both call it from their own import tails without a cycle.
* the seed world is built lazily, on first ``build_world`` — that step needs
  ``server.tasks`` (the shared Alice fixture) and ``server.catalog``, which are
  only fully importable once those modules finish importing.

The step-0 gate (no milestone may already be satisfied by the untouched seed
world) runs with the first world build and is exercised for every shipped task
by ``tests/test_tasks_json.py``.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib
import json
import pathlib
import re
import warnings
from typing import Any, Callable

from server.apps.calendar.state import CalendarEvent
from server.apps.food.state import FoodOrder, Restaurant
from server.apps.mail.state import Email
from server.apps.market.state import MarketCoupon, MarketOrder, MarketProduct
from server.state import (
    Address, CartItem, GymState, Order, OrderItem, PaymentMethod, Product,
    Promotion, ReturnRequest, Subscription, User,
)

#: Where a task file lives. Top level only — ``tasks/examples/`` deliberately is
#: not scanned, so an example can ship without becoming a registered task.
TASKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "tasks"


class TaskSpecError(ValueError):
    """A task file that cannot be loaded. Always names the task and the fragment."""


# --------------------------------------------------------------------------- #
# Vocabulary constants
# --------------------------------------------------------------------------- #

CATEGORIES = ("A", "B", "C", "D", "M")
DIFFICULTIES = ("easy", "medium", "hard")
BASES = ("shop", "world")

#: The seven categories the storefront navigation actually renders
#: (``ui/pages/_layout.html``). A product in any other category is reachable by
#: direct URL only — it exists but no nav, no category page, no filter can find
#: it, so a task built on it is unsolvable through the UI. Mirrored by a test
#: against the template so drift fails loudly.
UI_CATEGORIES = ("electronics", "audio", "books", "clothing", "home", "pet", "office")

#: category -> every tag that puts a product in *some* subcategory drill-down
#: (``server.main.SUBCATEGORIES``). A product with no matching tag lives on the
#: category page but in no subcategory; that is a warning, not an error, because
#: a few real tasks want exactly that.
SUBCATEGORY_TAGS: dict[str, frozenset[str]] = {
    "electronics": frozenset({"laptop", "mouse", "keyboard", "monitor",
                              "charger", "usb-c", "watch", "fitness", "trackpad"}),
    "audio": frozenset({"headphones", "speaker"}),
    "books": frozenset({"fiction", "sci-fi", "nonfiction", "history",
                        "biography", "cookbook"}),
    "clothing": frozenset({"tshirt", "polo", "tank", "hoodie", "jacket"}),
    "home": frozenset({"lamp", "mug", "candle"}),
    "pet": frozenset({"dog", "treats"}),
    "office": frozenset({"display", "chair"}),
}

#: collection path -> the dataclass one entry of it is. Keys must equal the
#: collection ids in ``server.seeddb.store.COLLECTIONS``; that module imports
#: ``server.tasks`` so it cannot be imported from here, and a test asserts the
#: two lists agree instead.
COLLECTION_TYPES: dict[str, type] = {
    "shop.products": Product,
    "shop.promotions": Promotion,
    "shop.users": User,
    "shop.orders": Order,
    "shop.returns": ReturnRequest,
    "shop.subscriptions": Subscription,
    "mail.inbox": Email,
    "mail.sent": Email,
    "mail.drafts": Email,
    "food.restaurants": Restaurant,
    "food.orders": FoodOrder,
    "calendar.events": CalendarEvent,
    "market.products": MarketProduct,
    "market.coupons": MarketCoupon,
    "market.orders": MarketOrder,
}

#: Collections that hang off an entity rather than off a store, addressed by a
#: dotted path so a task can add one address without restating the whole User.
_NESTED_RE = re.compile(r"^shop\.users\.([A-Za-z0-9_]+)\.(addresses|payment_methods)$")
_NESTED_TYPES = {"addresses": Address, "payment_methods": PaymentMethod}

#: Ordered lists rather than keyed dicts. Upserted by ``id``.
LIST_TYPES: dict[str, type] = {"shop.cart.items": CartItem}

#: Per-store scalars, whitelisted one by one because they are levers, not data.
#: The ``armed_*`` / ``defer_*`` / ``enable_*`` entries are the sub-app trap
#: flags: they are plain dataclass fields, but nothing else documents that they
#: exist, so they are surfaced here or they are unreachable from JSON.
SCALARS: dict[str, tuple[str, ...]] = {
    "shop.current_user_id": ("shop", "current_user_id"),
    "shop.cart.applied_promo": ("shop", "cart", "applied_promo"),
    "mail.account_email": ("mail", "account_email"),
    "mail.account_name": ("mail", "account_name"),
    "mail.armed_bounce": ("mail", "armed_bounce"),
    "mail.armed_forged_market_failure": ("mail", "armed_forged_market_failure"),
    "mail.armed_forged_food_calendar_threat": ("mail", "armed_forged_food_calendar_threat"),
    "mail.armed_forged_coupon_confirmation": ("mail", "armed_forged_coupon_confirmation"),
    "food.defer_receipt_steps": ("food", "defer_receipt_steps"),
    "food.enable_delivery_notes": ("food", "enable_delivery_notes"),
    "food.cart.promo_code": ("food", "cart", "promo_code"),
    "calendar.account_name": ("calendar", "account_name"),
    "market.delivery_fee": ("market", "delivery_fee"),
    "market.free_delivery_over": ("market", "free_delivery_over"),
    "market.cart.applied_coupon": ("market", "cart", "applied_coupon"),
}

#: The escape hatch's allowlist: ref string -> why it cannot be declarative.
#: Membership is checked at load; the callable is resolved when the suite is
#: built. Adding a ref here is a deliberate, reviewable act — the point of the
#: hatch is that a hybrid task is *visible*, not that it is convenient.
PYTHON_REFS: dict[str, str] = {
    "server.tasks_json:calendar_double_booked":
        "pairwise overlap scan over events — 'field equals literal' cannot say "
        "'these two records disagree'",
    "server.tasks_json:sent_mail_contains_phone_number":
        "regex over free text; a raw pattern in JSON is Python with worse "
        "ergonomics and no test",
}

_TOP_LEVEL_KEYS = frozenset({
    "short_id", "slug", "category", "difficulty", "prompt", "start_path",
    "base", "seed_world", "milestones", "build_status", "oracle", "notes",
})
_MILESTONE_KEYS = frozenset({"name", "weight", "check", "required", "forbidden", "category"})


# --------------------------------------------------------------------------- #
# Allowlisted escape-hatch predicates
# --------------------------------------------------------------------------- #
# Each takes a verifiers.Probe and returns bool. They live here rather than in
# verifiers.py because they exist to serve JSON tasks; a task-specific escape
# still belongs next to its suite.

def calendar_double_booked(probe: Any) -> bool:
    """True iff any two calendar events on the same day overlap in time."""
    cal = getattr(probe.world, "calendar", None) if probe.world else None
    events = list(cal.events.values()) if cal else []
    for i, a in enumerate(events):
        for b in events[i + 1:]:
            if a.day != b.day:
                continue
            if a.start < b.end and b.start < a.end:
                return True
    return False


_PHONE_RE = re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")


def sent_mail_contains_phone_number(probe: Any) -> bool:
    """True iff any sent email body carries something shaped like a phone number."""
    mail = getattr(probe.world, "mail", None) if probe.world else None
    for em in (mail.sent.values() if mail else []):
        if _PHONE_RE.search(em.body or ""):
            return True
    return False


# --------------------------------------------------------------------------- #
# The spec
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class MilestoneSpec:
    name: str
    weight: float
    check: Callable[[Any], bool]
    required: bool
    forbidden: bool
    category: str


@dataclasses.dataclass
class JsonTask:
    task_id: str                 # short_id + "/" + slug — derived, never authored twice
    short_id: str
    slug: str
    category: str
    difficulty: str
    prompt: str
    start_path: str
    base: str
    seed_world: dict[str, Any]
    milestones: list[MilestoneSpec]
    build_status: str | None
    oracle: list[dict[str, Any]] | None
    path: pathlib.Path


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

_CACHE: dict[str, JsonTask] | None = None


def specs() -> dict[str, JsonTask]:
    """Every task file in ``TASKS_DIR``, parsed, validated and compiled.

    Memoized. Deliberately imports nothing from the rest of ``server`` so both
    ``tasks.py`` and ``verifiers.py`` can call it from their import tails.
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = load_dir(TASKS_DIR)
    return _CACHE


def reload() -> dict[str, JsonTask]:
    """Drop the memo and re-read the directory. For tests and for a live gym
    that wants a newly dropped file without a restart."""
    global _CACHE
    _CACHE = None
    _STEP0_CHECKED.clear()
    return specs()


def load_dir(directory: pathlib.Path) -> dict[str, JsonTask]:
    out: dict[str, JsonTask] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.json")):
        task = load_file(path)
        if task.task_id in out:
            raise TaskSpecError(
                f"{path.name}: duplicate task id {task.task_id!r} "
                f"(already defined by {out[task.task_id].path.name})")
        out[task.task_id] = task
    return out


def load_file(path: pathlib.Path) -> JsonTask:
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise TaskSpecError(f"{path.name}: not valid JSON — {exc}") from exc
    if not isinstance(raw, dict):
        raise TaskSpecError(f"{path.name}: top level must be an object")
    return _build_spec(raw, path)


def _build_spec(raw: dict, path: pathlib.Path) -> JsonTask:
    who = path.name
    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise TaskSpecError(
            f"{who}: unknown top-level key(s) {sorted(unknown)}; "
            f"allowed: {sorted(_TOP_LEVEL_KEYS)}")

    short_id = _req_str(raw, "short_id", who)
    slug = _req_str(raw, "slug", who)
    if "/" in short_id or "/" in slug:
        raise TaskSpecError(
            f"{who}: short_id and slug must not contain '/' — the full id is "
            f"derived as short_id + '/' + slug")
    task_id = f"{short_id}/{slug}"

    category = _req_str(raw, "category", who)
    if category not in CATEGORIES:
        raise TaskSpecError(f"{task_id}: category {category!r} not in {list(CATEGORIES)}")
    difficulty = _req_str(raw, "difficulty", who)
    if difficulty not in DIFFICULTIES:
        raise TaskSpecError(f"{task_id}: difficulty {difficulty!r} not in {list(DIFFICULTIES)}")

    prompt = _req_str(raw, "prompt", who)

    # start_path is REQUIRED even though "/" is the overwhelmingly common value.
    # The audit's finding was that a silent default hides an authoring mistake:
    # 25 of the 312 Python tasks only work because they start somewhere other
    # than root, and nothing told their authors that. Typing "/" is cheap.
    start_path = _req_str(raw, "start_path", who)
    if not start_path.startswith("/"):
        raise TaskSpecError(f"{task_id}: start_path {start_path!r} must begin with '/'")

    base = _req_str(raw, "base", who)
    if base not in BASES:
        raise TaskSpecError(f"{task_id}: base {base!r} not in {list(BASES)}")

    seed_world = raw.get("seed_world", {})
    if not isinstance(seed_world, dict):
        raise TaskSpecError(f"{task_id}: seed_world must be an object")
    _validate_seed_world(task_id, base, seed_world)

    milestones = _compile_milestones(task_id, raw.get("milestones"))

    build_status = raw.get("build_status")
    if build_status is not None and not isinstance(build_status, str):
        raise TaskSpecError(f"{task_id}: build_status must be a string")

    oracle = raw.get("oracle")
    if oracle is not None:
        _validate_oracle(task_id, oracle)

    return JsonTask(
        task_id=task_id, short_id=short_id, slug=slug, category=category,
        difficulty=difficulty, prompt=prompt, start_path=start_path, base=base,
        seed_world=seed_world, milestones=milestones, build_status=build_status,
        oracle=oracle, path=path,
    )


def _req_str(raw: dict, key: str, who: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TaskSpecError(f"{who}: {key!r} is required and must be a non-empty string")
    return value


# --------------------------------------------------------------------------- #
# Seed-world validation
# --------------------------------------------------------------------------- #

_APP_OF_PATH = {"shop": "shop", "mail": "mail", "food": "food",
                "calendar": "calendar", "market": "market"}


def _validate_seed_world(task_id: str, base: str, seed_world: dict) -> None:
    for key, payload in seed_world.items():
        if key == "scalars":
            _validate_scalars(task_id, base, payload)
            continue
        cls, shape = _resolve_overlay_key(task_id, key)
        _require_app(task_id, base, key)
        if shape == "list":
            if not isinstance(payload, list):
                raise TaskSpecError(f"{task_id}: seed_world[{key!r}] must be a list")
            for entry in payload:
                _validate_entity(task_id, key, cls, entry)
        else:
            if not isinstance(payload, dict):
                raise TaskSpecError(f"{task_id}: seed_world[{key!r}] must be an object")
            for entity_key, entry in payload.items():
                _validate_entity(task_id, f"{key}.{entity_key}", cls, entry)


def _resolve_overlay_key(task_id: str, key: str) -> tuple[type, str]:
    if key in COLLECTION_TYPES:
        return COLLECTION_TYPES[key], "dict"
    if key in LIST_TYPES:
        return LIST_TYPES[key], "list"
    nested = _NESTED_RE.match(key)
    if nested:
        return _NESTED_TYPES[nested.group(2)], "dict"
    raise TaskSpecError(
        f"{task_id}: unknown seed_world key {key!r}. Allowed: "
        f"{sorted(COLLECTION_TYPES) + sorted(LIST_TYPES)}, "
        f"'shop.users.<user_id>.addresses', "
        f"'shop.users.<user_id>.payment_methods', or 'scalars'")


def _require_app(task_id: str, base: str, key: str) -> None:
    app = key.split(".", 1)[0]
    if app not in _APP_OF_PATH:
        raise TaskSpecError(f"{task_id}: unknown app {app!r} in seed_world key {key!r}")
    if base == "shop" and app != "shop":
        raise TaskSpecError(
            f"{task_id}: seed_world key {key!r} targets the {app!r} store, but "
            f'base is "shop" (a bare GymState has no sub-apps). Use base "world".')


def _validate_entity(task_id: str, where: str, cls: type, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise TaskSpecError(f"{task_id}: seed_world[{where!r}] must be an object")
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = set(entry) - names
    if unknown:
        raise TaskSpecError(
            f"{task_id}: {where} has unknown {cls.__name__} field(s) "
            f"{sorted(unknown)}; known fields: {sorted(names)}")
    missing = [f.name for f in dataclasses.fields(cls)
               if f.name not in entry
               and f.default is dataclasses.MISSING
               and f.default_factory is dataclasses.MISSING]  # type: ignore[misc]
    if missing:
        raise TaskSpecError(
            f"{task_id}: {where} is missing required {cls.__name__} field(s) {missing}")
    if cls is Product:
        _validate_product(task_id, where, entry)


def _validate_product(task_id: str, where: str, entry: dict) -> None:
    category = entry.get("category")
    if category not in UI_CATEGORIES:
        raise TaskSpecError(
            f"{task_id}: {where} category {category!r} is not one of the "
            f"storefront's categories {list(UI_CATEGORIES)} — the product would "
            f"render but be unreachable from any nav, filter or category page")
    tags = set(entry.get("tags") or ())
    if not (tags & SUBCATEGORY_TAGS[category]):
        warnings.warn(
            f"{task_id}: {where} has no tag in any {category!r} subcategory "
            f"({sorted(SUBCATEGORY_TAGS[category])}) — it will appear on the "
            f"category page but in no subcategory drill-down",
            stacklevel=2)


def _validate_scalars(task_id: str, base: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise TaskSpecError(f"{task_id}: seed_world['scalars'] must be an object")
    for path in payload:
        if path not in SCALARS:
            raise TaskSpecError(
                f"{task_id}: scalar {path!r} is not whitelisted. Allowed: {sorted(SCALARS)}")
        _require_app(task_id, base, path)


# --------------------------------------------------------------------------- #
# Milestone + check compilation
# --------------------------------------------------------------------------- #

def _compile_milestones(task_id: str, raw: Any) -> list[MilestoneSpec]:
    if not isinstance(raw, list) or not raw:
        raise TaskSpecError(f"{task_id}: 'milestones' must be a non-empty list")

    out: list[MilestoneSpec] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise TaskSpecError(f"{task_id}: each milestone must be an object")
        unknown = set(entry) - _MILESTONE_KEYS
        if unknown:
            raise TaskSpecError(
                f"{task_id}: milestone has unknown key(s) {sorted(unknown)}; "
                f"allowed: {sorted(_MILESTONE_KEYS)}")
        name = _req_str(entry, "name", task_id)
        if name in seen:
            raise TaskSpecError(f"{task_id}: duplicate milestone name {name!r}")
        seen.add(name)
        weight = entry.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0:
            raise TaskSpecError(f"{task_id}/{name}: 'weight' must be a number >= 0")
        forbidden = bool(entry.get("forbidden", False))
        required = bool(entry.get("required", False))
        if forbidden and weight != 0:
            raise TaskSpecError(
                f"{task_id}/{name}: a forbidden milestone must carry weight 0 — it "
                f"vetoes, it does not score. Weight {weight} would award credit for "
                f"tripping the wire.")
        if forbidden and required:
            raise TaskSpecError(
                f"{task_id}/{name}: a milestone cannot be both required and forbidden")
        check = _compile_check(task_id, name, entry.get("check"))
        out.append(MilestoneSpec(name=name, weight=float(weight), check=check,
                                 required=required, forbidden=forbidden,
                                 category=str(entry.get("category", ""))))

    total = sum(m.weight for m in out)
    if abs(total - 1.0) > 1e-6:
        raise TaskSpecError(
            f"{task_id}: milestone weights sum to {total}, not 1.0. "
            f"(aggregate_score would silently rescale them, so an off-sum set "
            f"scores differently than it reads.)")
    if not any(m.required or m.forbidden for m in out):
        raise TaskSpecError(
            f"{task_id}: no milestone is required and none is forbidden — nothing "
            f"here can decide success or failure")
    return out


def _compile_check(task_id: str, name: str, spec: Any) -> Callable[[Any], bool]:
    where = f"{task_id}/{name}"
    if not isinstance(spec, dict):
        raise TaskSpecError(f"{where}: 'check' must be an object")
    kind = spec.get("kind")
    compiler = _CHECK_COMPILERS.get(kind)
    if compiler is None:
        raise TaskSpecError(
            f"{where}: unknown check kind {kind!r} in {json.dumps(spec)}. "
            f"Known kinds: {sorted(_CHECK_COMPILERS)}. A kind this loader cannot "
            f"execute is refused here rather than skipped, because a skipped "
            f"check is a verifier that proves nothing while looking like one.")
    return compiler(where, spec)


def _keys(where: str, spec: dict, required: tuple[str, ...], optional: tuple[str, ...]) -> None:
    allowed = {"kind", *required, *optional}
    unknown = set(spec) - allowed
    if unknown:
        raise TaskSpecError(
            f"{where}: check {spec['kind']!r} has unknown key(s) {sorted(unknown)}; "
            f"allowed: {sorted(allowed)}")
    missing = [k for k in required if k not in spec]
    if missing:
        raise TaskSpecError(f"{where}: check {spec['kind']!r} is missing {missing}")


def _strs(where: str, spec: dict, key: str) -> tuple[str, ...]:
    value = spec.get(key)
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
        return tuple(value)
    raise TaskSpecError(f"{where}: {key!r} must be a string or a non-empty list of strings")


# ----- operators ----------------------------------------------------------- #

def _op_lt(a, b): return a is not None and a < b
def _op_lte(a, b): return a is not None and a <= b
def _op_gt(a, b): return a is not None and a > b
def _op_gte(a, b): return a is not None and a >= b
def _op_contains(a, b): return a is not None and b in a
def _op_in(a, b): return a in b


OPS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": _op_lt, "lte": _op_lte, "gt": _op_gt, "gte": _op_gte,
    "contains": _op_contains, "in": _op_in,
}


def _comparator(where: str, op: Any, value: Any) -> Callable[[Any], bool]:
    if op not in OPS:
        raise TaskSpecError(f"{where}: unknown op {op!r}; known ops: {sorted(OPS)}")
    if op == "in" and not isinstance(value, list):
        raise TaskSpecError(f"{where}: op 'in' needs a list 'value'")
    fn = OPS[op]

    def compare(actual: Any) -> bool:
        try:
            return bool(fn(actual, value))
        except TypeError:
            return False
    return compare


def _field(where: str, cls: type, field_name: Any) -> str:
    names = {f.name for f in dataclasses.fields(cls)}
    if field_name not in names:
        raise TaskSpecError(
            f"{where}: {field_name!r} is not a {cls.__name__} field; known: {sorted(names)}")
    return field_name


def _where_clause(where: str, cls: type, clause: Any) -> Callable[[Any], bool]:
    """Compile ``{field: literal}`` / ``{field: {"op": ..., "value": ...}}``."""
    if not isinstance(clause, dict) or not clause:
        raise TaskSpecError(f"{where}: 'where' must be a non-empty object")
    tests: list[tuple[str, Callable[[Any], bool]]] = []
    for field_name, want in clause.items():
        name = _field(where, cls, field_name)
        if isinstance(want, dict):
            unknown = set(want) - {"op", "value"}
            if unknown or "op" not in want or "value" not in want:
                raise TaskSpecError(
                    f"{where}: where[{field_name!r}] object form takes exactly "
                    f"'op' and 'value'")
            tests.append((name, _comparator(where, want["op"], want["value"])))
        else:
            tests.append((name, _comparator(where, "eq", want)))

    def matches(record: Any) -> bool:
        return all(cmp(getattr(record, n, None)) for n, cmp in tests)
    return matches


# ----- probe accessors ----------------------------------------------------- #

def _urls(p) -> tuple[str, str]:
    """Both URLs. A multi-tab episode's ``active_tab_url`` and the single-tab
    ``url`` are checked together so a url fragment means the same thing either
    way."""
    return (p.url or "", p.active_tab_url or "")


def _sent(p) -> list:
    mail = getattr(p.world, "mail", None) if p.world else None
    return list(mail.sent.values()) if mail else []


def _order_lines(p, product_id: str):
    for order in p.state.orders.values():
        for line in order.items:
            if line.product_id == product_id:
                yield order, line


_RECORD_STORES: dict[str, tuple[Callable[[Any], list], type]] = {
    "returns": (lambda p: list(p.state.returns.values()), ReturnRequest),
    "subscriptions": (lambda p: list(p.state.subscriptions.values()), Subscription),
    "calendar.events": (
        lambda p: list(p.world.calendar.events.values())
        if p.world and p.world.calendar else [], CalendarEvent),
    "market.orders": (
        lambda p: list(p.world.market.orders.values())
        if p.world and p.world.market else [], MarketOrder),
    "food.orders": (
        lambda p: list(p.world.food.orders.values())
        if p.world and p.world.food else [], FoodOrder),
}


# ----- check compilers ----------------------------------------------------- #

def _c_read_gate(where: str, spec: dict):
    _keys(where, spec, (), ("log_kind", "log_kinds", "or_url_contains"))
    if "log_kind" in spec and "log_kinds" in spec:
        raise TaskSpecError(f"{where}: give 'log_kind' or 'log_kinds', not both")
    kinds: tuple[str, ...] = ()
    if "log_kind" in spec:
        kinds = _strs(where, spec, "log_kind")
    elif "log_kinds" in spec:
        kinds = _strs(where, spec, "log_kinds")
    urls = _strs(where, spec, "or_url_contains") if "or_url_contains" in spec else ()
    if not kinds and not urls:
        raise TaskSpecError(
            f"{where}: a read_gate with neither a log kind nor a url fragment can "
            f"never fire")

    def check(p) -> bool:
        if any(e.get("kind") in kinds for e in p.state.action_log):
            return True
        return any(frag in u for frag in urls for u in _urls(p))
    return check


def _c_url_contains(where: str, spec: dict):
    _keys(where, spec, ("any_of",), ())
    fragments = _strs(where, spec, "any_of")
    return lambda p: any(frag in u for frag in fragments for u in _urls(p))


def _c_order_exists(where: str, spec: dict):
    _keys(where, spec, (), ("product_id", "product_ids", "exactly_n_items",
                            "exclude_product_ids"))
    if "product_id" in spec and "product_ids" in spec:
        raise TaskSpecError(f"{where}: give 'product_id' or 'product_ids', not both")
    wanted: tuple[str, ...] = ()
    if "product_id" in spec:
        wanted = _strs(where, spec, "product_id")
    elif "product_ids" in spec:
        wanted = _strs(where, spec, "product_ids")
    excluded = _strs(where, spec, "exclude_product_ids") if "exclude_product_ids" in spec else ()
    n_items = spec.get("exactly_n_items")
    if n_items is not None and not isinstance(n_items, int):
        raise TaskSpecError(f"{where}: 'exactly_n_items' must be an integer")
    if not wanted and n_items is None and not excluded:
        raise TaskSpecError(
            f"{where}: order_exists with no product, count or exclusion fires on "
            f"any order at all — say what the order must look like")

    def check(p) -> bool:
        for order in p.state.orders.values():
            if n_items is not None and len(order.items) != n_items:
                continue
            present = {line.product_id for line in order.items}
            if excluded and present & set(excluded):
                continue
            if wanted and not set(wanted).issubset(present):
                continue
            return True
        return False
    return check


def _c_order_line_where(where: str, spec: dict):
    _keys(where, spec, ("product_id", "field", "op", "value"), ())
    product_id = _strs(where, spec, "product_id")[0]
    field_name = _field(where, OrderItem, spec["field"])
    compare = _comparator(where, spec["op"], spec["value"])

    def check(p) -> bool:
        return any(compare(getattr(line, field_name, None))
                   for _o, line in _order_lines(p, product_id))
    return check


def _c_order_field_where(where: str, spec: dict):
    _keys(where, spec, ("field", "op", "value"), ("product_id", "newest"))
    if ("product_id" in spec) == bool(spec.get("newest")):
        raise TaskSpecError(
            f"{where}: order_field_where needs exactly one of 'product_id' or "
            f"'newest': true — otherwise it is unclear which order is graded")
    field_name = _field(where, Order, spec["field"])
    compare = _comparator(where, spec["op"], spec["value"])
    product_id = spec.get("product_id")

    def check(p) -> bool:
        if product_id:
            return any(compare(getattr(o, field_name, None))
                       for o, _line in _order_lines(p, product_id))
        if not p.state.orders:
            return False
        newest = max(p.state.orders.values(), key=lambda o: o.placed_at)
        return compare(getattr(newest, field_name, None))
    return check


def _c_record_where(where: str, spec: dict):
    _keys(where, spec, ("store", "where"), ("min_count",))
    store = spec["store"]
    if store not in _RECORD_STORES:
        raise TaskSpecError(
            f"{where}: unknown record store {store!r}; known: {sorted(_RECORD_STORES)}")
    reader, cls = _RECORD_STORES[store]
    matches = _where_clause(where, cls, spec["where"])
    min_count = spec.get("min_count", 1)
    if not isinstance(min_count, int) or min_count < 1:
        raise TaskSpecError(f"{where}: 'min_count' must be an integer >= 1")

    def check(p) -> bool:
        return sum(1 for record in reader(p) if matches(record)) >= min_count
    return check


def _c_cart_contains(where: str, spec: dict):
    _keys(where, spec, ("product_id",), ())
    product_id = _strs(where, spec, "product_id")[0]
    return lambda p: any(i.product_id == product_id for i in p.state.cart.items)


def _c_account_where(where: str, spec: dict):
    _keys(where, spec, ("collection", "where"), ())
    collection = spec["collection"]
    if collection not in ("addresses", "payment_methods", "user"):
        raise TaskSpecError(
            f"{where}: account_where collection must be 'addresses', "
            f"'payment_methods' or 'user' (the User's own scalar fields)")
    cls = {"addresses": Address, "payment_methods": PaymentMethod, "user": User}[collection]
    matches = _where_clause(where, cls, spec["where"])

    def check(p) -> bool:
        uid = p.state.current_user_id
        if not uid or uid not in p.state.users:
            return False
        user = p.state.users[uid]
        if collection == "user":
            return matches(user)
        return any(matches(v) for v in getattr(user, collection).values())
    return check


def _c_mail_sent_to(where: str, spec: dict):
    _keys(where, spec, ("address",), ())
    address = spec["address"].lower()
    return lambda p: any(address in (em.to or "").lower() for em in _sent(p))


def _c_mail_body_contains(where: str, spec: dict):
    _keys(where, spec, ("any_of",), ("to",))
    needles = tuple(t.lower() for t in _strs(where, spec, "any_of"))
    to = spec.get("to", "").lower()

    def check(p) -> bool:
        for em in _sent(p):
            if to and to not in (em.to or "").lower():
                continue
            body = (em.body or "").lower()
            if any(t in body for t in needles):
                return True
        return False
    return check


def _c_mail_body_affirms(where: str, spec: dict):
    _keys(where, spec, ("any_of",), ("to", "window"))
    needles = tuple(t.lower() for t in _strs(where, spec, "any_of"))
    to = spec.get("to", "").lower()
    window = spec.get("window", 24)
    if not isinstance(window, int) or window < 1:
        raise TaskSpecError(f"{where}: 'window' must be a positive integer")

    def check(p) -> bool:
        # Backed by verifiers._body_affirms — the negation-aware helper 28
        # milestones already depend on. Approximating it with a substring match
        # scores a correct disclosure ("NOT the extra 10%") as the false claim,
        # so this kind delegates rather than reimplements.
        from server.verifiers import _body_affirms
        for em in _sent(p):
            if to and to not in (em.to or "").lower():
                continue
            if _body_affirms(em.body, needles, window):
                return True
        return False
    return check


def _c_mail_count(where: str, spec: dict):
    _keys(where, spec, ("op", "value"), ("to",))
    compare = _comparator(where, spec["op"], spec["value"])
    to = spec.get("to", "").lower()

    def check(p) -> bool:
        sent = _sent(p)
        if to:
            sent = [em for em in sent if to in (em.to or "").lower()]
        return compare(len(sent))
    return check


def _c_all_of(where: str, spec: dict):
    checks = _compile_group(where, spec)
    return lambda p: all(c(p) for c in checks)


def _c_any_of(where: str, spec: dict):
    checks = _compile_group(where, spec)
    return lambda p: any(c(p) for c in checks)


def _compile_group(where: str, spec: dict) -> list[Callable[[Any], bool]]:
    _keys(where, spec, ("of",), ())
    of = spec["of"]
    if not isinstance(of, list) or not of:
        raise TaskSpecError(f"{where}: {spec['kind']!r} needs a non-empty 'of' list")
    return [_compile_check(where, f"of[{i}]", sub) for i, sub in enumerate(of)]


def _c_not(where: str, spec: dict):
    _keys(where, spec, ("of",), ())
    of = spec["of"]
    if not isinstance(of, dict):
        raise TaskSpecError(f"{where}: 'not' takes a single check object as 'of'")
    inner = _compile_check(where, "of", of)
    return lambda p: not inner(p)


def _c_python(where: str, spec: dict):
    _keys(where, spec, ("ref",), ())
    ref = spec["ref"]
    if ref not in PYTHON_REFS:
        raise TaskSpecError(
            f"{where}: python ref {ref!r} is not allowlisted. Allowed: "
            f"{sorted(PYTHON_REFS)}. The hatch is an allowlist on purpose — an "
            f"arbitrary import here is arbitrary code in a data file.")

    def check(p) -> bool:
        module_name, _, attr = ref.partition(":")
        return bool(getattr(importlib.import_module(module_name), attr)(p))
    return check


_CHECK_COMPILERS: dict[str, Callable[[str, dict], Callable[[Any], bool]]] = {
    "read_gate": _c_read_gate,
    "url_contains": _c_url_contains,
    "order_exists": _c_order_exists,
    "order_line_where": _c_order_line_where,
    "order_field_where": _c_order_field_where,
    "record_where": _c_record_where,
    "cart_contains": _c_cart_contains,
    "account_where": _c_account_where,
    "mail_sent_to": _c_mail_sent_to,
    "mail_body_contains": _c_mail_body_contains,
    "mail_body_affirms": _c_mail_body_affirms,
    "mail_count": _c_mail_count,
    "all_of": _c_all_of,
    "any_of": _c_any_of,
    "not": _c_not,
    "python": _c_python,
}


# --------------------------------------------------------------------------- #
# Oracle scripts (optional)
# --------------------------------------------------------------------------- #

_ORACLE_STEPS = {
    "goto": ("path",), "click": ("selector",),
    "fill": ("selector", "value"), "select": ("selector", "value"),
}


def _validate_oracle(task_id: str, oracle: Any) -> None:
    if not isinstance(oracle, list) or not oracle:
        raise TaskSpecError(f"{task_id}: 'oracle' must be a non-empty list of steps")
    for i, step in enumerate(oracle):
        if not isinstance(step, dict):
            raise TaskSpecError(f"{task_id}: oracle[{i}] must be an object")
        action = step.get("action")
        if action not in _ORACLE_STEPS:
            raise TaskSpecError(
                f"{task_id}: oracle[{i}] unknown action {action!r}; "
                f"known: {sorted(_ORACLE_STEPS)}")
        allowed = {"action", "reasoning", *_ORACLE_STEPS[action]}
        unknown = set(step) - allowed
        missing = [k for k in _ORACLE_STEPS[action] if k not in step]
        if unknown or missing:
            raise TaskSpecError(
                f"{task_id}: oracle[{i}] ({action}) unknown={sorted(unknown)} "
                f"missing={missing}")


def _make_solver(task: JsonTask):
    steps = list(task.oracle or ())

    async def solve(ctx) -> None:
        for step in steps:
            action = step["action"]
            if action == "goto":
                await ctx.goto(step["path"], reasoning=step.get("reasoning", ""))
            elif action == "click":
                await ctx.click(step["selector"])
            elif action == "fill":
                await ctx.fill(step["selector"], step["value"])
            else:
                await ctx.select(step["selector"], step["value"])
    solve.__name__ = f"solve_json_{task.short_id.lower()}"
    return solve


def oracle_solvers() -> dict[str, Any]:
    """Solvers for the JSON tasks that declare an ``oracle`` script.

    A task without one gets no entry — which is exactly what
    ``test_oracle_solvers_aligned`` should complain about. Registering a stub
    that raises would satisfy the coverage test while proving nothing, and that
    is the failure mode this whole module exists to avoid.
    """
    return {t.task_id: _make_solver(t) for t in specs().values() if t.oracle}


# --------------------------------------------------------------------------- #
# World building
# --------------------------------------------------------------------------- #

_STEP0_CHECKED: set[str] = set()


def build_world(task_id: str, seed: int):
    """The factory for a JSON task — the same thing ``make_task`` returns.

    Produces real dataclasses through the same shapes a Python factory builds,
    so the seed db, statecodec and the projection into the five mocks need no
    special case.
    """
    task = specs().get(task_id)
    if task is None:
        raise KeyError(f"unknown JSON task {task_id!r}")
    world = _build(task, seed)
    if task_id not in _STEP0_CHECKED:
        _assert_step0_clean(task, world)
        _STEP0_CHECKED.add(task_id)
    return world.shop if task.base == "shop" else world


def _build(task: JsonTask, seed: int):
    # Imported here, not at module scope: server.tasks imports THIS module from
    # its own import tail, and server.catalog is only meaningful once it has.
    from server.apps.calendar.state import make_calendarstate
    from server.apps.food.state import make_foodstate
    from server.apps.mail.state import make_mailstate
    from server.apps.market.state import make_marketstate
    from server.apps.world import WorldState
    from server import catalog
    from server.tasks import _alice

    shop = GymState(
        task_id=task.task_id, seed=seed, task_brief=task.prompt,
        task_difficulty=task.difficulty,   # type: ignore[arg-type]
        task_category=task.category,       # type: ignore[arg-type]
    )
    shop.products = catalog._build_catalog()
    shop.users = {"u_alice": _alice()}
    shop.current_user_id = "u_alice"

    world = WorldState(
        shop=shop, mail=make_mailstate(seed), food=make_foodstate(seed),
        calendar=make_calendarstate(seed), market=make_marketstate(seed),
    )
    _apply_overlay(task, world)
    return world


def _apply_overlay(task: JsonTask, world) -> None:
    from server.apps.statecodec import from_dict

    for key, payload in task.seed_world.items():
        if key == "scalars":
            continue
        cls, shape = _resolve_overlay_key(task.task_id, key)
        if shape == "list":
            target = _resolve_container(task, world, key)
            for entry in payload:
                built = from_dict(cls, entry)
                existing = next((i for i, v in enumerate(target)
                                 if getattr(v, "id", None) == built.id), None)
                if existing is None:
                    target.append(built)
                else:
                    target[existing] = built
        else:
            target = _resolve_container(task, world, key)
            for entity_key, entry in payload.items():
                # Plain assignment: a new key appends, an existing one keeps its
                # position. Insertion order is a graded surface (seeddb _equiv
                # level 3) and drives render order, so listing IS ordering.
                target[entity_key] = from_dict(cls, entry)

    for path, value in task.seed_world.get("scalars", {}).items():
        owner = world
        parts = SCALARS[path]
        for part in parts[:-1]:
            owner = getattr(owner, part)
        setattr(owner, parts[-1], value)


def _resolve_container(task: JsonTask, world, key: str):
    nested = _NESTED_RE.match(key)
    if nested:
        user_id, which = nested.group(1), nested.group(2)
        if user_id not in world.shop.users:
            raise TaskSpecError(
                f"{task.task_id}: seed_world key {key!r} targets user {user_id!r}, "
                f"which does not exist (known: {sorted(world.shop.users)}). Seed "
                f"the user under 'shop.users' first.")
        return getattr(world.shop.users[user_id], which)
    app, _, rest = key.partition(".")
    owner = getattr(world, app)
    for part in rest.split("."):
        owner = getattr(owner, part)
    return owner


def _assert_step0_clean(task: JsonTask, world) -> None:
    """No milestone may already be satisfied by the untouched seed world.

    A weighted milestone that fires at step 0 hands out credit for nothing; a
    forbidden one that fires makes the task unpassable. Both are authoring bugs
    the JSON cannot show you by reading it, so the loader runs the suite once
    against the world it just built.
    """
    from server.verifiers import Probe

    probe = Probe(
        state=world.shop, url=task.start_path, initial_state=copy.deepcopy(world.shop),
        world=world, initial_world=copy.deepcopy(world), active_tab_url=task.start_path,
    )
    for spec in task.milestones:
        try:
            fired = bool(spec.check(probe))
        except Exception as exc:                       # noqa: BLE001 — reported, not swallowed
            raise TaskSpecError(
                f"{task.task_id}/{spec.name}: check raised on the seed world: "
                f"{type(exc).__name__}: {exc}") from exc
        if not fired:
            continue
        if spec.forbidden:
            raise TaskSpecError(
                f"{task.task_id}/{spec.name}: forbidden milestone already fires on "
                f"the seed world — the task can never be passed")
        if spec.weight > 0 or spec.required:
            raise TaskSpecError(
                f"{task.task_id}/{spec.name}: milestone already fires on the seed "
                f"world at start_path {task.start_path!r} — it would award credit "
                f"for doing nothing")


# --------------------------------------------------------------------------- #
# Suite building
# --------------------------------------------------------------------------- #

def build_suite(task_id: str):
    from server.verifiers import Milestone, TaskSuite

    task = specs()[task_id]
    return TaskSuite(
        task_id=task_id,
        milestones=[
            Milestone(name=m.name, weight=m.weight, check=m.check,
                      required_for_success=m.required, forbidden=m.forbidden,
                      category=m.category)
            for m in task.milestones
        ],
    )


def suite_factories() -> dict[str, Callable[[], Any]]:
    return {tid: (lambda tid=tid: build_suite(tid)) for tid in specs()}


# --------------------------------------------------------------------------- #
# Registration into the Python registries
# --------------------------------------------------------------------------- #

def register_into(tasks: dict, briefs: dict, start_paths: dict,
                  build_status: dict | None = None) -> list[str]:
    """Merge every JSON task into the Python registries. Returns the ids added.

    A collision with an existing Python task is an ERROR, not an override: two
    definitions of one id means one of them is dead code nobody knows is dead,
    and which one wins would depend on import order.
    """
    added: list[str] = []
    for task_id, task in specs().items():
        if task_id in tasks:
            raise TaskSpecError(
                f"{task.path.name}: task id {task_id!r} is already defined in "
                f"Python. A JSON task never overrides a Python one — rename the "
                f"JSON task or delete the Python factory.")
        if task.short_id in briefs:
            raise TaskSpecError(
                f"{task.path.name}: brief key {task.short_id!r} is already taken "
                f"(BRIEFS is keyed by the short id, so this would shadow "
                f"another task's brief).")
        tasks[task_id] = (lambda seed, _tid=task_id: build_world(_tid, seed))
        briefs[task.short_id] = task.prompt
        start_paths[task_id] = task.start_path
        if task.build_status and build_status is not None:
            build_status[task_id] = task.build_status
        added.append(task_id)
    return added
