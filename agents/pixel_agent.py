"""Pixel-based browser agent — sees Set-of-Mark annotated screenshots.

The pixel sibling of ``LLMBrowserAgent``. Same Anthropic Claude
backend, same gym, same verifier, same trajectory schema. Different
perception:

  DOM/JSON agent (llm_agent.py):
      observation = JSON list of [data-test-id] interactables
      action      = click(selector), fill(selector, value), ...

  Pixel/SoM agent (this file):
      observation = annotated screenshot + URL + manifest text
      action      = click(mark_id), type_text(mark_id, text), ...

Why SoM (Set-of-Mark) instead of raw pixel coordinates?
  Holding the VLM constant (Claude Sonnet, no GUI fine-tuning), SoM
  with AX-tree-derived marks substantially outperforms coordinate
  regression on browser tasks. WebVoyager, SeeAct, VisualWebArena all
  use this approach. See PIXEL_VS_JSON.md for the research survey.

Why extended thinking + plan-then-act?
  Multi-turn browser tasks like C4/mega_checkout have 9 milestones and
  ~20 steps. Without explicit planning the agent reacts step-by-step
  and loses the thread. Plan-then-act forces a persistent mental model
  that the agent revises across turns — closer to how a real user
  works through a complex checkout.

Why no `navigate(url)` tool?
  The whole point of the pixel agent is to test pure visual navigation
  — what an agent can do on an unfamiliar UI with no a-priori route
  knowledge. The DOM agent has navigate(); this one doesn't. The
  agent must click its way to every page.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from harness.runner import BrowserCtx
from harness.som import (
    Mark, annotate_image, extract_marks, marks_to_manifest,
)


# --------------------------------------------------------------------------- #
# Tool spec for Claude — discrete, mark-id-based
# --------------------------------------------------------------------------- #

TOOLS_PIXEL = [
    {
        "name": "click",
        "description": (
            "Click the interactable element marked with the given mark_id "
            "in the current screenshot. Use this for buttons, links, "
            "checkboxes, dropdowns, radio buttons — anything you see "
            "marked with a numbered box. The harness resolves the mark "
            "to a coordinate; you only need to pick the number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mark_id": {"type": "integer",
                            "description": "The numbered mark to click."},
                "reason": {"type": "string"},
            },
            "required": ["mark_id"],
        },
    },
    {
        "name": "type_text",
        "description": (
            "Click the marked input element (textbox/searchbox) and type "
            "the given text into it. Does NOT clear existing text first — "
            "if you need to overwrite, send `key` with name='Control+a' "
            "and then key with name='Backspace' before this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mark_id": {"type": "integer",
                            "description": "The textbox/searchbox mark."},
                "text": {"type": "string",
                         "description": "The text to type."},
                "reason": {"type": "string"},
            },
            "required": ["mark_id", "text"],
        },
    },
    {
        "name": "key",
        "description": (
            "Press a keyboard key (or chord). Examples: 'Enter' (submit "
            "form), 'Tab', 'Escape', 'Backspace', 'ArrowDown' (navigate "
            "dropdown options), 'Control+a' (select all)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scroll",
        "description": (
            "Scroll the viewport up or down by the given pixel amount. "
            "Use this when the marks you need are not visible — content "
            "below the fold (related products, full review list, etc.) "
            "needs to be scrolled into view before it can be marked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]},
                "amount_px": {"type": "integer",
                              "description": "Typical: 400-800 pixels."},
                "reason": {"type": "string"},
            },
            "required": ["direction", "amount_px"],
        },
    },
    {
        "name": "open_tab",
        "description": (
            "Open an APP in a NEW browser tab and switch to it. `url` is an "
            "app root: '/' (Shop), '/mail' (Mail), '/food' (Food), "
            "'/calendar' (Calendar), '/market' (Xbay, a second store). "
            "Your old tab stays exactly where it was — use this to keep one "
            "app open while you read another."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"},
                           "reason": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "switch_tab",
        "description": (
            "Make an already-open tab active by its index (see the open "
            "tabs list in the observation). Use this to flip BACK to a tab "
            "you opened earlier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"index": {"type": "integer"},
                           "reason": {"type": "string"}},
            "required": ["index"],
        },
    },
    {
        "name": "close_tab",
        "description": "Close an open tab by its index.",
        "input_schema": {
            "type": "object",
            "properties": {"index": {"type": "integer"},
                           "reason": {"type": "string"}},
            "required": ["index"],
        },
    },
    {
        "name": "wait",
        "description": (
            "Let time pass WITHOUT a UI action — use this to wait for something "
            "to arrive that you cannot make happen yourself (a new email, a "
            "notification, a price/coupon update). After waiting, re-check the "
            "relevant tab (e.g. switch to Mail) to see if it arrived."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "finish",
        "description": (
            "End the episode. Call this ONLY after verifying that the "
            "task goal is fully achieved (e.g. confirmation page is "
            "visible, order ID is shown, all required milestones in your "
            "plan are marked done)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": [],
        },
    },
]


# --------------------------------------------------------------------------- #
# System prompt — plan-then-act, no DOM language, no selectors
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are operating a web browser to complete an e-commerce task on the
Xmazon site. You see the page through a SCREENSHOT — the same view
a human would see — annotated with numbered colored boxes around every
interactable element (buttons, links, inputs, dropdowns).

═══════════════════════════════════════════════════════════════════════════
HOW YOU SEE THE PAGE
═══════════════════════════════════════════════════════════════════════════

Each turn I give you:
  1. An annotated screenshot of the current page (1280×800 viewport)
  2. The current URL
  3. A text manifest listing each numbered mark: `[N] role "name"`
  4. The task brief (your goal)
  5. The result of your last action (if any)

The numbered boxes are colored by role:
  • BLUE        = button (click to perform an action)
  • TEAL        = link (click to navigate)
  • ORANGE      = textbox / searchbox (type into)
  • PURPLE      = combobox / select dropdown (click to open, then click an option)
  • EMERALD     = checkbox / radio / switch (click to toggle)
  • AMBER       = tab (click to switch view)

Mark IDs are 1..N, ordered top-to-bottom-left-to-right. **They are
re-numbered every turn** — mark 7 last turn may be mark 3 now. Always
read the current image, never assume continuity.

═══════════════════════════════════════════════════════════════════════════
HOW YOU ACT
═══════════════════════════════════════════════════════════════════════════

You have five tools, all reference mark IDs (never coordinates):

  click(mark_id)
      Click button/link/checkbox/dropdown-opener.
  type_text(mark_id, text)
      Click textbox + type text. Doesn't clear first.
  key(name)
      Press a key. Examples: "Enter" (submit), "Tab", "Escape",
      "Backspace", "ArrowDown", "Control+a".
  scroll(direction, amount_px)
      Scroll viewport. Use when you need to see marks below the fold.
  finish(reason)
      End the episode. Only when goal is confirmed achieved.

There is NO `navigate(url)` tool. You must reach every page by
clicking visible links — exactly like a human on an unfamiliar site.

There is NO `select_option` for dropdowns. Click the dropdown to
open it, then in the next turn click the option you see.

═══════════════════════════════════════════════════════════════════════════
RESPONSE STRUCTURE — plan-then-act, every single turn
═══════════════════════════════════════════════════════════════════════════

Every visible response (after your private thinking) MUST contain
three sections in this order:

  ## Plan
  Numbered list of steps toward the goal. Mark each as [done] /
  [in progress] / [next] / [later]. REVISE this plan as new
  information arrives — don't just rebuild it from scratch each turn,
  amend the existing plan. Always anchor it to the original task
  brief verbatim.

  ## What I see now
  Brief description of the visible page. Reference specific mark
  numbers when relevant: "the green Add to Cart button is mark 23".
  Note any flash banners (red = error, green = success). If you see
  a confirmation page, an error, or unexpected content, call it out.

  ## Next action
  One tool_use block. Just one action per turn.

═══════════════════════════════════════════════════════════════════════════
PATTERNS YOU WILL NEED
═══════════════════════════════════════════════════════════════════════════

Form filling:
  - type_text(mark_id, text) clicks-then-types — one call is enough.
  - To overwrite existing text: key("Control+a") → key("Backspace") →
    type_text(mark_id, new_text)
  - Spinbutton (number input): same pattern — click, Control+a, type
    the new number. For increment-only changes, key("ArrowUp") works.

Dropdown selection — TWO KINDS, pick the right pattern:

  CUSTOM dropdown (most app menus, the "More ▾" nav, "Account &
  Lists" dropdown): clicking the opener REVEALS new option marks in
  the DOM, so:
      Turn N:   click(opener_mark)
      Turn N+1: new option marks appear; click the option you want.

  NATIVE <select> combobox (the OS-rendered list; you'll see roles
  like "combobox" with a small ▼ chevron, e.g. the cadence /
  address / payment dropdowns on subscription forms): clicking it
  opens an OS-native option list that does NOT appear in your
  screenshot as new marks. But you do NOT need to open it to know the
  choices: the mark's manifest line lists them as
  `options: A | B | *C | …` (the `*` marks the current selection). Read
  that list, then pick with keyboard cycling — you already know how many
  steps and in which direction:
      Step 1: click(combobox_mark)  — focuses the control
      Step 2: key("ArrowDown")/key("ArrowUp") — advances/rewinds one
                                       option; the displayed value updates
      Step 3: repeat until the combobox shows the option you read in the
                                       manifest
      Step 4: optional key("Enter") to confirm focus elsewhere
  Don't wait for option MARKS on a native combobox — they never appear;
  use the `options:` list in the manifest instead.

Form submission:
  - Either: click(submit_button_mark)
  - Or:     key("Enter") when focused inside the form

Recovering from errors:
  - If a flash-error banner is visible in the screenshot, READ IT.
    It tells you what went wrong (e.g. "Please pick an option for
    Cotton T-Shirt" means you forgot variant selection).
  - If nothing visible changed after your last action, your click
    may have missed. Re-examine the screenshot before retrying.

Scrolling:
  - If no mark matches what you need, the target is likely below the
    fold. Scroll down 600px and re-examine.

Looking for "missing" buttons:
  - Sometimes pages have collapsible sections (e.g. "More options ▾",
    "Gift options" inside <details>). If you expected a button and
    don't see it, look for a small ▾ or ▶ chevron — it may be hiding
    inside a closed disclosure. Click the chevron mark first to expand.
  - Each interactable card (subscription, order, address) usually has
    its own action buttons (Cancel, Edit, View, Return) attached
    directly to the card. They'll be marks on the card itself.

═══════════════════════════════════════════════════════════════════════════
WHEN TO CALL finish
═══════════════════════════════════════════════════════════════════════════

ONLY when:
  1. Your Plan shows every step as [done]
  2. The visible page confirms the outcome (e.g. order confirmation
     page with an order ID, "subscription created" page, return
     confirmation, etc.)

Premature finish() loses points. If unsure, take one more action to
verify.

═══════════════════════════════════════════════════════════════════════════

The task brief is your goal. Read it literally. If it says "Home
address" use Home, not Work. If it says "size M Black" pick exactly
that variant. If it says "under $550", check the running subtotal.

═══════════════════════════════════════════════════════════════════════════
MULTI-APP WORKSPACE + BROWSER TABS
═══════════════════════════════════════════════════════════════════════════

At the very top of every page is a dark workspace bar with marks for
several apps: Shop, Mail, Food, and Calendar. Some tasks span apps — e.g.
place an order in the Shop, then read the confirmation email in Mail; or
check the Calendar for free/busy before booking something.

You have THREE extra tools for tabs (in addition to the five above):
  open_tab(url)     open an app in a NEW tab and switch to it. `url` is an
                    app ROOT: "/" (Shop), "/mail" (Mail), "/food" (Food),
                    "/calendar" (Calendar), "/market" (Xbay, 2nd store).
  switch_tab(index) make an already-open tab active (see the open-tabs list).
  close_tab(index)  close a tab.

Each turn the observation lists your open tabs as {index, url, title,
active}. Use tabs like a person on a multi-app task: keep the Shop in
tab 0, OPEN MAIL IN A SECOND TAB to read a confirmation email, then
switch_tab(0) BACK to the Shop to act on it. (open_tab is the ONE exception
to "no navigation" — it only opens an app root in a new tab; WITHIN a tab
you still navigate by clicking marks.)

CARRY VALUES ACCURATELY across tabs (an order number, a charged total, an
ETA). Read them off the OTHER app's screenshot — never invent or guess a
value. If a task needs the exact total you were charged, OPEN and READ the
email; the sticker price on the product is NOT the charged total.
"""


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #

class PixelBrowserAgent:
    """An Anthropic-backed pixel/SoM browser agent.

    Pass ``model`` to override the default (Claude Sonnet 4.5).
    Set ANTHROPIC_API_KEY in the environment.
    """

    def __init__(self, model: str | None = None, max_steps: int | None = None,
                 verbose: bool = True, thinking_budget: int = 4000,
                 eval_mode: bool | None = None):
        from anthropic import Anthropic
        # Explicit finite per-request timeout + NO opaque SDK-internal retries:
        # our _llm_retry.acall wrapper is the single retry authority, so a stuck
        # call is bounded and surfaces as an error instead of freezing the batch.
        from agents._llm_retry import _env_float, _env_int
        self.client = Anthropic(
            timeout=_env_float("LLM_CALL_TIMEOUT", 120.0),
            max_retries=0,
        )
        self.model = model or os.getenv(
            "ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929",
        )
        self.max_steps = (max_steps if max_steps is not None
                          else int(os.getenv("AGENT_MAX_STEPS", "50")))
        self.verbose = verbose
        self.thinking_budget = thinking_budget
        # No reward leakage in benchmark runs (AGENT_EVAL_MODE=1): strip
        # milestone names + running score from the agent's observation. The
        # trajectory still records them for grading.
        self.eval_mode = (eval_mode if eval_mode is not None
                          else os.getenv("AGENT_EVAL_MODE", "0") == "1")
        # DYNAMIC context guard (see openai_pixel_agent) — end the episode before the
        # accumulated screenshots overflow the model window, using measured
        # input_tokens. Default 190000 (Sonnet 4.6 = 200K); per-tier via env.
        self.context_budget = int(os.getenv("LLM_CONTEXT_BUDGET", "190000"))

    async def run(self, ctx: BrowserCtx, task_brief: str) -> None:
        messages: list[dict[str, Any]] = []
        last_action_result: str = ""
        last_prompt_tokens = 0        # measured context size of the previous turn
        # The tool_result for the PREVIOUS action, carried forward and merged
        # into the NEXT turn's user message so the assistant tool_use is
        # immediately followed by a single user message that STARTS with its
        # tool_result (required by extended-thinking + tool-use validation).
        pending_tool_result: dict[str, Any] | None = None

        for turn in range(self.max_steps):
            # DYNAMIC context guard — stop before the next turn overflows the window.
            if last_prompt_tokens >= self.context_budget:
                if self.verbose:
                    print(f"[pixel_agent] context budget reached "
                          f"({last_prompt_tokens} >= {self.context_budget}); "
                          f"ending episode at turn {turn} to avoid overflow.")
                break
            # ─── TICK the async clock BEFORE observing, so any event scheduled
            # for this step (a new email / price change / coupon flip) has
            # arrived and shows up in the screenshot the agent is about to act
            # on. Without this, scheduled events never fire for this agent. ───
            await ctx.tick()
            # ─── OBSERVE: capture screenshot, extract marks, annotate ───
            marks = await extract_marks(ctx.page)
            raw_png = await ctx.page.screenshot(full_page=False)
            annotated_png = annotate_image(raw_png, marks)
            manifest = marks_to_manifest(marks)
            b64 = base64.standard_b64encode(annotated_png).decode("ascii")

            url = ctx.page.url
            try:
                tabs = await ctx._tab_strip()
            except Exception:
                tabs = []
            user_text = (
                f"URL: {url}\n"
                f"Open tabs: {json.dumps(tabs)}\n"
                f"Task: {task_brief}\n"
                f"\n"
                f"Visible marks ({len(marks)}):\n{manifest}\n"
                f"\n"
                f"Last action result: {last_action_result or '(this is your first turn)'}"
            )

            content_blocks: list[dict[str, Any]] = []
            # The previous action's tool_result MUST be the first block of the
            # user turn that follows the assistant's tool_use.
            if pending_tool_result is not None:
                content_blocks.append(pending_tool_result)
                pending_tool_result = None
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            })
            content_blocks.append({"type": "text", "text": user_text})
            messages.append({"role": "user", "content": content_blocks})

            # ─── THINK + ACT: call Claude with extended thinking ───
            from agents._llm_retry import acall, LLMCallError
            # Build kwargs so the SONNET path stays byte-identical while Opus 4.8+
            # uses its NEW thinking API. Opus 4.8 REPLACED thinking.type="enabled"
            # +budget_tokens with ADAPTIVE thinking controlled by output_config.effort;
            # sending the old shape 400s ("thinking.type.enabled not supported for this
            # model"). Gated on "opus" so the concurrent 4-cut's Sonnet-4.6 episodes
            # get the IDENTICAL create() call they got before this edit.
            _create_kw = dict(
                model=self.model,
                max_tokens=8000,          # > thinking budget, leaves room
                system=SYSTEM_PROMPT + f"\n\n## TASK\n\n{task_brief}",
                tools=TOOLS_PIXEL,
                messages=messages,
            )
            if "opus" in (self.model or "").lower():
                _create_kw["thinking"] = {"type": "adaptive"}
                # "medium" = fair moderate effort; mirrors Sonnet's budget_tokens=4000
                # and gpt-5.6-sol's default reasoning (not cranked to bias the flagship)
                _create_kw["output_config"] = {"effort": "medium"}
            else:
                _create_kw["thinking"] = {"type": "enabled",
                                          "budget_tokens": self.thinking_budget}
            try:
                resp = await acall(
                    lambda: self.client.messages.create(**_create_kw),
                    label="pixel",
                    verbose=self.verbose,
                )
            except LLMCallError:
                # Hard failure after timeout + bounded retries. Let it propagate
                # so eval/run.py records traj.error — a stuck call must surface as
                # an error, never a silent freeze.
                raise
            except Exception as e:
                if self.verbose:
                    print(f"[pixel_agent] API error: {type(e).__name__}: {e}")
                    # Dump the message structure so we can see the exact
                    # tool_use/tool_result pairing that the API rejected.
                    for i, mm in enumerate(messages):
                        types = [b.get("type") for b in mm["content"]] \
                            if isinstance(mm["content"], list) else ["<str>"]
                        ids = [b.get("id") or b.get("tool_use_id") or ""
                               for b in mm["content"]] \
                            if isinstance(mm["content"], list) else [""]
                        print(f"   msg[{i}] {mm['role']}: {list(zip(types, ids))}")
                break

            # measured context size of THIS turn — feeds the context guard next turn
            last_prompt_tokens = int(getattr(getattr(resp, "usage", None),
                                             "input_tokens", 0) or 0)

            # ─── PARSE the response ───
            tool_call = None
            tool_use_id = None
            text_parts: list[str] = []
            thinking_text: str = ""
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "thinking":
                    # Extended-thinking block — capture for trajectory
                    thinking_text = getattr(block, "thinking", "")
                elif btype == "text":
                    text_parts.append(block.text)
                elif btype == "tool_use" and tool_call is None:
                    tool_call = {
                        "name": block.name,
                        "input": dict(block.input or {}),
                    }
                    tool_use_id = block.id

            visible_text = "\n".join(text_parts)
            raw_model_output = (
                (f"<thinking>\n{thinking_text}\n</thinking>\n\n" if thinking_text else "")
                + visible_text
            )

            # Persist the assistant turn for conversation continuity, keeping
            # thinking blocks (Anthropic requires them passed back to maintain
            # tool_use context) but TRUNCATING at the first tool_use. With
            # extended thinking Claude sometimes emits MULTIPLE parallel
            # tool_use blocks in one turn; we only dispatch + answer the first,
            # so any extra tool_use would be left without a matching
            # tool_result and the next request 400s. One action per turn.
            assistant_content: list[dict[str, Any]] = []
            for b in resp.content:
                assistant_content.append(self._serialize_block(b))
                if getattr(b, "type", None) == "tool_use":
                    break
            messages.append({"role": "assistant", "content": assistant_content})

            if tool_call is None:
                if self.verbose:
                    print(f"[pixel_agent] no tool call. visible={visible_text[:200]!r}")
                break

            kind = tool_call["name"]
            args = tool_call["input"]
            if self.verbose:
                print(f"[pixel_agent] step {turn}: {kind}({json.dumps(args)[:120]})")

            # ─── DISPATCH the tool to BrowserCtx ───
            try:
                step_record = None
                if kind == "click":
                    step_record = await ctx.click_mark(
                        mark_id=int(args["mark_id"]),
                        marks=marks,
                        reasoning=args.get("reason", ""),
                    )
                elif kind == "type_text":
                    step_record = await ctx.type_into_mark(
                        mark_id=int(args["mark_id"]),
                        marks=marks,
                        text=args["text"],
                        reasoning=args.get("reason", ""),
                    )
                elif kind == "key":
                    step_record = await ctx.key_press(
                        name=args["name"],
                        reasoning=args.get("reason", ""),
                    )
                elif kind == "scroll":
                    step_record = await ctx.scroll_by(
                        direction=args["direction"],
                        amount_px=int(args["amount_px"]),
                        reasoning=args.get("reason", ""),
                    )
                elif kind == "open_tab":
                    step_record = await ctx.open_tab(
                        args["url"], reasoning=args.get("reason", ""))
                elif kind == "switch_tab":
                    step_record = await ctx.switch_tab(
                        int(args["index"]), reasoning=args.get("reason", ""))
                elif kind == "close_tab":
                    step_record = await ctx.close_tab(
                        int(args["index"]), reasoning=args.get("reason", ""))
                elif kind == "wait":
                    step_record = await ctx.wait(reasoning=args.get("reason", ""))
                elif kind == "finish":
                    if self.verbose:
                        print(f"[pixel_agent] finishing: {args.get('reason', '')}")
                    break
                else:
                    raise ValueError(f"unknown tool {kind}")

                # Decorate the StepRecord with reasoning + token info
                if step_record is not None:
                    step_record.raw_model_output = raw_model_output[:4000]
                    if hasattr(resp, "usage") and resp.usage:
                        step_record.tokens_in = int(getattr(resp.usage, "input_tokens", 0) or 0)
                        step_record.tokens_out = int(getattr(resp.usage, "output_tokens", 0) or 0)

                # Build a concise result string for the next turn's user message
                if step_record is None:
                    last_action_result = "(no record)"
                elif step_record.action_error:
                    last_action_result = (
                        f"ERROR: {step_record.action_error}. "
                        f"URL is now {step_record.url_after}."
                    )
                elif self.eval_mode:
                    # Benchmark mode: do NOT leak milestone names / score.
                    last_action_result = (
                        f"OK ({kind}). URL is now {step_record.url_after}."
                    )
                else:
                    last_action_result = (
                        f"OK ({kind}). URL is now {step_record.url_after}. "
                        f"Newly fired milestones: "
                        f"{step_record.milestones_fired_this_step or '[]'}. "
                        f"Running score: {step_record.running_score:.2f}."
                    )
            except Exception as e:
                last_action_result = (
                    f"DISPATCH ERROR: {type(e).__name__}: {e}"
                )
                if self.verbose:
                    print(f"[pixel_agent] dispatch error: {last_action_result}")

            # Stash the tool_result; it is merged into the NEXT turn's user
            # message (as its first block) instead of being a SEPARATE user
            # message. Two consecutive user messages (tool_result, then the
            # observation) intermittently tripped a 400 "tool_use ids were
            # found without tool_result blocks immediately after" under
            # extended thinking — a harness bug that mislabeled clean episodes
            # as agent failures.
            pending_tool_result = {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": last_action_result,
            }

    @staticmethod
    def _serialize_block(block: Any) -> dict[str, Any]:
        """Convert an Anthropic content block (Pydantic model) to the
        plain dict shape needed for sending back into messages."""
        btype = getattr(block, "type", None)
        if btype == "thinking":
            return {
                "type": "thinking",
                "thinking": getattr(block, "thinking", ""),
                "signature": getattr(block, "signature", ""),
            }
        if btype == "text":
            return {"type": "text", "text": getattr(block, "text", "")}
        if btype == "tool_use":
            return {
                "type": "tool_use",
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": dict(getattr(block, "input", {}) or {}),
            }
        # Fallback — return whatever shape is present
        return {"type": btype or "unknown"}
