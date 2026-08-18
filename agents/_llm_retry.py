"""Bounded, backed-off LLM call wrapper — turns a stuck API call into a HARD
error instead of an infinite freeze.

Root cause of the M230-M253 screening hang: the pixel agents call the SYNC
Anthropic/OpenAI SDK client directly inside their ``async def run`` loop with no
explicit timeout. A stalled socket (or an SDK/proxy that never returns) blocks
the event loop with no ceiling, so the episode — and the whole batch behind it —
freezes silently.

This helper guarantees three things the plan requires:
  1. TIMEOUT      — every attempt is offloaded to a DAEMON worker thread and
                    bounded by ``asyncio.wait_for``. Even if the SDK's own timeout
                    misbehaves, the coroutine gives up after ``per_call_timeout``
                    seconds — and because the thread is a daemon, a call still
                    stuck on the socket cannot hold the process open at exit.
                    See ``_spawn`` for why ``asyncio.to_thread`` is wrong here.
  2. RETRY+BACKOFF— transient failures (timeouts, 429, 5xx, connection resets) are
                    retried up to ``attempts`` times with capped exponential backoff.
                    Non-transient 4xx client errors (e.g. a malformed request) are
                    NOT retried — they surface immediately.
  3. HARD FAILURE — when the budget is exhausted the call raises
                    :class:`LLMCallError`, which propagates to the episode runner
                    (eval/run.py wraps the agent in try/except and records
                    ``traj.error``). A stuck call becomes a visible error row, not
                    a hang.

All knobs are env-overridable so a screening batch can tune them without code
edits:
    LLM_CALL_TIMEOUT      per-attempt ceiling, seconds        (default 120)
    LLM_MAX_ATTEMPTS      total attempts incl. the first      (default 3)
    LLM_RETRY_BASE_DELAY  first backoff, seconds              (default 2)
    LLM_RETRY_MAX_DELAY   backoff cap, seconds                (default 30)
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Callable


class LLMCallError(RuntimeError):
    """An LLM API call could not complete within the timeout + retry budget."""


def _spawn(make_call: Callable[[], Any]) -> "asyncio.Future":
    """Run ``make_call`` on a throwaway DAEMON thread; return a future for it.

    Deliberately not ``asyncio.to_thread``. That borrows the loop's default
    ThreadPoolExecutor, whose workers are non-daemon and are JOINED by an
    interpreter-exit hook. So when an SDK call wedges on a socket, the
    ``wait_for`` below correctly abandons the await and the episode runs to
    completion — and then the PROCESS hangs forever at shutdown waiting to join
    a thread that will never return. Seen on the ten-task Sol batch: the episode
    wrote its 41st frame, then sat at 0% CPU with an ESTABLISHED socket for 15+
    minutes, with the other nine queued behind it.

    A daemon thread is abandoned at exit instead of joined, so the timeout
    ceiling actually ends the call as far as the process is concerned.
    """
    loop = asyncio.get_running_loop()
    fut: "asyncio.Future" = loop.create_future()

    def settle(setter, value) -> None:
        if not fut.done():                    # wait_for may have cancelled it
            setter(value)

    def target() -> None:
        try:
            res = make_call()
        except BaseException as exc:          # noqa: BLE001 — relayed verbatim
            payload, setter = exc, fut.set_exception
        else:
            payload, setter = res, fut.set_result
        try:
            loop.call_soon_threadsafe(settle, setter, payload)
        except RuntimeError:
            pass                              # loop already closed; nobody is waiting

    threading.Thread(target=target, name="llm-call", daemon=True).start()
    return fut


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def is_retryable(exc: BaseException) -> bool:
    """Retry timeouts, connection errors, rate limits and 5xx; NOT plain 4xx."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        # 4xx are client errors and won't get better by retrying — except
        # 408 (request timeout), 409 (conflict), 429 (rate limit).
        if 400 <= status < 500 and status not in (408, 409, 429):
            return False
        return True
    # httpx/openai/anthropic connection & timeout exceptions have no status_code
    # and are transient by nature.
    return True


async def acall(
    make_call: Callable[[], Any],
    *,
    label: str,
    attempts: int | None = None,
    per_call_timeout: float | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    verbose: bool = False,
) -> Any:
    """Run the sync ``make_call`` (an SDK ``...create(...)`` thunk) with a hard
    per-attempt timeout and bounded exponential-backoff retries.

    Returns the SDK response on success. Raises the original exception on a
    non-retryable error, or :class:`LLMCallError` once the retry budget is spent.
    """
    attempts = attempts if attempts is not None else _env_int("LLM_MAX_ATTEMPTS", 3)
    per_call_timeout = (per_call_timeout if per_call_timeout is not None
                        else _env_float("LLM_CALL_TIMEOUT", 120.0))
    base_delay = base_delay if base_delay is not None else _env_float("LLM_RETRY_BASE_DELAY", 2.0)
    max_delay = max_delay if max_delay is not None else _env_float("LLM_RETRY_MAX_DELAY", 30.0)

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            # Offload the blocking SDK call to a thread so wait_for can enforce a
            # ceiling the SDK cannot escape. asyncio.CancelledError (BaseException)
            # is NOT caught here, so cooperative cancellation still works.
            return await asyncio.wait_for(_spawn(make_call), timeout=per_call_timeout)
        except Exception as e:  # noqa: BLE001 — deliberately broad, then triaged
            last_exc = e
            retryable = is_retryable(e)
            if verbose:
                kind = ("timeout" if isinstance(e, (asyncio.TimeoutError, TimeoutError))
                        else type(e).__name__)
                disp = "retry" if (retryable and attempt < attempts) else "give up"
                print(f"[llm_retry:{label}] attempt {attempt}/{attempts} "
                      f"{kind}: {str(e)[:200]} -> {disp}")
            if not retryable:
                raise
            if attempt >= attempts:
                break
            await asyncio.sleep(min(max_delay, base_delay * (2 ** (attempt - 1))))

    raise LLMCallError(
        f"{label}: exhausted {attempts} attempt(s) x {per_call_timeout:.0f}s ceiling; "
        f"last error: {type(last_exc).__name__}: {str(last_exc)[:300]}"
    ) from last_exc
