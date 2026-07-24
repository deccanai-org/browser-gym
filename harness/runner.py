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
from playwright.async_api import (
    Browser, BrowserContext, Page, Playwright, async_playwright,
)
from harness.auth import harness_headers


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
    "gemini_pixel": {
        "api": "openai_compatible",
        "format": "png",
        "detail": "high",
        "detail_field": "image_url.detail",
        "via": "GeminiPixelAgent",
        "note": "Gemini 3.1 Pro via OpenAI-compatible endpoint",
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
    elif kind in ("gemini", "gemini_pixel"):
        profile_key = "gemini_pixel"
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
    snapshot_after: dict[str, Any]   # /_harness/snapshot (orders_count=Shop;
                                     # market_orders_count=ValueMart)
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
    # Paired with seed_initial.json written into screenshot_dir at reset
    # (before any agent action). Empty if capture failed / not yet run.
    seed_initial_screenshot: str | None = None
    seed_initial_json: str | None = None
    steps: list[StepRecord] = field(default_factory=list)
    final_url: str = ""
    final_snapshot: dict[str, Any] = field(default_factory=dict)
    # Paired with seed_final.json written after episode end (before browser close).
    seed_final_screenshot: str | None = None
    seed_final_json: str | None = None
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
            "seed_initial_screenshot": self.seed_initial_screenshot,
            "seed_initial_json": self.seed_initial_json,
            "steps": [asdict(s) for s in self.steps],
            "final_url": self.final_url,
            "final_snapshot": self.final_snapshot,
            "seed_final_screenshot": self.seed_final_screenshot,
            "seed_final_json": self.seed_final_json,
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

    async def click(self, selector: str, reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "CLICK")
        try:
            await self.page.click(selector)
            # window.open popups may race the opener's load; sync first so
            # wait_for_load_state runs on the popup when one was created.
            await self._sync_context_pages()
            await self.page.wait_for_load_state("load")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "click", {"selector": selector}, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    async def _wait_search_autocomplete_ready(self) -> None:
        """After typing into the header search box, wait for Alpine to open the
        suggestion dropdown (when suggestions exist) instead of a fixed sleep.

        Screenshots taken immediately after ``fill`` / ``type_*`` were often
        missing the dropdown because Alpine's ``x-show`` + opacity transition
        had not committed yet. We wait for either:
          * ``[data-test-id='search-autocomplete']`` visible, or
          * the input still empty / no matching suggestions (timeout → no-op).
        """
        try:
            # Only relevant when the header search input is focused / filled.
            q = await self.page.evaluate(
                """() => {
                  const el = document.querySelector(
                    "[data-test-id='input-header-search']"
                  );
                  return el ? (el.value || "") : null;
                }"""
            )
            if q is None or len(str(q)) < 1:
                return
            await self.page.wait_for_selector(
                "[data-test-id='search-autocomplete']:visible",
                timeout=1500,
                state="visible",
            )
        except Exception:
            pass  # no suggestions / dropdown not applicable — never block

    async def fill(self, selector: str, value: str,
                   reasoning: str = "") -> StepRecord:
        t0 = time.monotonic()
        err: str | None = None
        await self._animate_cursor(selector, "FILL", detail=value)
        try:
            await self.page.fill(selector, value)
            # Header search: wait for autocomplete render before screenshot.
            if "input-header-search" in selector or "search" in selector.lower():
                await self._wait_search_autocomplete_ready()
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
            await self.page.select_option(selector, value=value)
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
            await self.page.check(selector)
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
            await self.page.click(selector)
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
        Anthropic Computer Use semantics. ``key_press`` maps ``Control+a``
        to Playwright ``ControlOrMeta+a`` so select-all works on
        Chromium/macOS (raw Control+a is line-start there).
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
            # If this mark was the header search input, wait for dropdown.
            name_l = (mark.name or "").lower()
            role_l = (mark.role or "").lower()
            if "search" in name_l or role_l == "searchbox":
                await self._wait_search_autocomplete_ready()
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return await self._record(
            "type_into_mark", resolved, reasoning=reasoning,
            error=err, latency_ms=latency_ms,
        )

    @staticmethod
    def _normalize_key_chord(name: str) -> str:
        """Map agent chords to Playwright keys that work cross-platform.

        On Chromium/macOS, raw ``Control+a`` is the emacs "line start" binding
        (caret → 0, no selection). Select-all is ``Meta+a``. Playwright's
        ``ControlOrMeta+a`` emits Meta on macOS and Control elsewhere, which
        is what agents mean when they send ``Control+a`` for overwrite.
        """
        if name in ("Control+a", "Control+A"):
            return "ControlOrMeta+a"
        return name

    async def key_press(self, name: str, reasoning: str = "") -> "StepRecord":
        """Press a keyboard key (or chord) on the focused element.

        Examples: "Enter", "Tab", "Escape", "Backspace", "ArrowDown",
                  "Control+a", "Shift+Tab"
        """
        t0 = time.monotonic()
        err: str | None = None
        press_name = self._normalize_key_chord(name)
        try:
            await self.page.keyboard.press(press_name)
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
            # Best-effort: if focus landed on header search, wait for dropdown.
            await self._wait_search_autocomplete_ready()
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
        if self.extract_facts is not None:
            try:
                world_json = self.http.get(
                    f"{self.server_url}/_harness/world",
                ).json()
                facts = self.extract_facts(world_json, url) or {}
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
        return f"{self.server_url}{path}"


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
                    ui: str = "normal") -> dict[str, Any]:
    """Tell the backend to reset state for this task/seed (+ optional named UI
    perturbation, applied to every page of the episode)."""
    async with httpx.AsyncClient(headers=harness_headers()) as c:
        r = await c.post(
            f"{server_url}/_harness/reset",
            json={"task_id": task_id, "seed": seed, "ui": ui},
        )
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
