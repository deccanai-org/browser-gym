"""Credit/billing exhaustion must be detected across the whole error class, and
must never be confused with ordinary rate limiting or with task content.

Regression guard for the 2026-08-05 mis-scoring incident: monitors matched the
literal token ``credit_balance_too_low``, which Anthropic does not emit. See
docs/history/audits/OPUS_CREDIT_DETECTION_FIX_AND_REAUDIT_2026-08-05.md.
"""
from __future__ import annotations

import pytest

from harness.api_failure_class import (
    AUTH_FAILED,
    CONTEXT_OVERFLOW,
    CREDIT_EXHAUSTED,
    OVERLOADED,
    RATE_LIMITED,
    classify_api_failure,
    is_credit_exhaustion,
    is_fatal_provider_failure,
    is_ordinary_rate_limit,
    scan_log_text,
)
from harness.invalid_episode import INVALID_AGENT_PROVIDER, reason_from_error

# The exact body Anthropic returned during the contaminated runs. Note the type
# is `invalid_request_error` and the token `credit_balance_too_low` is absent.
ANTHROPIC_CREDIT = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API. "
    "Please go to Plans & Billing to upgrade or purchase credits.'}, "
    "'request_id': 'req_011CdiZ6mh2qDdTxkWPQiCGm'}"
)
OPENAI_CREDIT = (
    "Error code: 429 - {'error': {'type': 'insufficient_quota', 'message': "
    "'You exceeded your current quota, please check your plan and billing details.'}}"
)
ANTHROPIC_RATE_LIMIT = (
    "Error code: 429 - {'type': 'error', 'error': {'type': 'rate_limit_error', "
    "'message': 'Number of requests per minute exceeded'}}"
)
ANTHROPIC_OVERLOADED = (
    "Error code: 529 - {'type': 'error', 'error': {'type': 'overloaded_error', "
    "'message': 'Overloaded'}}"
)


@pytest.mark.parametrize("text", [
    ANTHROPIC_CREDIT,
    OPENAI_CREDIT,
    "credit_balance_too_low",                        # legacy literal token
    "Your credit balance is too low",                # prose only
    "your credit_balance_too_low flag is set",       # token, odd casing/context
    "Error code: 402 - Payment Required",
    "APIStatusError: insufficient credits on this account",
    "billing_hard_limit_reached",
    "quota_exceeded",
])
def test_credit_class_detected(text: str) -> None:
    assert is_credit_exhaustion(text)
    assert classify_api_failure(text) == CREDIT_EXHAUSTED
    assert is_fatal_provider_failure(text)


@pytest.mark.parametrize("text,want", [
    (ANTHROPIC_RATE_LIMIT, RATE_LIMITED),
    (ANTHROPIC_OVERLOADED, OVERLOADED),
    ("Error code: 401 - authentication_error", AUTH_FAILED),
    ("Error code: 400 - context_length_exceeded", CONTEXT_OVERFLOW),
])
def test_other_classes(text: str, want: str) -> None:
    assert classify_api_failure(text) == want
    assert not is_credit_exhaustion(text)


def test_rate_limit_is_not_fatal_but_credit_is() -> None:
    """The distinction that protects genuine model failures from being voided."""
    assert is_ordinary_rate_limit(ANTHROPIC_RATE_LIMIT)
    assert not is_fatal_provider_failure(ANTHROPIC_RATE_LIMIT)
    assert not is_fatal_provider_failure(ANTHROPIC_OVERLOADED)
    assert is_fatal_provider_failure(ANTHROPIC_CREDIT)
    # OpenAI ships billing exhaustion on a 429; credit must win the tie.
    assert not is_ordinary_rate_limit(OPENAI_CREDIT)
    assert is_fatal_provider_failure(OPENAI_CREDIT)


@pytest.mark.parametrize("line", [
    '[pixel_agent] step 4: type({"mark_id": 7, "text": "12 Billing Rd", '
    '"reason": "fill in billing details"})',
    '[pixel_agent] step 9: click({"reason": "pick the credit card ending 1111"})',
    '[pixel_agent] step 2: type({"text": "our seat quota is 5 this month"})',
    '[openai_pixel] step 1: click({"reason": "open Plans page"})',
])
def test_task_content_never_reads_as_credit_death(line: str) -> None:
    """Bare `credit` / `billing` / `quota` words in agent actions must not void a
    real episode — that would erase genuine model failures."""
    assert not is_credit_exhaustion(line)
    assert classify_api_failure(line) is None


def test_scan_log_terminal_credit_death_zero_step() -> None:
    log = (
        "[worker] task=food_006/design_review_shared_platter seed=0\n"
        ">>> pixel on food_006/design_review_shared_platter seed=0\n"
        f"[llm_retry:pixel] attempt 1/3 BadRequestError: {ANTHROPIC_CREDIT} -> give up\n"
        f"[pixel_agent] API error: BadRequestError: {ANTHROPIC_CREDIT}\n"
        "  -> score=0.00 success=False steps=0 failure=never_reached_checkout\n"
    )
    scan = scan_log_text(log)
    assert scan["credit_death"] is True
    assert scan["failure_class"] == CREDIT_EXHAUSTED
    assert scan["credit_gave_up"] == 1
    assert scan["credit_at_step"] == 0          # died on the first model call
    assert scan["transient"] == {}


def test_scan_log_terminal_credit_death_mid_run() -> None:
    log = (
        '[pixel_agent] step 0: click({"mark_id": 2})\n'
        '[pixel_agent] step 1: click({"mark_id": 22})\n'
        '[pixel_agent] step 2: click({"mark_id": 18})\n'
        f"[llm_retry:pixel] attempt 1/3 BadRequestError: {ANTHROPIC_CREDIT} -> give up\n"
        "  -> score=0.00 success=False steps=3 failure=unclassified_failure\n"
    )
    scan = scan_log_text(log)
    assert scan["credit_death"] is True
    assert scan["credit_at_step"] == 3
    assert scan["steps_seen"] == 3


def test_scan_log_retried_overload_stays_valid() -> None:
    """A 529 that was retried and then produced more steps is a VALID episode."""
    log = (
        '[pixel_agent] step 12: click({"mark_id": 19})\n'
        f"[llm_retry:pixel] attempt 1/3 OverloadedError: {ANTHROPIC_OVERLOADED} -> retry\n"
        '[pixel_agent] step 13: scroll({"direction": "down"})\n'
        '[pixel_agent] step 18: finish({"reason": "Order placed"})\n'
        "  -> score=1.00 success=False steps=18\n"
    )
    scan = scan_log_text(log)
    assert scan["credit_death"] is False
    assert scan["failure_class"] == OVERLOADED
    assert scan["transient"] == {OVERLOADED: 1}


def test_scan_log_clean_episode() -> None:
    log = (
        '[pixel_agent] step 0: click({"mark_id": 2})\n'
        '[pixel_agent] step 1: finish({"reason": "done"})\n'
        "  -> score=1.00 success=True steps=2\n"
    )
    scan = scan_log_text(log)
    assert scan["credit_death"] is False
    assert scan["failure_class"] is None
    assert scan["steps_seen"] == 2


def test_scan_log_finds_credit_without_retry_wrapper_line() -> None:
    """Raw-text fallback: some paths only print the agent's own error line."""
    log = f"[pixel_agent] API error [credit_exhausted]: BadRequestError: {ANTHROPIC_CREDIT}\n"
    assert scan_log_text(log)["credit_death"] is True


def test_invalid_episode_buckets_prose_credit_error() -> None:
    """The prose form carries no 402 and no `credit_balance_too_low`, so the old
    flat marker list only caught it via the bare substring `credit`."""
    err = f"BadRequestError: {ANTHROPIC_CREDIT}"
    assert reason_from_error(err) == INVALID_AGENT_PROVIDER
