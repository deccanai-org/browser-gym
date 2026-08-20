"""Raw pixel-COORDINATE browser agent — no Set-of-Mark.

The hard sibling of PixelBrowserAgent. Same Claude backend, same gym, same
verifier, same trajectory schema — but the observation is a PLAIN screenshot
with NO numbered marks and NO accessibility manifest, and the agent acts by
emitting raw viewport coordinates:

  SoM agent (pixel_agent.py):  sees numbered boxes, acts via click(mark_id)
  COORD agent (this file):     sees a bare screenshot, acts via click_at(x, y)

Why: Set-of-Mark hands the agent the answer to "where do I click?" (the
accessibility tree, as numbered boxes). That removes the #1 failure surface of
real browser agents — visual grounding. This agent puts it back: the model
must judge each target's pixel location itself, so an off-by-a-bit estimate
clicks the wrong element or empty space. This is where even frontier models
miss (SeeAct, WebVoyager), and the regime where shrinking/crowding buttons
(tim's hypothesis) actually bites.

No `navigate(url)` within a tab (visual navigation only); `open_tab` opens an
app root in a new tab, mirroring the SoM agent so multi-app tasks still work.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from harness.runner import BrowserCtx


# --------------------------------------------------------------------------- #
# Tool spec — raw (x, y) coordinates, no mark ids
# --------------------------------------------------------------------------- #

TOOLS_COORD = [
    {
        "name": "click_at",
        "description": (
            "Click at a pixel coordinate in the current screenshot. The "
            "viewport is 1280 wide x 800 tall, origin (0,0) at TOP-LEFT, x "
            "increases rightward, y downward. Aim at the CENTER of the element "
            "you want (button, link, checkbox, dropdown, tab). The click lands "
            "exactly at (x, y) — if you miss the element you hit whatever is "
            "under that pixel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "0-1280, from left."},
                "y": {"type": "integer", "description": "0-800, from top."},
                "reason": {"type": "string"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "type_at",
        "description": (
            "Click at (x, y) to focus an input, then type the text. Does NOT "
            "clear existing content first — send key('Control+a') then "
            "key('Backspace') first if you need to overwrite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "text": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["x", "y", "text"],
        },
    },
    {
        "name": "key",
        "description": (
            "Press a keyboard key or chord: 'Enter' (submit), 'Tab', "
            "'Escape', 'Backspace', 'ArrowDown', 'Control+a'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"},
                           "reason": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "scroll",
        "description": (
            "Scroll the viewport up or down by a pixel amount (typical "
            "400-800). Use when the element you need is below/above the fold."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]},
                "amount_px": {"type": "integer"},
                "reason": {"type": "string"},
            },
            "required": ["direction", "amount_px"],
        },
    },
    {
        "name": "open_tab",
        "description": (
            "Open an APP in a NEW tab and switch to it. `url` is an app root: "
            "'/' (Shop), '/mail' (Mail), '/food' (Food), '/calendar' "
            "(Calendar), '/market' (Xbay, a second store). Your old tab "
            "stays where it was."
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
        "description": "Make an already-open tab active by its index.",
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
            "Let time pass WITHOUT taking a UI action — use this to wait for "
            "something to arrive that you cannot make happen yourself (a new "
            "email, a notification, a status/price update). After waiting, "
            "re-check the relevant tab (e.g. switch to Mail) to see if it "
            "arrived yet."
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
            "End the episode. Call ONLY after the visible page confirms the "
            "task goal is fully achieved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": [],
        },
    },
]


SYSTEM_PROMPT = """\
You are operating a web browser to complete a task on the Xmazon workspace
(Shop + Mail + Food + Calendar apps). You see each page through a SCREENSHOT —
exactly what a human sees, with NO annotations or numbered boxes.

═══════════════════════════════════════════════════════════════════════════
HOW YOU SEE THE PAGE
═══════════════════════════════════════════════════════════════════════════
Each turn I give you:
  1. A screenshot of the current page (viewport 1280 wide x 800 tall)
  2. The current URL
  3. Your open browser tabs: {index, url, title, active}
  4. The task brief (your goal)
  5. The result of your last action

There are NO numbered marks and NO element list. You must LOOK at the
screenshot and judge, in pixels, WHERE each thing is.

═══════════════════════════════════════════════════════════════════════════
HOW YOU ACT — by pixel coordinate
═══════════════════════════════════════════════════════════════════════════
Coordinates: origin (0,0) is the TOP-LEFT; x grows rightward to 1280; y grows
downward to 800. To click something, estimate the pixel at its CENTER.

  click_at(x, y)        Click that pixel. Aim at the middle of the target. If
                        your estimate is off, you click the wrong thing or
                        empty space — so look carefully and be precise.
  type_at(x, y, text)   Click (x, y) to focus an input, then type.
  key(name)             "Enter", "Tab", "Escape", "Backspace", "Control+a"...
  scroll(direction, amount_px)   Reveal content above/below the fold.
  open_tab(url) / switch_tab(index) / close_tab(index)   Browser tabs.
  finish(reason)        End — only when the page confirms the goal is done.

There is NO navigate(url) within a tab — reach pages by clicking links you can
SEE. open_tab only opens an app root in a new tab.

═══════════════════════════════════════════════════════════════════════════
RESPONSE STRUCTURE — plan-then-act, every turn
═══════════════════════════════════════════════════════════════════════════
After your private thinking, your visible response MUST have three sections:

  ## Plan
  Numbered steps toward the goal, each [done]/[in progress]/[next]/[later].
  Revise it across turns; anchor to the task brief verbatim.

  ## What I see now
  Describe the visible page and, for your next target, say roughly WHERE it is
  ("the blue Add button is near x=980, y=240"). Note flash banners (red=error,
  green=success) and confirmation pages.

  ## Next action
  Exactly ONE tool_use block. One action per turn.

═══════════════════════════════════════════════════════════════════════════
GROUNDING TIPS
═══════════════════════════════════════════════════════════════════════════
  - Estimate coordinates from layout: headers/nav near the top, primary action
    buttons often right-aligned, forms stacked left. Use visible text labels as
    anchors and click the CENTER of the labelled control.
  - After acting, check the new screenshot: if nothing changed, your click
    likely missed — re-estimate the coordinate, don't blindly repeat it.
  - Small or tightly-packed buttons need extra care: pick the pixel clearly
    inside the intended target, not a neighbor.
  - Read the task literally. Carry exact values (order ids, totals, ETAs)
    across tabs by READING them off the other app's screenshot — never invent.
  - finish() only when the visible page confirms success; premature finish
    loses points.
"""


class PixelCoordAgent:
    """Anthropic-backed RAW-coordinate browser agent (no Set-of-Mark).

    Pass ``model`` to override the default. Set ANTHROPIC_API_KEY in env.
    """

    def __init__(self, model: str | None = None, max_steps: int | None = None,
                 verbose: bool = True, thinking_budget: int = 4000,
                 eval_mode: bool | None = None):
        from anthropic import Anthropic
        self.client = Anthropic()
        self.model = model or os.getenv(
            "ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929",
        )
        # Step budget. Default 50, overridable via AGENT_MAX_STEPS env var so a
        # run can be given an effectively-unlimited cap (to separate genuine
        # premature-completion failures from step-budget exhaustion).
        self.max_steps = (max_steps if max_steps is not None
                          else int(os.getenv("AGENT_MAX_STEPS", "50")))
        # Benchmark eval mode: when ON, the agent's observation does NOT include
        # fired-milestone names or the running score (which would leak signals
        # like "the refund email was delivered"). Default from AGENT_EVAL_MODE
        # env (set =1 for leaderboard runs). The trajectory still records them.
        self.eval_mode = (eval_mode if eval_mode is not None
                          else os.getenv("AGENT_EVAL_MODE", "0") == "1")
        self.verbose = verbose
        self.thinking_budget = thinking_budget

    @staticmethod
    def _serialize_block(block: Any) -> dict[str, Any]:
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
        return {"type": btype or "unknown"}

    async def run(self, ctx: BrowserCtx, task_brief: str) -> None:
        messages: list[dict[str, Any]] = []
        last_action_result: str = ""
        pending_tool_result: dict[str, Any] | None = None

        for turn in range(self.max_steps):
            # ── TICK the async clock BEFORE observing, so any event scheduled
            # for this step (a new email / price change) has arrived and shows
            # up in the screenshot the agent is about to act on. ──
            await ctx.tick()
            # ── OBSERVE: plain screenshot of the active tab (NO annotation) ──
            raw_png = await ctx.page.screenshot(full_page=False)
            b64 = base64.standard_b64encode(raw_png).decode("ascii")
            url = ctx.page.url
            try:
                tabs = await ctx._tab_strip()
            except Exception:
                tabs = []
            user_text = (
                f"URL: {url}\n"
                f"Open tabs: {json.dumps(tabs)}\n"
                f"Task: {task_brief}\n\n"
                f"Last action result: "
                f"{last_action_result or '(this is your first turn)'}"
            )

            content_blocks: list[dict[str, Any]] = []
            if pending_tool_result is not None:
                content_blocks.append(pending_tool_result)
                pending_tool_result = None
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png",
                           "data": b64},
            })
            content_blocks.append({"type": "text", "text": user_text})
            messages.append({"role": "user", "content": content_blocks})

            # ── THINK + ACT ──
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    thinking={"type": "enabled",
                              "budget_tokens": self.thinking_budget},
                    system=SYSTEM_PROMPT + f"\n\n## TASK\n\n{task_brief}",
                    tools=TOOLS_COORD,
                    messages=messages,
                )
            except Exception as e:
                if self.verbose:
                    print(f"[coord_agent] API error: {type(e).__name__}: {e}")
                break

            tool_call = None
            tool_use_id = None
            text_parts: list[str] = []
            thinking_text = ""
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "thinking":
                    thinking_text = getattr(block, "thinking", "")
                elif btype == "text":
                    text_parts.append(block.text)
                elif btype == "tool_use" and tool_call is None:
                    tool_call = {"name": block.name,
                                 "input": dict(block.input or {})}
                    tool_use_id = block.id

            raw_model_output = (
                (f"<thinking>\n{thinking_text}\n</thinking>\n\n"
                 if thinking_text else "") + "\n".join(text_parts)
            )

            # Persist the assistant turn, TRUNCATED at the first tool_use so a
            # parallel/extra tool_use never goes unanswered (would 400).
            assistant_content: list[dict[str, Any]] = []
            for b in resp.content:
                assistant_content.append(self._serialize_block(b))
                if getattr(b, "type", None) == "tool_use":
                    break
            messages.append({"role": "assistant", "content": assistant_content})

            if tool_call is None:
                if self.verbose:
                    print(f"[coord_agent] no tool call. "
                          f"visible={'/'.join(text_parts)[:160]!r}")
                break

            kind = tool_call["name"]
            args = tool_call["input"]
            if self.verbose:
                print(f"[coord_agent] step {turn}: {kind}"
                      f"({json.dumps(args)[:120]})")

            # ── DISPATCH ──
            try:
                step_record = None
                if kind == "click_at":
                    step_record = await ctx.click_xy(
                        int(args["x"]), int(args["y"]),
                        reasoning=args.get("reason", ""))
                elif kind == "type_at":
                    step_record = await ctx.type_xy(
                        int(args["x"]), int(args["y"]), args["text"],
                        reasoning=args.get("reason", ""))
                elif kind == "key":
                    step_record = await ctx.key_press(
                        name=args["name"], reasoning=args.get("reason", ""))
                elif kind == "scroll":
                    step_record = await ctx.scroll_by(
                        direction=args["direction"],
                        amount_px=int(args["amount_px"]),
                        reasoning=args.get("reason", ""))
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
                        print(f"[coord_agent] finishing: {args.get('reason', '')}")
                    break
                else:
                    raise ValueError(f"unknown tool {kind}")

                if step_record is not None:
                    step_record.raw_model_output = raw_model_output[:4000]
                    if hasattr(resp, "usage") and resp.usage:
                        step_record.tokens_in = int(
                            getattr(resp.usage, "input_tokens", 0) or 0)
                        step_record.tokens_out = int(
                            getattr(resp.usage, "output_tokens", 0) or 0)

                if step_record is None:
                    last_action_result = "(no record)"
                elif step_record.action_error:
                    last_action_result = (
                        f"ERROR: {step_record.action_error}. "
                        f"URL is now {step_record.url_after}.")
                elif self.eval_mode:
                    # Benchmark mode: do NOT leak milestone names / score.
                    last_action_result = (
                        f"OK ({kind}). URL is now {step_record.url_after}.")
                else:
                    last_action_result = (
                        f"OK ({kind}). URL is now {step_record.url_after}. "
                        f"Newly fired milestones: "
                        f"{step_record.milestones_fired_this_step or '[]'}. "
                        f"Running score: {step_record.running_score:.2f}.")
            except Exception as e:
                last_action_result = f"DISPATCH ERROR: {type(e).__name__}: {e}"
                if self.verbose:
                    print(f"[coord_agent] dispatch error: {last_action_result}")

            # Carry the tool_result into the NEXT user turn (one user message
            # that starts with the tool_result — keeps tool_use/tool_result
            # adjacency valid under extended thinking).
            pending_tool_result = {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": last_action_result,
            }
