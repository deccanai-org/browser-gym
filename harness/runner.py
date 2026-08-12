"""Browser harness — wraps Playwright + the per-step verifier probe.

This is the layer that sits between the agent and the browser. Key
responsibilities:

  1. Launch a real Chromium browser (headed by default — you can WATCH it).
  2. Record video of every episode (saved to ``videos/``).
  3. Take a screenshot after every agent step.
  4. After every step, probe the FastAPI ``/_harness/verify`` endpoint
     to detect newly-fired milestones and capture the running score.
  5. Build a Trajectory record with everything.

The agent doesn't talk to this directly — instead, the agent calls
Playwright methods through a thin wrapper that yields hooks (so we can
intercept after every action). See ``BrowserCtx`` below.

Why per-step probing?
- The score is **monotone** — it only goes up — so probing after each
  action shows exactly when the agent earns each milestone.
- For RL training, this gives a dense reward signal (small reward each
  time a milestone fires, big reward at completion) rather than a
  sparse one (one reward at the end).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from urllib.parse import urlencode, urlsplit, urlunsplit
from playwright.async_api import (
    Browser, BrowserContext, Page, Playwright, async_playwright,
)
from harness.auth import harness_headers

# Milliseconds to let the post-action UI settle before the step screenshot, so a
# freshly-opened dropdown/portal or an SPA route change is actually captured
# (React re-renders + CSS transitions fire no load event). See _record().
_SCREENSHOT_SETTLE_MS = 250


# --------------------------------------------------------------------------- #
# Realistic-UI (bridged) navigation
# --------------------------------------------------------------------------- #
# Each realistic mock (CUA-Gym-Hub Amazon/Gmail/eBay/GCal/UberEats) is its OWN
# origin, unlike the gym's single path-prefixed origin. These maps let the
# harness open the right mock: a gym-style path segment -> app key, and each app
# -> its mock start path. Scoring still goes to the gym /_harness/* — only
# browser navigation is redirected to the mock origins.
#
# The four sub-apps are route-prefixed (/mail, /food, /calendar, /market); the
# shop owns every other top-level segment the gym serves, so those are listed
# here one by one. They used to be covered by a `default="shop"`, which meant an
# unrecognised segment — a renamed route, a typo in a new task's START_PATHS —
# resolved to shop just as confidently as /cart did, and the task ran against
# the wrong primary app with nothing on screen to say so. 70 of the 312 tasks
# start on a shop segment, so this list is load-bearing, not decoration:
# tests/test_seed_projection_strictness.py re-derives it from the live route
# table and fails when a new top-level route is added without one.
_SEG_TO_APP = {
    "mail": "mail", "food": "food", "calendar": "calendar",
    # `valuemart` is the storefront name the mocks use for the market app.
    "market": "market", "valuemart": "market",
    "": "shop", "account": "shop", "browse": "shop", "bulk": "shop",
    "cart": "shop", "catalog": "shop", "category": "shop", "checkout": "shop",
    "deals": "shop", "item": "shop", "items": "shop", "log-in": "shop",
    "login": "shop", "me": "shop", "my-orders": "shop", "order": "shop",
    "orders": "shop", "p": "shop", "product": "shop", "products": "shop",
    "profile": "shop", "returns": "shop", "search": "shop", "shop": "shop",
    "sign-in": "shop", "signin": "shop", "store": "shop", "subs": "shop",
    "subscriptions": "shop",
}
_APP_START_PATH = {"shop": "/", "mail": "/#/inbox", "market": "/",
                   "calendar": "/", "food": "/"}


class UnknownStartPath(ValueError):
    """A start path whose leading segment belongs to no known app."""


def _seg_to_app_or_none(path: str) -> str | None:
    seg = urlsplit(path or "/").path.lstrip("/").split("/")[0].lower()
    return _SEG_TO_APP.get(seg)


def _seg_to_app(path: str) -> str:
    """The app a gym path belongs to. Raises rather than guessing.

    Used to pick a task's PRIMARY app — the tab the agent lands in and the one
    the catalog records — so a wrong answer here mis-files the task for every
    run that follows.
    """
    app = _seg_to_app_or_none(path)
    if app is None:
        seg = urlsplit(path or "/").path.lstrip("/").split("/")[0].lower()
        raise UnknownStartPath(
            f"start path {path!r} begins with {seg!r}, which maps to no app — "
            f"add it to _SEG_TO_APP in harness/runner.py"
        )
    return app


def _app_url(origin: str, app: str, param: dict, start_path: str | None = None) -> str:
    """``origin`` at the app's start path, carrying ``param`` BEFORE any hash so a
    hash-routed SPA (Gmail's /#/inbox) still reads it from location.search."""
    sp = start_path or _APP_START_PATH.get(app, "/")
    if not sp.startswith(("/", "#", "?")):
        sp = "/" + sp
    parts = urlsplit(sp)
    extra = urlencode(param)
    query = f"{parts.query}&{extra}" if parts.query else extra
    return origin.rstrip("/") + urlunsplit(("", "", parts.path or "/", query, parts.fragment))


def bridged_app_url(app_origins: dict, bridge_url: str, app: str,
                    start_path: str | None = None) -> str:
    """Bridged mode: the mock drives the live gym engine via ``?bridge=``."""
    return _app_url(app_origins[app], app, {"bridge": bridge_url}, start_path)


def hosted_app_url(app: str, sid: str, start_path: str | None = None,
                   bridge: str | None = None, session: str | None = None) -> str:
    """Hosted mode: the deployed mock, seeded per ``?sid=``.

    The mock reads its world from the hub for that sid and writes every mutation
    straight back, so the DB is the trajectory.

    Adding ``bridge``/``session`` puts the tab in bridged mode on top of that:
    clicks run through the real gym engine, so cross-app effects and the engine's
    own rules apply, and the re-projected state is still journalled to the hub.
    """
    from tools.cua_env import ui_base
    params = {"sid": sid}
    if bridge:
        params["bridge"] = bridge.rstrip("/")
    if session:
        params["session"] = session
    return _app_url(ui_base(app), app, params, start_path)


def _mock_start_path(app: str, gym_path: str | None) -> str | None:
    """Map a gym deep-link start-path to the realistic mock's equivalent route, so
    a task that starts pre-positioned (a cart, a product, a search) lands there
    instead of the app root. Returns None (-> app start) when there is no SAFE
    equivalent, so an unknown path never breaks rendering."""
    if not gym_path:
        return None
    parts = urlsplit(gym_path)
    p = parts.path.rstrip("/")
    q = ("?" + parts.query) if parts.query else ""
    segs = [s for s in p.split("/") if s]
    if app == "shop":
        if p == "/cart":
            return "/cart"
        if p == "/checkout" or p.startswith("/checkout"):
            return "/checkout"
        if p == "/search":
            return "/search" + q                       # keep ?q= & category
        if len(segs) == 2 and segs[0] == "product":
            return f"/product/{segs[1]}"
        if segs[:2] == ["account", "orders"]:
            # A deep link to ONE order has no mock route (order-confirmation/:id
            # is a different page), so the orders list is the closest safe landing.
            return "/orders"
        if p == "/wishlist":
            return "/wishlist"
        if p == "/account/subscriptions":
            return "/subscriptions"
        # Account settings — including the security page the 2FA tasks start on —
        # all live under the mock's profile route.
        if p in ("/account", "/account/security"):
            return "/profile"
    elif app == "market":                              # gym /market/... -> ebay mock
        if segs[:1] == ["market"]:
            rest = segs[1:]
            if len(rest) == 2 and rest[0] == "product":
                return f"/item/{rest[1]}"
            if rest[:1] == ["cart"]:
                return "/cart"
    elif app == "food":
        if segs[:2] == ["food", "cart"]:
            return "/cart"
        # Gym /food/restaurant/:id → uber mock /store/:id (RedirectToStore).
        if len(segs) == 3 and segs[0] == "food" and segs[1] == "restaurant":
            return f"/store/{segs[2]}"
        if len(segs) == 3 and segs[0] == "food" and segs[1] == "order":
            return f"/orders/{segs[2]}"
        if segs[:2] == ["food", "orders"]:
            return "/orders"
    return None


# --------------------------------------------------------------------------- #
# Pinned image / viewport settings (Section 1C)
# --------------------------------------------------------------------------- #
# Every cascade / eval.run episode must use these capture pins unless an
# explicit override is passed to open_browser. Provider-side detail knobs are
# asymmetric by API surface (OpenAI/Qwen have detail="high"; Anthropic Messages
# has no equivalent) — that asymmetry is recorded, not papered over.

PINNED_VIEWPORT: dict[str, int] = {"width": 1280, "height": 800}
PINNED_DEVICE_SCALE_FACTOR: float = 1.0
PINNED_SCREENSHOT_FORMAT: str = "png"

# Documented provider image-encoding settings. Agents must keep these stable;
# Trajectory.image_settings records which profile applied to the episode.
PROVIDER_IMAGE_SETTINGS: dict[str, dict[str, Any]] = {
    "openai_pixel": {
        "api": "openai",
        "format": "png",
        "detail": "high",
        "detail_field": "image_url.detail / input_image.detail",
    },
    "openai_coord": {
        "api": "openai",
        "format": "png",
        "detail": "high",
        "detail_field": "image_url.detail",
    },
    "qwen_pixel": {
        "api": "openai_compatible",
        "format": "png",
        "detail": "high",
        "detail_field": "image_url.detail",
        "via": "OpenAIPixelAgent",
    },
    "anthropic_pixel": {
        "api": "anthropic_messages",
        "format": "png",
        "detail": None,
        "detail_field": None,
        "note": "Anthropic Messages API has no image detail knob",
    },
    "anthropic_coord": {
        "api": "anthropic_messages",
        "format": "png",
        "detail": None,
        "detail_field": None,
        "note": "Anthropic Messages API has no image detail knob",
    },
    "oracle": {
        "api": None,
        "format": "png",
        "detail": None,
        "detail_field": None,
        "note": "oracle does not send screenshots to a VLM",
    },
    "dom": {
        "api": None,
        "format": "png",
        "detail": None,
        "detail_field": None,
        "note": "DOM agents record screenshots but act on JSON, not pixels",
    },
}


def image_settings_for_agent(agent_kind: str) -> dict[str, Any]:
    """Return the pinned capture + provider encoding profile for an agent kind."""
    kind = (agent_kind or "").strip().lower()
    if kind in ("pixel", "anthropic_pixel"):
        profile_key = "anthropic_pixel"
    elif kind in ("pixel_coord", "anthropic_coord"):
        profile_key = "anthropic_coord"
    elif kind in ("openai_pixel",):
        profile_key = "openai_pixel"
    elif kind in ("openai_coord",):
        profile_key = "openai_coord"
    elif kind in ("qwen", "qwen_pixel"):
        profile_key = "qwen_pixel"
    elif kind == "oracle":
        profile_key = "oracle"
    elif kind in ("llm", "openai", "dom"):
        profile_key = "dom"
    else:
        profile_key = "dom"
    provider = dict(PROVIDER_IMAGE_SETTINGS[profile_key])
    return {
        "viewport": dict(PINNED_VIEWPORT),
        "device_scale_factor": PINNED_DEVICE_SCALE_FACTOR,
        "screenshot_format": PINNED_SCREENSHOT_FORMAT,
        "full_page": False,
        "provider_profile": profile_key,
        "provider": provider,
    }


# --------------------------------------------------------------------------- #
# Step record + Trajectory
# --------------------------------------------------------------------------- #

@dataclass
class StepRecord:
    """One snapshot of agent activity. Captured AFTER each action.

    Enriched fields (added 2026-05) bring our trajectory format closer
    to tau-bench / BrowserGym quality:

      action_error:    explicit Playwright/JS error if the action failed
                       (selector not found, timeout, etc.). None on success.
      action_latency_ms:
                       how long the Playwright operation took to settle
                       (incl. wait_for_load_state). Useful for analyzing
                       slow pages or detecting hangs.
      raw_model_output:
                       the LLM's full response text (incl. thinking, not
                       just the parsed tool_use). Set by the agent layer
                       AFTER the harness creates the StepRecord.
      tokens_in / tokens_out:
                       prompt + completion tokens for this step's LLM
                       call. Cost accounting + training data weighting.

    Note: per-step failure labels were removed. Failure classification is
    a single episode-level summary (`Trajectory.agent_failure_class`)
    produced by ``harness/failure_classifier.classify`` at episode end.
    """
    step_idx: int
    action_kind: str               # "click", "fill", "navigate", "open_tab", ...
    action_args: dict[str, Any]
    url_after: str
    screenshot_path: str | None
    milestones_fired_this_step: list[str]
    running_score: float
    snapshot_after: dict[str, Any]   # /_harness/snapshot (a small SUMMARY: counts + ids)
    # The FULL multi-app world after this step. snapshot_after is only a ~200-byte
    # summary, so it cannot restore state; correcting step N needs the real world
    # AT step N, otherwise the resume replays the run's FINAL world (which already
    # contains the effects of every later step).
    world_after: dict[str, Any] | None = None
    reasoning: str = ""
    action_error: str | None = None
    action_latency_ms: int = 0
    raw_model_output: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    # Environment-truth facts VISIBLE or CREATED at this step, namespaced by
    # app (e.g. {"mail.order_id": "ORD-1042", "mail.tracking_url": "..."}).
    # Populated by a per-task extract_facts hook (see harness/facts.py). This
    # is what lets the harvester detect "the fact was on screen at step k but
    # the agent acted on a wrong value at step k+n" — the root of cross-app
    # failures. Empty for single-app tasks (no extractor wired).
    facts_visible_or_created: dict[str, Any] = field(default_factory=dict)
    # Multi-tab context: which tab was active + the open tab strip after this
    # action. Single-tab episodes record a one-entry strip.
    active_tab: int = 0
    tab_strip: list[dict[str, Any]] = field(default_factory=list)
    # Section 1C pins: encoded PNG size + devicePixelRatio at capture time.
    screenshot_width: int | None = None
    screenshot_height: int | None = None
    device_pixel_ratio: float | None = None


@dataclass
class Trajectory:
    episode_id: str
    task_id: str
    seed: int
    agent_name: str
    started_at: float
    finished_at: float | None = None
    task_brief: str = ""
    task_difficulty: str = ""
    task_category: str = ""
    initial_url: str = ""
    initial_snapshot: dict[str, Any] = field(default_factory=dict)
    steps: list[StepRecord] = field(default_factory=list)
    final_url: str = ""
    final_snapshot: dict[str, Any] = field(default_factory=dict)
    verifier_result: dict[str, Any] = field(default_factory=dict)
    video_path: str = ""
    error: str | None = None
    # Universal failure label (from harness/failure_classifier). None on
    # success. Set once at episode end. This is the queryable, task-
    # agnostic failure key for the trajectory store.
    agent_failure_class: str | None = None
    # Named UI perturbation in effect for this episode ("normal" if none), so
    # the harvester can attribute failures to a variant.
    ui_variant: str = "normal"
    # Two-field sellable label (Phase 4), set once at episode end by
    # finalize_labels(). vein = canonical_vein(task_id) (mechanism family);
    # specific_failure = name of the fired forbidden milestone(s), or None on
    # success / a non-trap failure. Orthogonal to agent_failure_class (the
    # 38-class behavioural label, retained as the capability-only fallback).
    vein: str | None = None
    specific_failure: str | None = None
    # Section 1C: pinned viewport/DPR + provider image-encoding profile for
    # this episode (see image_settings_for_agent / PINNED_*).
    image_settings: dict[str, Any] = field(default_factory=dict)
    # Protocol §3A: infra invalidation (orthogonal to agent_failure_class).
    # When set, cascade.classify must bucket "invalid" — never break/success/
    # incomplete. See harness/invalid_episode.py.
    invalid_reason: str | None = None
    invalid_detail: str | None = None

    def finalize_labels(self) -> None:
        """Set vein + specific_failure from task_id + verifier_result.

        Centralized two-field labeling (Phase 4): every runner that builds a
        Trajectory calls this once at episode end (after agent_failure_class is
        set), so the labeling lives in ONE place — not bolted onto each task
        suite. Idempotent and crash-safe: never lets labeling fail an episode;
        on success, specific_failure stays None."""
        try:
            from harness.failure_classifier import label_episode
            lab = label_episode(self.task_id, self.verifier_result,
                                 fallback_class=self.agent_failure_class)
            self.vein = lab["vein"]
            self.specific_failure = lab["specific_failure"]
        except Exception as e:
            print(f"[trajectory] finalize_labels skipped: {e}")

    def to_json(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id, "seed": self.seed,
            "agent_name": self.agent_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "task_brief": self.task_brief,
            "task_difficulty": self.task_difficulty,
            "task_category": self.task_category,
            "initial_url": self.initial_url,
            "initial_snapshot": self.initial_snapshot,
            "steps": [asdict(s) for s in self.steps],
            "final_url": self.final_url,
            "final_snapshot": self.final_snapshot,
            "verifier_result": self.verifier_result,
            "agent_failure_class": self.agent_failure_class,
            "vein": self.vein,
            "specific_failure": self.specific_failure,
            "ui_variant": self.ui_variant,
            "video_path": self.video_path,
            "error": self.error,
            "image_settings": self.image_settings,
            "invalid_reason": self.invalid_reason,
            "invalid_detail": self.invalid_detail,
        }


def save_trajectory(traj: Trajectory, out_dir: str | Path) -> Path:
    # NOTE: the file is ONE pretty-printed JSON object, not line-delimited JSON,
    # but keeps the `.jsonl` extension on purpose — the whole eval ecosystem
    # (eval/cost_tracker, eval/harvest_failures, run_screen.sh, the annotator's
    # ingest) globs `*.jsonl`, and every reader uses whole-file json.load. Do not
    # rename to `.json` without updating all of those globs.
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_task = traj.task_id.replace("/", "_")
    path = out_dir / f"{safe_task}__{traj.seed}__{traj.episode_id}.jsonl"
    # default=str makes the serializer resilient to unusual values
    # (Path objects, datetime, accidental coroutines, etc.).
    path.write_text(
        json.dumps(traj.to_json(), indent=2, default=str),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# BrowserCtx — the harness instance the agent operates through
# --------------------------------------------------------------------------- #

@dataclass
class BrowserCtx:
    """A thin wrapper that exposes Playwright operations to the agent
    AND hooks our verifier probe / screenshot / trajectory recording
    after every step.

    The agent only needs to call:
        await ctx.goto("/login")
        await ctx.click("input[data-test-id='input-email']")
        await ctx.fill("input[data-test-id='input-email']", "alice@example.com")
        await ctx.click("button[data-test-id='btn-login']")
        ...
    Each call yields one StepRecord with full reward / milestone info.

    If ``show_cursor`` is True (default in headed runs), a ghost cursor
    is animated to each target element BEFORE the underlying Playwright
    action fires, with an action label tooltip. Pure decoration — does
    not affect verifier or trajectory.
    """
    page: Page
    server_url: str
    trajectory: Trajectory
    screenshot_dir: Path
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(
            timeout=30.0, headers=harness_headers(),
        ),
    )
    show_cursor: bool = True
    cursor_pause_ms: int = 450  # how long to linger so the human can see
    # Multi-tab: ``page`` is always the ACTIVE tab; ``pages`` holds every open
    # tab in the one BrowserContext. open/switch/close_tab keep ``page`` in
    # sync. Single-tab episodes leave pages=[page], active_tab=0 — unchanged.
    pages: list = field(default_factory=list)
    active_tab: int = 0
    # Per-task fact extractor: (world_json, active_url) -> {namespaced facts}.
    # None for single-app tasks (then no /_harness/world fetch happens).
    extract_facts: Optional[Callable[[dict, str], dict]] = None
    # Realistic-UI (bridged) mode: when set, browser navigation targets the mock
    # origins (carrying ?bridge=) instead of the gym; scoring still uses
    # server_url (the gym). None -> classic gym-HTML mode (unchanged).
    app_origins: Optional[dict] = None
    bridge_url: Optional[str] = None
    # Hosted mode: {app: attempt_sid}. The deployed mocks are seeded per sid and
    # persist every mutation to cua-gym, so this is the live-server path. Takes
    # precedence over bridge_url when both are set.
    app_sids: Optional[dict] = None

    def _hosted(self) -> bool:
        return bool(self.app_sids)

    def _apps(self) -> list:
        return list(self.app_sids or self.app_origins or {})

    def __post_init__(self) -> None:
        if not self.pages:
            self.pages = [self.page]
        # Track window.open / target=_blank popups that Playwright creates as
        # extra pages in this BrowserContext. Without this, only open_tab()
        # updates ``pages``, so UI popups (e.g. View tracking) never enter the
        # agent-visible tab strip and screenshots stay on the opener.
        self._install_popup_tracking()

    def _install_popup_tracking(self) -> None:
        """Register a BrowserContext 'page' listener (idempotent best-effort)."""
        try:
            context = self.page.context
        except Exception:
            return
        if getattr(self, "_popup_tracking_installed", False):
            return

        def _on_page(new_page: Page) -> None:
            try:
                if new_page in self.pages or new_page.is_closed():
                    return
                self.pages.append(new_page)
                self.active_tab = len(self.pages) - 1
                self.page = new_page
            except Exception:
                pass

        try:
            context.on("page", _on_page)
            self._popup_tracking_installed = True
        except Exception:
            self._popup_tracking_installed = False

    async def _sync_context_pages(self) -> None:
        """Pull any context pages missing from ``pages`` (popup race safety).

        Prefer the newest unmatched page as active so a just-opened tracking
        popup becomes the screenshot surface after the click that spawned it.
        """
        try:
            ctx_pages = list(self.page.context.pages)
        except Exception:
            return
        added = False
        for pg in ctx_pages:
            try:
                if pg.is_closed():
                    continue
            except Exception:
                continue
            if pg not in self.pages:
                self.pages.append(pg)
                added = True
        if added and self.pages:
            self.active_tab = len(self.pages) - 1
            self.page = self.pages[self.active_tab]
            try:
                await self.page.bring_to_front()
            except Exception:
                pass

    # --------- helpers the agent calls ---------
    #
    # Each method wraps the Playwright call in a try/except so a failure
    # (selector missing, timeout, etc.) becomes a FIRST-CLASS field in
    # the StepRecord rather than an unhandled exception. This is the
    # "explicit error capture" pattern from BrowserGym/WorkArena.

    async def _animate_cursor(self, selector: str, kind: str,
                              detail: str = "") -> None:
        """Move ghost cursor to target + flash an action label. Best-effort:
        if the JS isn't loaded yet or the selector doesn't match, silently
        skip so we never break a real action."""
        if not self.show_cursor:
            return
        try:
            # Move ghost cursor
            await self.page.evaluate(
                "(s) => window.__shopgym_cursor && window.__shopgym_cursor.moveTo(s)",
                selector,
            )
            # Show action label
            await self.page.evaluate(
                "(args) => window.__shopgym_cursor && window.__shopgym_cursor.showAction(args.kind, args.detail)",
                {"kind": kind, "detail": detail},
            )
            # Step badge
            step_idx = len(self.trajectory.steps)
            await self.page.evaluate(
                "(args) => window.__shopgym_cursor && window.__shopgym_cursor.setStep(args.step, args.kind)",
                {"step": step_idx, "kind": kind.lower()},
            )
            # Pause so the human sees the animation
            await asyncio.sleep(self.cursor_pause_ms / 1000)
            # Pulse ring on click-like actions
            if kind.upper() in ("CLICK", "SUBMIT"):
                await self.page.evaluate(
                    "() => window.__shopgym_cursor && window.__shopgym_cursor.pulse()"
                )
        except Exception:
            pass  # decoration only — never block on it

    async def goto(self, path: str, reasoning: str = "") -> StepRecord:
        url = self._abs(path)
        t0 = time.monotonic()
        err: str | None = None
        # No cursor animation here — we haven't loaded the new page yet.
        try:
            await self.page.goto(url, wait_until="load")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "navigate", {"url": path}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def _js_activate(self, selector: str, kind: str, value: str | None = None) -> str | None:
        """Reveal a present-but-hidden element and activate it via JS — click (fires
        the handler / follows an <a href> even inside a collapsed menu) or fill (sets
        the value + dispatches input/change so framework bindings update). Returns
        None on success, or a short error only if the element isn't in the DOM. This
        is the harness's 'everything is pickable, no timeouts' fallback."""
        try:
            ok = await self.page.evaluate(
                """([sel, kind, val]) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    try { el.scrollIntoView({block: 'center', inline: 'center'}); } catch (e) {}
                    if (kind === 'fill') {
                        try { el.focus(); } catch (e) {}
                        const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
                        if (d && d.set) d.set.call(el, val); else el.value = val;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    } else if (kind === 'select') {
                        let matched = false;
                        for (const o of (el.options || [])) {
                            if (o.value === val || (o.textContent || '').trim() === val) { el.value = o.value; matched = true; break; }
                        }
                        if (!matched) el.value = val;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    } else if (kind === 'check') {
                        if (!el.checked) { el.checked = true; el.dispatchEvent(new Event('change', {bubbles: true})); }
                    } else {
                        el.click();
                    }
                    return true;
                }""",
                [selector, kind, value],
            )
            return None if ok else f"no element matched {selector}"
        except Exception as e:
            return f"{type(e).__name__}: {e}"

    async def _click_robust(self, selector: str) -> str | None:
        """Click that never hangs: normal click if the element is visible, else
        reveal + JS-click (collapsed menus, transiently-unready targets). Only a
        genuinely absent element returns an error."""
        loc = self.page.locator(selector).first
        try:
            visible = await loc.is_visible()  # instant, no wait
        except Exception:
            visible = False
        if visible:
            try:
                await loc.scroll_into_view_if_needed(timeout=2000)
                await loc.click(timeout=5000)
                return None
            except Exception:
                pass  # intercepted / went stale → fall through to JS
        return await self._js_activate(selector, "click")

    async def click(self, selector: str, reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "CLICK")
        try:
            err = await self._click_robust(selector)
            if err is None:
                # window.open popups may race the opener's load; sync first so
                # wait_for_load_state runs on the popup when one was created.
                await self._sync_context_pages()
                try:
                    await self.page.wait_for_load_state("load", timeout=5000)
                except Exception:
                    pass
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "click", {"selector": selector}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def fill(self, selector: str, value: str,
                   reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "FILL", detail=value)
        try:
            loc = self.page.locator(selector).first
            try:
                visible = await loc.is_visible()
            except Exception:
                visible = False
            if visible:
                try:
                    await loc.fill(value, timeout=5000)
                    err = None
                except Exception:
                    err = await self._js_activate(selector, "fill", value)  # intercepted → JS
            else:
                err = await self._js_activate(selector, "fill", value)  # hidden/absent → reveal + JS
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "fill", {"selector": selector, "value": value},
            reasoning=reasoning, error=err, latency_ms=latency_ms,
        )

    async def select(self, selector: str, value: str,
                     reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "SELECT", detail=value)
        try:
            loc = self.page.locator(selector).first
            try:
                visible = await loc.is_visible()
            except Exception:
                visible = False
            if visible:
                try:
                    await loc.select_option(value=value, timeout=5000)
                    err = None
                except Exception:
                    err = await self._js_activate(selector, "select", value)
            else:
                err = await self._js_activate(selector, "select", value)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "select", {"selector": selector, "value": value},
            reasoning=reasoning, error=err, latency_ms=latency_ms,
        )

    async def check(self, selector: str, reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "CHECK")
        try:
            loc = self.page.locator(selector).first
            try:
                visible = await loc.is_visible()
            except Exception:
                visible = False
            if visible:
                try:
                    await loc.check(timeout=5000)
                    err = None
                except Exception:
                    err = await self._js_activate(selector, "check")
            else:
                err = await self._js_activate(selector, "check")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "check", {"selector": selector}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def submit(self, selector: str,
                     reasoning: str = "") -> StepRecord:
        """Submit a form by clicking a button inside it."""
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "SUBMIT")
        try:
            err = await self._click_robust(selector)
            if err is None:
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "submit", {"selector": selector}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    # ─────────────────────────────────────────────────────────────────
    # Multi-tab actions — the agent juggles tabs like a real person.
    #
    # ``page`` always points at the ACTIVE tab; all the action methods
    # above operate on it, so they keep working unchanged. Tabs live in
    # ONE BrowserContext (shared cookies/session), so the agent stays
    # logged in across tabs — exactly like a real browser. Cross-app
    # tasks (Shop in one tab, Mail in another) are the point.
    # ─────────────────────────────────────────────────────────────────

    async def open_tab(self, path: str, reasoning: str = "") -> StepRecord:
        url = self._abs(path)
        t0 = time.monotonic()
        err: str | None = None
        try:
            new_page = await self.page.context.new_page()
            await new_page.goto(url, wait_until="load")
            # The context 'page' listener may already have appended new_page.
            if new_page not in self.pages:
                self.pages.append(new_page)
            self.active_tab = self.pages.index(new_page)
            self.page = new_page
            await new_page.bring_to_front()
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "open_tab", {"url": path, "tab_index": self.active_tab},
            reasoning=reasoning, error=err, latency_ms=latency_ms,
        )

    async def switch_tab(self, index: int, reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        try:
            if 0 <= index < len(self.pages):
                self.active_tab = index
                self.page = self.pages[index]
                await self.page.bring_to_front()
            else:
                err = (f"ValueError: tab index {index} out of range "
                       f"(0..{len(self.pages) - 1})")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "switch_tab", {"tab_index": index}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def close_tab(self, index: int, reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        try:
            if len(self.pages) <= 1:
                err = "ValueError: cannot close the last remaining tab"
            elif 0 <= index < len(self.pages):
                pg = self.pages.pop(index)
                try:
                    await pg.close()
                except Exception:
                    pass
                self.active_tab = min(self.active_tab, len(self.pages) - 1)
                self.page = self.pages[self.active_tab]
                await self.page.bring_to_front()
            else:
                err = f"ValueError: tab index {index} out of range"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "close_tab", {"tab_index": index}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def _tab_strip(self) -> list[dict[str, Any]]:
        """The open-tabs bar an agent reads off its browser: one entry per
        tab with {index, url, title, active}."""
        strip: list[dict[str, Any]] = []
        for i, pg in enumerate(self.pages):
            try:
                title = await pg.title()
            except Exception:
                title = ""
            strip.append({
                "index": i, "url": pg.url, "title": title,
                "active": i == self.active_tab,
            })
        return strip

    # ─────────────────────────────────────────────────────────────────
    # Mark-based actions (used by the pixel agent — feat/pixel-agent-fork)
    #
    # The pixel agent emits a discrete `mark_id`. The harness resolves
    # that ID to a pixel coordinate (the centre of the mark's bbox) and
    # dispatches via page.mouse / page.keyboard. The agent never sees
    # the resolved coord — it stays inside the harness for diagnostics.
    # ─────────────────────────────────────────────────────────────────

    def _resolve_mark(self, mark_id: int, marks: list) -> Any:
        """Look up a Mark by ID. Returns the Mark or raises ValueError."""
        for m in marks:
            if m.mark_id == mark_id:
                return m
        raise ValueError(
            f"mark_id={mark_id} not in marks list (valid: 1..{len(marks)})"
        )

    async def click_mark(self, mark_id: int, marks: list,
                         reasoning: str = "") -> "StepRecord":
        """Click the centre of the mark identified by mark_id.

        Args:
            mark_id: agent-emitted discrete mark identifier (1..N).
            marks:   the list[Mark] produced by extract_marks() this turn.
            reasoning: agent's natural-language justification.
        """
        t0 = time.monotonic()
        err: str | None = None
        resolved: dict[str, Any] = {"mark_id": mark_id}
        try:
            mark = self._resolve_mark(mark_id, marks)
            resolved.update({
                "role": mark.role, "name": mark.name[:80],
                "coord": list(mark.center),
            })
            await self._animate_cursor_at_coord(
                mark.center, "CLICK", detail=f"{mark.role}:{mark.name[:40]}",
            )
            await self.page.mouse.move(*mark.center)
            await self.page.mouse.click(*mark.center)
            await self._sync_context_pages()
            await self.page.wait_for_load_state("load")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "click_mark", resolved, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def type_into_mark(self, mark_id: int, marks: list, text: str,
                             reasoning: str = "") -> "StepRecord":
        """Click the mark first to focus, then type the given text.

        The clear-first behavior is intentionally NOT included — if the
        agent wants to overwrite existing content it should send
        key('Control+a') + key('Backspace') before typing. This matches
        Anthropic Computer Use semantics.
        """
        t0 = time.monotonic()
        err: str | None = None
        resolved: dict[str, Any] = {"mark_id": mark_id, "value": text}
        try:
            mark = self._resolve_mark(mark_id, marks)
            resolved.update({
                "role": mark.role, "name": mark.name[:80],
                "coord": list(mark.center),
            })
            await self._animate_cursor_at_coord(
                mark.center, "FILL", detail=text,
            )
            await self.page.mouse.click(*mark.center)
            await self.page.keyboard.type(text)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "type_into_mark", resolved, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def key_press(self, name: str, reasoning: str = "") -> "StepRecord":
        """Press a keyboard key (or chord) on the focused element.

        Examples: "Enter", "Tab", "Escape", "Backspace", "ArrowDown",
                  "Control+a", "Shift+Tab"
        """
        t0 = time.monotonic()
        err: str | None = None
        # The eval browser is headless Chromium on Linux, where select-all / copy /
        # paste use Control, not Meta. A model that sends the macOS chord
        # (Cmd/Command/Meta+a) would otherwise no-op — so "select all, then
        # overwrite" silently failed and the agent looped trying to clear a field.
        # Normalize any Meta-family modifier to Control.
        name = "+".join(
            "Control" if p.strip().lower() in ("meta", "cmd", "command", "super", "os")
            else p.strip()
            for p in name.split("+")
        )
        try:
            await self.page.keyboard.press(name)
            # Some keys (Enter on a form) trigger navigation — wait briefly
            if name.lower() in ("enter", "return"):
                try:
                    await self.page.wait_for_load_state(
                        "load", timeout=3000,
                    )
                except Exception:
                    pass
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "key_press", {"key": name}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def scroll_by(self, direction: str, amount_px: int,
                        reasoning: str = "") -> "StepRecord":
        """Scroll the viewport in `direction` by `amount_px` pixels.

        direction: "up" or "down" (left/right not currently needed)
        amount_px: positive integer (typical: 400-800)
        """
        t0 = time.monotonic()
        err: str | None = None
        try:
            dy = amount_px if direction == "down" else -amount_px
            await self.page.mouse.wheel(0, dy)
            # Tiny wait so subsequent screenshot captures the new viewport
            await asyncio.sleep(0.15)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "scroll_by",
            {"direction": direction, "amount_px": amount_px},
            reasoning=reasoning, error=err, latency_ms=latency_ms,
        )

    async def click_xy(self, x: int, y: int,
                       reasoning: str = "") -> "StepRecord":
        """Click at a RAW viewport pixel coordinate. No Set-of-Mark: the agent
        judged this (x, y) from the screenshot itself, so this is where the
        visual-grounding difficulty lives — an off-by-a-bit estimate clicks the
        wrong element (or empty space)."""
        t0 = time.monotonic()
        err: str | None = None
        try:
            await self._animate_cursor_at_coord((x, y), "CLICK",
                                                detail=f"({x},{y})")
            await self.page.mouse.move(x, y)
            await self.page.mouse.click(x, y)
            await self._sync_context_pages()
            await self.page.wait_for_load_state("load")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "click_xy", {"x": int(x), "y": int(y)}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def type_xy(self, x: int, y: int, text: str,
                      reasoning: str = "") -> "StepRecord":
        """Click at a raw (x, y) to focus, then type. Clearing existing content
        is NOT automatic — send key('Control+a') first if needed."""
        t0 = time.monotonic()
        err: str | None = None
        try:
            await self._animate_cursor_at_coord((x, y), "FILL", detail=text)
            await self.page.mouse.click(x, y)
            await self.page.keyboard.type(text)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "type_xy", {"x": int(x), "y": int(y), "value": text},
            reasoning=reasoning, error=err, latency_ms=latency_ms,
        )

    async def _animate_cursor_at_coord(self, coord: tuple[int, int],
                                       kind: str, detail: str = "") -> None:
        """Same as _animate_cursor but for direct pixel coords (no selector).

        The ghost cursor JS exposes a coordinate API too — we use it
        for mark-based actions so the visual feedback still works."""
        if not self.show_cursor:
            return
        try:
            x, y = int(coord[0]), int(coord[1])
            # Move cursor by coord directly (the JS has a moveToCoord helper
            # — if it doesn't exist yet, we just position the existing one
            # by injecting a temporary anchor element. Simpler: do it via JS.)
            await self.page.evaluate(
                """(args) => {
                    const c = document.getElementById('__shopgym_cursor');
                    if (!c) return;
                    c.style.left = args.x + 'px';
                    c.style.top = args.y + 'px';
                    if (window.__shopgym_cursor) {
                        window.__shopgym_cursor.showAction(args.kind, args.detail);
                    }
                    const lbl = document.getElementById('__shopgym_action_label');
                    if (lbl) {
                        lbl.style.left = args.x + 'px';
                        lbl.style.top = (args.y - 30) + 'px';
                    }
                }""",
                {"x": x, "y": y, "kind": kind, "detail": detail},
            )
            step_idx = len(self.trajectory.steps)
            await self.page.evaluate(
                "(args) => window.__shopgym_cursor && window.__shopgym_cursor.setStep(args.step, args.kind)",
                {"step": step_idx, "kind": kind.lower()},
            )
            await asyncio.sleep(self.cursor_pause_ms / 1000)
            if kind.upper() in ("CLICK", "SUBMIT"):
                await self.page.evaluate(
                    "() => window.__shopgym_cursor && window.__shopgym_cursor.pulse()"
                )
        except Exception:
            pass  # decoration only

    # --------- internal: probe + record after each action ---------

    async def tick(self) -> dict[str, Any]:
        """Advance the deterministic async clock to the current step and flush
        any scheduled events now due (emails / price-changes / notifications
        arriving ON TIME). Call at the START of each agent turn, BEFORE the
        screenshot, so the observation reflects events that just arrived — and
        so the verifier never sees an event the screenshot didn't show. No-op
        for single-app tasks (no schedule) or when the clock hasn't moved."""
        step = len(self.trajectory.steps)
        try:
            return self.http.post(
                f"{self.server_url}/_harness/tick", json={"step": step},
            ).json()
        except Exception:
            return {}

    async def wait(self, reasoning: str = "") -> "StepRecord":
        """A 'let time pass' action — wait for an async event (a new email /
        notification) to arrive instead of taking a UI action. Advances the
        clock (flushing any now-due scheduled events) then records a turn. The
        leading tick is what lets the ORACLE advance time (it has no
        turn-start tick like the agent loop does); for the agent it's a
        harmless no-op since the turn already ticked.

        After ticking, RELOAD the active tab so an event the tick just
        delivered server-side (a new email / price change) actually appears in
        the screenshot the agent sees next. Our app pages are server-rendered
        and do NOT live-update, so an agent that sits on a page and waits would
        otherwise never see the arrival — it would wait forever for content it
        structurally cannot see (the rendered page is frozen at navigation
        time). Reloading on `wait` specifically is safe: the agent only waits
        when it has no UI action to take, so there is no in-progress form/scroll
        state to clobber, and it makes 'wait then re-check' actually work."""
        await self.tick()
        try:
            await self.page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        return await self._record("wait", {}, reasoning=reasoning, latency_ms=0)

    async def _record(self, kind: str, args: dict[str, Any],
                      reasoning: str = "",
                      error: str | None = None,
                      latency_ms: int = 0) -> StepRecord:
        step_idx = len(self.trajectory.steps)
        url = self.page.url

        # Screenshot (pinned: viewport PNG, full_page=False)
        shot_path = self.screenshot_dir / f"step_{step_idx:03d}.png"
        shot_w: int | None = None
        shot_h: int | None = None
        dpr: float | None = None
        # Let the POST-action UI settle BEFORE capturing, or the shot catches the
        # PRE-action frame. Two reported failure modes this fixes: (a) a click that
        # opens a dropdown / account menu / portal renders on a later React tick, so
        # an immediate screenshot misses it and the agent loops; (b) an SPA route
        # change (e.g. "Proceed to checkout") swaps the page client-side, so an
        # immediate shot still shows the previous step's button/text. wait_for_load
        # covers real navigations; the short fixed settle covers React re-renders,
        # dropdown mounts and CSS transitions that fire no load event.
        try:
            await self.page.wait_for_load_state("load", timeout=1500)
        except Exception:
            pass
        try:
            await self.page.wait_for_timeout(_SCREENSHOT_SETTLE_MS)
        except Exception:
            pass
        try:
            await self.page.screenshot(path=str(shot_path), full_page=False)
            try:
                from PIL import Image
                with Image.open(shot_path) as im:
                    shot_w, shot_h = im.size
            except Exception:
                pass
            try:
                dpr = float(await self.page.evaluate("() => window.devicePixelRatio"))
            except Exception:
                dpr = None
        except Exception:
            shot_path = None

        # Snapshot + verifier probe
        snap = self.http.get(f"{self.server_url}/_harness/snapshot").json()
        verifier_resp = self.http.post(
            f"{self.server_url}/_harness/verify",
            json={"url": url, "step": step_idx},
        ).json()
        newly = list(verifier_resp.get("newly_fired", []))
        running_score = float(verifier_resp.get("score", 0.0))

        # Per-step facts (cross-app tasks only). Best-effort: a faulty
        # extractor must never break the episode.
        facts: dict[str, Any] = {}
        world_after: dict[str, Any] | None = None
        try:
            world_after = self.http.get(f"{self.server_url}/_harness/world").json()
        except Exception:
            world_after = None
        if self.extract_facts is not None and world_after is not None:
            try:
                facts = self.extract_facts(world_after, url) or {}
            except Exception:
                facts = {}

        try:
            strip = await self._tab_strip()
        except Exception:
            strip = []

        rec = StepRecord(
            step_idx=step_idx,
            action_kind=kind, action_args=args,
            url_after=url,
            screenshot_path=(str(shot_path) if shot_path else None),
            milestones_fired_this_step=newly,
            running_score=running_score,
            snapshot_after=snap,
            world_after=world_after,
            reasoning=reasoning,
            action_error=error,
            action_latency_ms=latency_ms,
            facts_visible_or_created=facts,
            active_tab=self.active_tab,
            tab_strip=strip,
            screenshot_width=shot_w,
            screenshot_height=shot_h,
            device_pixel_ratio=dpr,
        )
        self.trajectory.steps.append(rec)
        return rec

    def _abs(self, path: str) -> str:
        if path.startswith("http"):
            return path
        # Realistic-UI modes: an app-level path (/mail, /food, ...) opens that
        # mock's own origin. Keep the sub-path where the mock has a matching route
        # (a product, a cart) so a deep link lands where it should; _mock_start_path
        # returns None when there's no safe equivalent and we fall back to the app
        # start rather than a 404.
        #
        # This is mid-episode navigation, not task setup: the path comes from
        # whatever the agent asked for, so an unresolvable one is the agent's
        # mistake and must not kill the run. Fall through to the gym origin,
        # which answers with the recoverable 404 page — the lenient lookup here
        # is deliberate, unlike _seg_to_app's, which raises.
        app = _seg_to_app_or_none(path)
        if app is not None:
            if self._hosted():
                if app in self.app_sids:
                    return hosted_app_url(app, self.app_sids[app], _mock_start_path(app, path))
            elif self.app_origins and self.bridge_url:
                if app in self.app_origins:
                    # Match hosted: keep /cart, /product/:id, etc. Dropping the
                    # sub-path here sent every shop goto to "/" and broke oracles
                    # that deep-link mid-episode (mp_059 gift-message cart flow).
                    return bridged_app_url(
                        self.app_origins, self.bridge_url, app,
                        _mock_start_path(app, path),
                    )
        return f"{self.server_url}{path}"

    async def open_app_tabs(self, apps: list[str], primary: str,
                            primary_start_path: str | None = None) -> None:
        """Pre-open one browser tab per realistic app (bridged), ``primary``
        active. Mirrors a person who already has the relevant app tabs open —
        the cross-app substitute for the gym's single-origin app-bar. The agent
        moves between apps with switch_tab (both pixel agents support it). The
        primary tab honors the task's deep-link start-path where the mock has a
        matching route (else the app start)."""
        known = self._apps()
        order = [primary] + [a for a in apps if a != primary and a in known]
        built: list = []
        for i, app in enumerate(order):
            sp = _mock_start_path(app, primary_start_path) if i == 0 else None
            url = (hosted_app_url(app, self.app_sids[app], sp) if self._hosted()
                   else bridged_app_url(self.app_origins, self.bridge_url, app, sp))
            pg = self.page if i == 0 else await self.page.context.new_page()
            try:
                await pg.goto(url, wait_until="load")
            except Exception as e:
                print(f"[runner] WARNING: failed to open {app} tab at {url}: {e}")
            built.append(pg)
        # Assign LAST so the popup-tracking listener's interim mutations don't
        # leave duplicates: this clean list is the source of truth.
        self.pages = built or [self.page]
        self.active_tab = 0
        self.page = self.pages[0]
        try:
            await self.page.bring_to_front()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Harness lifecycle
# --------------------------------------------------------------------------- #

_AGENT_CURSOR_JS_PATH = Path(__file__).resolve().parents[1] / "ui" / "static" / "agent_cursor.js"


async def open_browser(
    *, server_url: str = "http://localhost:8000",
    headless: bool = False, record_video: bool = True,
    videos_dir: str | Path = "videos",
    viewport: dict[str, int] | None = None,
    device_scale_factor: float | None = None,
    inject_cursor: bool = True,
) -> tuple[Playwright, Browser, BrowserContext, Page]:
    """Launch a real Chromium and open one page tab.

    Viewport and deviceScaleFactor default to the Section 1C pins
    (``PINNED_VIEWPORT`` / ``PINNED_DEVICE_SCALE_FACTOR``) so cascade and
    single-run episodes share identical capture geometry unless explicitly
    overridden.

    If ``inject_cursor`` is True (default), the ghost-cursor JS is
    injected into every page in this context via ``add_init_script``.
    This is what makes the red glowing dot and action labels appear so
    a human watching can SEE the agent move.
    """
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=headless)
    vp = dict(viewport or PINNED_VIEWPORT)
    dpr = (
        PINNED_DEVICE_SCALE_FACTOR
        if device_scale_factor is None
        else float(device_scale_factor)
    )
    ctx_kwargs: dict[str, Any] = {
        "viewport": vp,
        "device_scale_factor": dpr,
    }
    if record_video:
        Path(videos_dir).mkdir(parents=True, exist_ok=True)
        ctx_kwargs["record_video_dir"] = str(videos_dir)
        ctx_kwargs["record_video_size"] = ctx_kwargs["viewport"]
    context = await browser.new_context(**ctx_kwargs)
    # No 30s hangs anywhere: cap every action's implicit wait. Interactions also
    # self-heal via a JS fallback (BrowserCtx.click/fill/submit), so an element
    # behind a collapsed menu is revealed + activated instead of timing out — the
    # agent can pick anything, and no run stalls 30s on a single click.
    context.set_default_timeout(6000)

    # Inject the ghost cursor on EVERY page load (incl. after redirects).
    if inject_cursor and _AGENT_CURSOR_JS_PATH.exists():
        try:
            cursor_js = _AGENT_CURSOR_JS_PATH.read_text(encoding="utf-8")
            await context.add_init_script(script=cursor_js)
        except Exception as e:
            print(f"[harness] warning: failed to inject cursor JS: {e}")

    page = await context.new_page()
    return pw, browser, context, page


async def reset_gym(server_url: str, task_id: str, seed: int,
                    ui: str = "normal", brief: str | None = None) -> dict[str, Any]:
    """Tell the backend to reset state for this task/seed (+ optional named UI
    perturbation, applied to every page of the episode). `brief` overrides the
    task instruction ON THE SERVER STATE too, so the in-page brief banner (and
    every screenshot) reflects an annotator's prompt edit."""
    body: dict[str, Any] = {"task_id": task_id, "seed": seed, "ui": ui}
    if brief:
        body["brief"] = brief
    async with httpx.AsyncClient(headers=harness_headers()) as c:
        r = await c.post(f"{server_url}/_harness/reset", json=body)
        r.raise_for_status()
        return r.json()


async def final_verify(server_url: str, url: str, step: int) -> dict[str, Any]:
    async with httpx.AsyncClient(headers=harness_headers()) as c:
        r = await c.post(
            f"{server_url}/_harness/verify",
            json={"url": url, "step": step},
        )
        r.raise_for_status()
        return r.json()
