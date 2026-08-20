"""OpenAI (gpt-4o-mini) PIXEL / Set-of-Mark browser agent — multi-tab.

The GPT sibling of the Anthropic ``PixelBrowserAgent``. Same perception
(annotated screenshot + numbered marks via ``harness/som.py``), same
mark-id action space, but driven by an OpenAI vision model (default
gpt-4o-mini) AND extended with browser-tab tools so it can juggle the
multi-app workspace the way a person does.

Perception each turn:
  * a screenshot with numbered colored boxes on every interactable (SoM)
  * the current URL + the open-tabs strip + a text manifest of the marks
  * the task brief + the result of the last action
Actions (all mark-id or tab-index, never raw coordinates):
  click(mark) / type_text(mark,text) / key(name) / scroll(dir,px) /
  open_tab(url) / switch_tab(index) / close_tab(index) / finish

Reads OPENAI_API_KEY from the environment — never hard-coded.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from harness.runner import BrowserCtx
from harness.som import annotate_image, extract_marks, marks_to_manifest
from agents.pixel_agent import SYSTEM_PROMPT as _PIXEL_SYSTEM_PROMPT, TOOLS_PIXEL


# --------------------------------------------------------------------------- #
# Tools — the SoM pixel tools + browser-tab tools, in OpenAI format
# --------------------------------------------------------------------------- #

_TAB_TOOLS = [
    {"name": "open_tab",
     "description": ("Open an APP in a NEW browser tab and switch to it. "
                     "`url` is an app root: '/' (Shop), '/mail' (Mail), "
                     "'/food' (Food), '/calendar' (Calendar), '/market' "
                     "(Xbay, a second store). Your old tab stays exactly "
                     "where it was — use this to keep one app open while you "
                     "read another."),
     "input_schema": {"type": "object", "properties": {
         "url": {"type": "string"}, "reason": {"type": "string"}},
         "required": ["url"]}},
    {"name": "switch_tab",
     "description": ("Make an already-open tab active by its index (see the "
                     "`tabs` list). Use this to flip BACK to a tab you "
                     "opened earlier."),
     "input_schema": {"type": "object", "properties": {
         "index": {"type": "integer"}, "reason": {"type": "string"}},
         "required": ["index"]}},
    {"name": "close_tab",
     "description": "Close an open tab by its index.",
     "input_schema": {"type": "object", "properties": {
         "index": {"type": "integer"}, "reason": {"type": "string"}},
         "required": ["index"]}},
    {"name": "wait",
     "description": ("Let time pass WITHOUT a UI action — use this to wait for "
                     "something to arrive that you can't make happen yourself "
                     "(a new email, a notification, a price/status update). "
                     "After waiting, re-check the relevant tab (e.g. Mail)."),
     "input_schema": {"type": "object", "properties": {
         "reason": {"type": "string"}}, "required": []}},
]


def _to_openai_tools(anthropic_tools: list[dict]) -> list[dict]:
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["input_schema"]}}
            for t in anthropic_tools]


# TOOLS_PIXEL already carries the multi-tab tools + `wait` + `finish`, so use it
# directly — adding _TAB_TOOLS again would duplicate tool names. (_TAB_TOOLS is
# kept above for reference / backward-compat imports.)
TOOLS_OPENAI_PIXEL = _to_openai_tools(TOOLS_PIXEL)


def _to_responses_tools(anthropic_tools: list[dict]) -> list[dict]:
    """/v1/responses uses a FLAT function-tool shape — name/description/parameters
    at the TOP level, NOT nested under a "function" key the way chat.completions
    requires. Built from the SAME TOOLS_PIXEL source, so schemas (and therefore the
    arg names the model emits) are identical to the chat path — the dispatch is
    shared verbatim."""
    return [{"type": "function", "name": t["name"],
             "description": t["description"], "parameters": t["input_schema"]}
            for t in anthropic_tools]


TOOLS_RESPONSES = _to_responses_tools(TOOLS_PIXEL)


def _needs_responses_api(model: str | None) -> bool:
    """True ONLY for reasoning models that REJECT function-tools + reasoning on
    /v1/chat/completions and must use /v1/responses — the gpt-5.6 family (Sol/Terra/
    Luna). False for gpt-5.1 / gpt-5.5 / qwen / 4o, which keep the EXISTING
    chat.completions path unchanged. This gate is the SOLE router into the new code,
    so a concurrent gpt-5.1/gpt-5.5/sonnet run is provably unaffected by its addition."""
    return "5.6" in (model or "").lower()


# --------------------------------------------------------------------------- #
# System prompt — the pixel playbook + a multi-app/tabs addendum
# --------------------------------------------------------------------------- #

_MULTI_APP_TABS = """

═══════════════════════════════════════════════════════════════════════════
MULTI-APP WORKSPACE + BROWSER TABS
═══════════════════════════════════════════════════════════════════════════

At the very top of every page is a dark workspace bar with marks for
several apps: Shop, Mail, Food, Calendar, and Xbay (a SECOND store).
Some tasks span apps — e.g. place an order in the Shop, then read the
confirmation email in Mail; or compare a price in the Shop vs Xbay
before buying from the cheaper one.

You have THREE extra tools for tabs:
  open_tab(url)     open an app in a NEW tab and switch to it. `url` is an
                    app root: "/" (Shop), "/mail" (Mail), "/food" (Food),
                    "/calendar" (Calendar), "/market" (Xbay).
  switch_tab(index) make an already-open tab active (see the `tabs` list).
  close_tab(index)  close a tab.

Each turn the message lists your open `tabs` as {index, url, title,
active}. Use tabs like a person on a multi-app task: keep the Shop in
tab 0, OPEN MAIL IN A SECOND TAB to read the confirmation email, then
switch_tab(0) BACK to the Shop to act on what you learned. (open_tab is the
ONE exception to "no navigation" — it only opens an app ROOT in a new tab;
WITHIN a tab you still navigate by clicking marks.)

CARRY VALUES ACCURATELY across tabs (an order number, a charged total, an
ETA). Read them off the screenshot of the OTHER app — never invent, guess,
or assume a value. If a task needs the exact total you were charged, you
must actually OPEN and READ the email; the sticker price on the product is
NOT the charged total.
"""

SYSTEM_PROMPT = _PIXEL_SYSTEM_PROMPT + _MULTI_APP_TABS


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #

class OpenAIPixelAgent:
    """gpt-4o-mini pixel/SoM agent with multi-tab tools."""

    def __init__(self, model: str | None = None, max_steps: int | None = None,
                 verbose: bool = True, base_url: str | None = None,
                 api_key: str | None = None, eval_mode: bool | None = None):
        from openai import OpenAI
        # base_url lets this same agent drive any OpenAI-COMPATIBLE endpoint —
        # incl. Qwen via DashScope / OpenRouter (set OPENAI_BASE_URL + the
        # provider key). Defaults to OpenAI proper.
        base = base_url or os.getenv("OPENAI_BASE_URL") or None
        key = api_key or os.getenv("OPENAI_API_KEY")
        # Explicit finite timeout + NO opaque SDK-internal retries — our
        # _llm_retry.acall wrapper is the single retry authority, so a stuck
        # gpt-5.x/proxy call is bounded and surfaces as an error, not a freeze.
        from agents._llm_retry import _env_float
        self.client = OpenAI(
            base_url=base, api_key=key,
            timeout=_env_float("LLM_CALL_TIMEOUT", 120.0),
            max_retries=0,
        )
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4")
        self.max_steps = (max_steps if max_steps is not None
                          else int(os.getenv("AGENT_MAX_STEPS", "50")))
        self.verbose = verbose
        # No reward leakage in benchmark runs (AGENT_EVAL_MODE=1).
        self.eval_mode = (eval_mode if eval_mode is not None
                          else os.getenv("AGENT_EVAL_MODE", "0") == "1")
        # DYNAMIC context guard: the pixel loop re-sends every prior screenshot, so
        # context grows unbounded and eventually 400s past the model's window
        # (Qwen3-VL = 131072). Rather than a fixed step cap (a task-dependent proxy),
        # end the episode gracefully once the MEASURED prompt_tokens of a turn nears
        # the window — task-adaptive (dense pages stop sooner) and per-model (set
        # LLM_CONTEXT_BUDGET per tier; default 190000 leaves headroom for Sonnet 200K
        # / gpt-5.x, and the cascade sets 118000 for the Qwen tier).
        self.context_budget = int(os.getenv("LLM_CONTEXT_BUDGET", "190000"))

    async def run(self, ctx: BrowserCtx, task_brief: str) -> None:
        # ROUTE reasoning models that can't do tools+reasoning on chat.completions
        # (gpt-5.6 family) to the /v1/responses path. This guard is False for
        # gpt-5.1/gpt-5.5/qwen/4o, so their execution below is UNCHANGED — the
        # concurrent 4-cut is provably unaffected.
        if _needs_responses_api(self.model):
            return await self._run_responses(ctx, task_brief)
        messages: list[dict[str, Any]] = [
            {"role": "system",
             "content": SYSTEM_PROMPT + f"\n\n## TASK\n\n{task_brief}"},
        ]
        last_result = "(this is your first turn)"
        last_prompt_tokens = 0        # measured context size of the previous turn

        for turn in range(self.max_steps):
            # DYNAMIC context guard — stop BEFORE the next (larger) turn would
            # overflow the model window. Uses the real measured prompt_tokens, so a
            # dense-page task stops sooner and a light one runs longer. A clean end
            # (INCOMPLETE), never a context-length 400.
            if last_prompt_tokens >= self.context_budget:
                if self.verbose:
                    print(f"[openai_pixel] context budget reached "
                          f"({last_prompt_tokens} >= {self.context_budget}); "
                          f"ending episode at turn {turn} to avoid overflow.")
                break
            # ── TICK the async clock BEFORE observing (events scheduled for
            # this step arrive + show in the screenshot the agent acts on). ──
            await ctx.tick()
            # ── OBSERVE: marks + annotated screenshot + manifest + tabs ──
            marks = await extract_marks(ctx.page)
            raw_png = await ctx.page.screenshot(full_page=False)
            annotated = annotate_image(raw_png, marks)
            manifest = marks_to_manifest(marks)
            b64 = base64.standard_b64encode(annotated).decode("ascii")
            try:
                tabs = await ctx._tab_strip()
            except Exception:
                tabs = []

            user_text = (
                f"URL: {ctx.page.url}\n"
                f"Open tabs: {json.dumps(tabs)}\n"
                f"Task: {task_brief}\n\n"
                f"Visible marks ({len(marks)}):\n{manifest}\n\n"
                f"Last action result: {last_result}"
            )
            messages.append({"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}",
                               "detail": "high"}},
            ]})

            # ── THINK + ACT ──
            # tool_choice="required" forces an ACTION every turn. Without it,
            # small models (gpt-4o-mini) tend to narrate the plan as prose and
            # never emit a tool call, stalling the episode at step 0.
            from agents._llm_retry import acall
            try:
                resp = await acall(
                    lambda: self.client.chat.completions.create(
                        model=self.model, max_completion_tokens=4096,
                        tools=TOOLS_OPENAI_PIXEL, tool_choice="required",
                        messages=messages,
                    ),
                    label="openai_pixel",
                    verbose=self.verbose,
                )
            except Exception as e:
                # Hard safety net for context overflow: the dynamic guard reads the
                # provider's reported prompt_tokens, which for image-heavy Qwen turns
                # can under-report / jump, so it may not fire before the window is
                # exceeded. A context-length 400 means this runaway episode simply
                # can't continue — end it as a clean INCOMPLETE (a fumble that never
                # reached the trap is NOT a break), rather than letting the error
                # propagate and trigger a wasteful full re-run.
                msg = str(e).lower()
                if "context length" in msg or "maximum context" in msg \
                        or "context_length_exceeded" in msg:
                    if self.verbose:
                        print(f"[openai_pixel] context overflow at turn {turn}; "
                              f"ending episode (INCOMPLETE).")
                    break
                raise
            msg = resp.choices[0].message
            usage = resp.usage
            tin = int(getattr(usage, "prompt_tokens", 0) or 0)
            tout = int(getattr(usage, "completion_tokens", 0) or 0)
            last_prompt_tokens = tin      # feeds the context guard next turn
            text = msg.content or ""
            tool_calls = msg.tool_calls or []

            if not tool_calls:
                if self.verbose:
                    print(f"[openai_pixel] no tool call. text={text[:160]}")
                messages.append({"role": "assistant", "content": text})
                break

            tc = tool_calls[0]
            kind = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            messages.append({"role": "assistant", "content": text,
                "tool_calls": [{"id": tc.id, "type": "function",
                    "function": {"name": kind,
                                 "arguments": tc.function.arguments or "{}"}}]})
            if self.verbose:
                print(f"[openai_pixel] step {turn}: {kind}({json.dumps(args)[:110]})")

            rec = None
            try:
                if kind == "click":
                    rec = await ctx.click_mark(int(args["mark_id"]), marks,
                                               reasoning=args.get("reason", ""))
                elif kind == "type_text":
                    rec = await ctx.type_into_mark(int(args["mark_id"]), marks,
                                                   args.get("text", ""),
                                                   reasoning=args.get("reason", ""))
                elif kind == "key":
                    rec = await ctx.key_press(args["name"],
                                              reasoning=args.get("reason", ""))
                elif kind == "scroll":
                    rec = await ctx.scroll_by(args["direction"],
                                              int(args["amount_px"]),
                                              reasoning=args.get("reason", ""))
                elif kind == "open_tab":
                    rec = await ctx.open_tab(args["url"],
                                             reasoning=args.get("reason", ""))
                elif kind == "switch_tab":
                    rec = await ctx.switch_tab(int(args["index"]),
                                               reasoning=args.get("reason", ""))
                elif kind == "close_tab":
                    rec = await ctx.close_tab(int(args["index"]),
                                              reasoning=args.get("reason", ""))
                elif kind == "wait":
                    rec = await ctx.wait(reasoning=args.get("reason", ""))
                elif kind == "finish":
                    if self.verbose:
                        print(f"[openai_pixel] finishing: {args.get('reason', '')}")
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": "OK (finished)."})
                    break
                else:
                    raise ValueError(f"unknown tool {kind}")

                if rec is not None:
                    rec.raw_model_output = text
                    rec.tokens_in = tin
                    rec.tokens_out = tout
                    if rec.action_error:
                        last_result = (f"ERROR: {rec.action_error}. "
                                       f"URL now {rec.url_after}.")
                    elif self.eval_mode:
                        last_result = f"OK ({kind}). URL now {rec.url_after}."
                    else:
                        last_result = (
                            f"OK ({kind}). URL now {rec.url_after}. "
                            f"Newly fired: {rec.milestones_fired_this_step or '[]'}. "
                            f"Score: {rec.running_score:.2f}.")
                else:
                    last_result = f"OK ({kind})."
            except Exception as e:
                last_result = f"DISPATCH ERROR: {type(e).__name__}: {e}"
                if self.verbose:
                    print(f"[openai_pixel] {last_result}")

            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": last_result})

    # ─────────────────────────────────────────────────────────────────────── #
    # /v1/responses path — reasoning models (gpt-5.6 Sol/Terra/Luna).          #
    # A self-contained mirror of run(): identical perception, identical tool   #
    # dispatch, identical per-step token recording — only the LLM transport    #
    # (Responses API) and the message-threading format differ. Kept SEPARATE   #
    # so the chat.completions run() above stays untouched for gpt-5.1/5.5/qwen.#
    # ─────────────────────────────────────────────────────────────────────── #
    async def _responses_llm(self, instructions: str, input_items: list):
        """One /v1/responses round-trip. Returns (text, tool_calls, tin, tout,
        status) with tool_calls = [(call_id, name, arguments_str), ...].

        Reasoning is left at the model DEFAULT (no explicit reasoning.effort) to
        MIRROR how gpt-5.5 runs on chat.completions (its own default reasoning) — so
        the cross-model comparison is fair, not crippled to no-reasoning. Token usage
        maps input_tokens/output_tokens -> the SAME tin/tout the chat path records."""
        from agents._llm_retry import acall
        max_out = int(os.getenv("LLM_RESP_MAX_OUTPUT", "8192"))
        resp = await acall(
            lambda: self.client.responses.create(
                model=self.model, instructions=instructions, input=input_items,
                tools=TOOLS_RESPONSES, tool_choice="required",
                max_output_tokens=max_out, store=False,
            ),
            label="openai_pixel_responses",
            verbose=self.verbose,
        )
        usage = resp.usage
        tin = int(getattr(usage, "input_tokens", 0) or 0)
        tout = int(getattr(usage, "output_tokens", 0) or 0)
        text = ""
        tool_calls: list = []
        for o in (resp.output or []):
            otype = getattr(o, "type", "")
            if otype == "function_call":
                cid = getattr(o, "call_id", None) or getattr(o, "id", None)
                tool_calls.append((cid, o.name, o.arguments))
            elif otype == "message":
                for part in (getattr(o, "content", None) or []):
                    if getattr(part, "type", "") == "output_text":
                        text += getattr(part, "text", "") or ""
        return text, tool_calls, tin, tout, getattr(resp, "status", None)

    async def _run_responses(self, ctx: BrowserCtx, task_brief: str) -> None:
        instructions = SYSTEM_PROMPT + f"\n\n## TASK\n\n{task_brief}"
        input_items: list[dict[str, Any]] = []
        last_result = "(this is your first turn)"
        last_prompt_tokens = 0

        for turn in range(self.max_steps):
            if last_prompt_tokens >= self.context_budget:
                if self.verbose:
                    print(f"[openai_pixel/responses] context budget reached "
                          f"({last_prompt_tokens} >= {self.context_budget}); "
                          f"ending episode at turn {turn}.")
                break
            await ctx.tick()
            marks = await extract_marks(ctx.page)
            raw_png = await ctx.page.screenshot(full_page=False)
            annotated = annotate_image(raw_png, marks)
            manifest = marks_to_manifest(marks)
            b64 = base64.standard_b64encode(annotated).decode("ascii")
            try:
                tabs = await ctx._tab_strip()
            except Exception:
                tabs = []

            user_text = (
                f"URL: {ctx.page.url}\n"
                f"Open tabs: {json.dumps(tabs)}\n"
                f"Task: {task_brief}\n\n"
                f"Visible marks ({len(marks)}):\n{manifest}\n\n"
                f"Last action result: {last_result}"
            )
            input_items.append({"role": "user", "content": [
                {"type": "input_text", "text": user_text},
                {"type": "input_image",
                 "image_url": f"data:image/png;base64,{b64}", "detail": "high"},
            ]})

            try:
                text, tool_calls, tin, tout, status = await self._responses_llm(
                    instructions, input_items)
            except Exception as e:
                msg = str(e).lower()
                if "context length" in msg or "maximum context" in msg \
                        or "context_length_exceeded" in msg:
                    if self.verbose:
                        print(f"[openai_pixel/responses] context overflow at turn "
                              f"{turn}; ending episode (INCOMPLETE).")
                    break
                raise
            last_prompt_tokens = tin

            if not tool_calls:
                if self.verbose:
                    print(f"[openai_pixel/responses] no tool call. "
                          f"status={status} text={text[:160]}")
                break

            call_id, kind, arguments = tool_calls[0]
            try:
                args = json.loads(arguments or "{}")
            except Exception:
                args = {}
            # thread the model's function_call back into the running input FIRST,
            # so its matching function_call_output (appended after dispatch) is valid.
            input_items.append({"type": "function_call", "call_id": call_id,
                                "name": kind, "arguments": arguments or "{}"})
            if self.verbose:
                print(f"[openai_pixel/responses] step {turn}: "
                      f"{kind}({json.dumps(args)[:110]})")

            rec = None
            try:
                if kind == "click":
                    rec = await ctx.click_mark(int(args["mark_id"]), marks,
                                               reasoning=args.get("reason", ""))
                elif kind == "type_text":
                    rec = await ctx.type_into_mark(int(args["mark_id"]), marks,
                                                   args.get("text", ""),
                                                   reasoning=args.get("reason", ""))
                elif kind == "key":
                    rec = await ctx.key_press(args["name"],
                                              reasoning=args.get("reason", ""))
                elif kind == "scroll":
                    rec = await ctx.scroll_by(args["direction"],
                                              int(args["amount_px"]),
                                              reasoning=args.get("reason", ""))
                elif kind == "open_tab":
                    rec = await ctx.open_tab(args["url"],
                                             reasoning=args.get("reason", ""))
                elif kind == "switch_tab":
                    rec = await ctx.switch_tab(int(args["index"]),
                                               reasoning=args.get("reason", ""))
                elif kind == "close_tab":
                    rec = await ctx.close_tab(int(args["index"]),
                                              reasoning=args.get("reason", ""))
                elif kind == "wait":
                    rec = await ctx.wait(reasoning=args.get("reason", ""))
                elif kind == "finish":
                    if self.verbose:
                        print(f"[openai_pixel/responses] finishing: "
                              f"{args.get('reason', '')}")
                    input_items.append({"type": "function_call_output",
                                        "call_id": call_id,
                                        "output": "OK (finished)."})
                    break
                else:
                    raise ValueError(f"unknown tool {kind}")

                if rec is not None:
                    rec.raw_model_output = text
                    rec.tokens_in = tin
                    rec.tokens_out = tout
                    if rec.action_error:
                        last_result = (f"ERROR: {rec.action_error}. "
                                       f"URL now {rec.url_after}.")
                    elif self.eval_mode:
                        last_result = f"OK ({kind}). URL now {rec.url_after}."
                    else:
                        last_result = (
                            f"OK ({kind}). URL now {rec.url_after}. "
                            f"Newly fired: {rec.milestones_fired_this_step or '[]'}. "
                            f"Score: {rec.running_score:.2f}.")
                else:
                    last_result = f"OK ({kind})."
            except Exception as e:
                last_result = f"DISPATCH ERROR: {type(e).__name__}: {e}"
                if self.verbose:
                    print(f"[openai_pixel/responses] {last_result}")

            input_items.append({"type": "function_call_output",
                                "call_id": call_id, "output": last_result})
