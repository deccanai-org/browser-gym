"""Fine-grained classification of model-provider API failures.

Why this module exists
----------------------
Credit/billing exhaustion and ordinary rate limiting look similar in a log but
mean opposite things for an eval:

* **Credit exhaustion is fatal and non-retryable.** Anthropic answers
  ``HTTP 400 invalid_request_error`` with the prose *"Your credit balance is too
  low to access the Anthropic API"*; OpenAI answers ``HTTP 429 insufficient_quota``
  with *"You exceeded your current quota"*. The agent loop cannot continue, so
  the episode never reaches a terminal agent decision. Scoring it yields a
  **false BREAK** (partial world state) or a **false HOLD** (nothing harmful
  happened because nothing happened at all). Such an episode must be VOIDed, not
  counted.
* **Ordinary rate limiting / capacity is transient and retryable.** Anthropic
  ``429 rate_limit_error`` and ``529 overloaded_error`` are retried by
  ``agents._llm_retry.acall`` and the episode usually continues to a genuine
  decision. Voiding those would silently erase real model failures.

The 2026-08-05 mis-scoring incident came from matching the literal token
``credit_balance_too_low``, which Anthropic **never emits in the message body** —
the machine token is ``invalid_request_error`` and the credit fact lives only in
the human-readable ``message``. Every monitor and audit that grepped the token
saw zero hits while a third of the panel was dying on credits.

Matching policy
---------------
Bare words (``credit``, ``billing``, ``quota``) are NOT sufficient: episode logs
legitimately contain agent actions like typing a *billing address* or reading a
*credit card* row, and matching those would void real model failures. So:

* **Tier 1** phrases are provider error strings that cannot plausibly appear in
  task content, and match on their own.
* **Tier 2** phrases are weaker (``payment required``, ``402``, ``quota``) and
  only count when the same line also carries an API-error co-signal
  (``Error code:``, ``'type': 'error'``, ``BadRequestError``, ``llm_retry`` …).

``scan_log_text`` works on **raw log text**, because the structured
``Trajectory.error`` field is empty for exactly the failure this module targets:
the pixel agents used to ``break`` out of their loop on a non-retryable API
error without recording anything.
"""
from __future__ import annotations

import re
from typing import Any, Final

# --- failure classes -------------------------------------------------------- #

CREDIT_EXHAUSTED: Final = "credit_exhausted"
RATE_LIMITED: Final = "rate_limited"
OVERLOADED: Final = "overloaded"
AUTH_FAILED: Final = "auth_failed"
CONTEXT_OVERFLOW: Final = "context_overflow"
TIMEOUT: Final = "timeout"
CONNECTION: Final = "connection"
PROVIDER_OTHER: Final = "provider_other"

FAILURE_CLASSES: Final[frozenset[str]] = frozenset({
    CREDIT_EXHAUSTED,
    RATE_LIMITED,
    OVERLOADED,
    AUTH_FAILED,
    CONTEXT_OVERFLOW,
    TIMEOUT,
    CONNECTION,
    PROVIDER_OTHER,
})

#: Classes that mean "the episode could not produce a model decision, and
#: retrying inside the episode cannot help". These must VOID the episode.
FATAL_CLASSES: Final[frozenset[str]] = frozenset({CREDIT_EXHAUSTED, AUTH_FAILED})

# --- tier 1: unambiguous provider billing/credit strings --------------------- #

_CREDIT_TIER1: Final[tuple[str, ...]] = (
    # Anthropic. The machine token AND the prose, plus the remediation sentence
    # that follows it ("Please go to Plans & Billing to upgrade or purchase
    # credits."). ``[_ ]`` so the snake_case token and the prose share one arm.
    r"credit[_ ]balance[_ ](?:is[_ ])?too[_ ]low",
    r"\bpurchase\s+credits?\b",
    r"upgrade\s+or\s+purchase",
    # OpenAI / Azure OpenAI billing exhaustion (arrives as HTTP 429, NOT a plain
    # rate limit — distinguished from rate_limit_error by this wording).
    r"insufficient[_ ]quota",
    r"exceeded\s+your\s+current\s+quota",
    r"billing[_ ]hard[_ ]limit(?:[_ ]reached)?",
    r"check\s+your\s+plan\s+and\s+billing\s+details",
    # Generic provider phrasings for the same class.
    r"insufficient[_ ](?:credits?|funds|balance)",
    r"\bout\s+of\s+credits?\b",
    r"\bno\s+(?:remaining\s+)?credits?\s+(?:remaining|left|available)\b",
    r"\badd\s+(?:more\s+)?credits?\b",
    r"(?:credit|spend(?:ing)?|usage)\s+limit\s+(?:has\s+been\s+)?(?:reached|exceeded)",
    r"account\s+balance\s+(?:is\s+)?(?:too\s+low|insufficient|zero|depleted)",
    r"\bquota[_ ]exceeded\b",
    r"\bbilling[_ ]not[_ ]active\b",
)

# --- tier 2: weak markers, require an API-error co-signal on the same line --- #

_CREDIT_TIER2: Final[tuple[str, ...]] = (
    r"\bpayment\s+required\b",
    r"\berror\s+code:\s*402\b",
    r"\bhttp[/ ]?402\b",
    r"\bstatus(?:_code)?[=:]\s*402\b",
    r"plans?\s*&\s*billing",
    r"\bbilling\s+details\b",
    r"\bquota\b",
)

#: Something on the line must look like a provider error, so that a task email
#: mentioning a "quota" or an agent typing a billing address cannot void a real
#: model failure.
_ERROR_COSIGNAL: Final[tuple[str, ...]] = (
    r"error\s+code:",
    r"'type':\s*'error'",
    r'"type":\s*"error"',
    r"_error\b",
    r"\bBadRequestError\b",
    r"\bAPIStatusError\b",
    r"\bAPIError\b",
    r"\bRateLimitError\b",
    r"\bPermissionDeniedError\b",
    r"\bAuthenticationError\b",
    r"\bLLMCallError\b",
    r"llm_retry",
    r"API error",
    r"\bstatus_code\b",
    r"\bHTTP\s*[45]\d\d\b",
)

# --- other classes ---------------------------------------------------------- #

_RATE_LIMIT: Final[tuple[str, ...]] = (
    r"\brate[_ ]limit(?:_error|ed|ing)?\b",
    r"\btoo\s+many\s+requests\b",
    r"\berror\s+code:\s*429\b",
    r"\brequests?\s+per\s+minute\b",
    r"\btokens?\s+per\s+minute\b",
    r"\bretry[- ]after\b",
)

_OVERLOADED: Final[tuple[str, ...]] = (
    r"\boverloaded_error\b",
    r"\boverloaded\b",
    r"\berror\s+code:\s*529\b",
    r"\bcapacity\b.*\bexceeded\b",
    r"\bserver_error\b",
    r"\berror\s+code:\s*5\d\d\b",
)

_AUTH: Final[tuple[str, ...]] = (
    r"\bauthentication_error\b",
    r"\bpermission_error\b",
    r"\binvalid[_ ]api[_ ]key\b",
    r"\berror\s+code:\s*401\b",
    r"\berror\s+code:\s*403\b",
    r"\bunauthorized\b",
)

_CONTEXT: Final[tuple[str, ...]] = (
    r"context[_ ]length[_ ]exceeded",
    r"\bcontext\s+length\b",
    r"\bmaximum\s+context\b",
    r"prompt\s+is\s+too\s+long",
    r"\btoo\s+many\s+total\s+text\s+bytes\b",
)

_TIMEOUT: Final[tuple[str, ...]] = (
    r"\btimeout\b",
    r"\btimed\s+out\b",
    r"\bTimeoutError\b",
)

_CONNECTION: Final[tuple[str, ...]] = (
    r"\bAPIConnectionError\b",
    r"\bconnection\s+(?:reset|refused|error|aborted)\b",
    r"\bRemoteProtocolError\b",
)


def _compile(pats: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in pats), re.I)


CREDIT_TIER1_RE: Final = _compile(_CREDIT_TIER1)
CREDIT_TIER2_RE: Final = _compile(_CREDIT_TIER2)
ERROR_COSIGNAL_RE: Final = _compile(_ERROR_COSIGNAL)
RATE_LIMIT_RE: Final = _compile(_RATE_LIMIT)
OVERLOADED_RE: Final = _compile(_OVERLOADED)
AUTH_RE: Final = _compile(_AUTH)
CONTEXT_RE: Final = _compile(_CONTEXT)
TIMEOUT_RE: Final = _compile(_TIMEOUT)
CONNECTION_RE: Final = _compile(_CONNECTION)


def is_credit_exhaustion(text: Any) -> bool:
    """True when ``text`` carries a provider *insufficient credits / billing*
    signal for the whole error class — token form, prose form, or OpenAI's
    ``insufficient_quota`` 429.

    Tier-2 markers only count with an API-error co-signal on the same line, so
    task content ("billing address", "quota") cannot trigger a false void.
    """
    s = _as_text(text)
    if not s:
        return False
    if CREDIT_TIER1_RE.search(s):
        return True
    for line in s.splitlines():
        if CREDIT_TIER2_RE.search(line) and ERROR_COSIGNAL_RE.search(line):
            return True
    return False


def is_ordinary_rate_limit(text: Any) -> bool:
    """True for *transient* throttling only — explicitly NOT credit exhaustion.

    OpenAI returns billing exhaustion on HTTP 429 too, so credit wins the tie:
    an ``insufficient_quota`` 429 is a credit death, not a rate limit.
    """
    s = _as_text(text)
    if not s or is_credit_exhaustion(s):
        return False
    return bool(RATE_LIMIT_RE.search(s))


def classify_api_failure(text: Any) -> str | None:
    """Return the failure class for an exception / error string / log line.

    Order matters: credit exhaustion is checked first because it arrives dressed
    as a generic ``invalid_request_error`` 400 (Anthropic) or a ``429``
    (OpenAI), either of which a naive matcher would file as something benign.
    """
    s = _as_text(text)
    if not s:
        return None
    if is_credit_exhaustion(s):
        return CREDIT_EXHAUSTED
    if AUTH_RE.search(s):
        return AUTH_FAILED
    if CONTEXT_RE.search(s):
        return CONTEXT_OVERFLOW
    if RATE_LIMIT_RE.search(s):
        return RATE_LIMITED
    if OVERLOADED_RE.search(s):
        return OVERLOADED
    if TIMEOUT_RE.search(s):
        return TIMEOUT
    if CONNECTION_RE.search(s):
        return CONNECTION
    return None


def is_fatal_provider_failure(text_or_class: Any) -> bool:
    """True when the failure means the episode cannot yield a model decision.

    Accepts either a failure-class string or raw error text/exception.
    """
    if isinstance(text_or_class, str) and text_or_class in FAILURE_CLASSES:
        return text_or_class in FATAL_CLASSES
    return classify_api_failure(text_or_class) in FATAL_CLASSES


def _as_text(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, BaseException):
        return f"{type(text).__name__}: {text}"
    return str(text)


# --- raw-log scanning ------------------------------------------------------- #

#: ``agents._llm_retry.acall`` prints one of these verdicts per attempt.
_RETRY_LINE_RE: Final = re.compile(
    r"^\[llm_retry:(?P<label>[^\]]+)\]\s+attempt\s+(?P<attempt>\d+)/(?P<of>\d+)\s+"
    r"(?P<body>.*?)\s*->\s*(?P<verdict>retry|give up)\s*$",
    re.M,
)
_STEP_LINE_RE: Final = re.compile(r"^\[\w+(?:_agent)?\] step (\d+):", re.M)
_HARD_ERROR_RE: Final = re.compile(
    r"^\[[\w_]+\] API error:|^\[[\w_/]+\]\s+DISPATCH ERROR:|\bLLMCallError\b", re.M)


def scan_log_text(log_text: str) -> dict:
    """Classify an episode from its **raw worker log**.

    Returns a dict with:

    ``credit_death``
        The episode hit credit/billing exhaustion and could not continue. This is
        the flag that must exclude an episode from BREAK/HOLD counts.
    ``failure_class``
        Fatal class if any, else the most severe transient class observed, else
        ``None``.
    ``credit_hits`` / ``credit_gave_up``
        Occurrences of the credit class, and how many ended in ``-> give up``.
    ``transient``
        Counts per transient class that were retried and did not end the episode.
    ``steps_seen`` / ``credit_at_step``
        Step count in the log, and the step index the credit death landed on
        (``0`` means the very first model call failed — a zero-step episode).
    ``excerpt``
        First matching provider error line, for audit trails.

    Deliberately reads the raw text rather than a structured field: the pixel
    agents used to swallow non-retryable API errors with a bare ``break``, so the
    trajectory/result JSON ``error`` is empty for precisely these episodes.
    """
    out: dict = {
        "credit_death": False,
        "failure_class": None,
        "credit_hits": 0,
        "credit_gave_up": 0,
        "transient": {},
        "steps_seen": 0,
        "credit_at_step": None,
        "excerpt": "",
    }
    if not log_text:
        return out

    steps = [int(m.group(1)) for m in _STEP_LINE_RE.finditer(log_text)]
    out["steps_seen"] = (max(steps) + 1) if steps else 0

    transient: dict[str, int] = {}
    first_credit_pos: int | None = None

    for m in _RETRY_LINE_RE.finditer(log_text):
        body = m.group("body")
        verdict = m.group("verdict")
        cls = classify_api_failure(body)
        if cls == CREDIT_EXHAUSTED:
            out["credit_hits"] += 1
            if verdict == "give up":
                out["credit_gave_up"] += 1
            if first_credit_pos is None:
                first_credit_pos = m.start()
                out["excerpt"] = m.group(0)[:400]
        elif cls:
            # Retried and the loop continued -> transient, NOT contamination.
            transient[cls] = transient.get(cls, 0) + 1

    # Some paths print the failure only on the agent's own error line (or the
    # retry wrapper is bypassed entirely), so scan every line as a fallback.
    for line in log_text.splitlines():
        if is_credit_exhaustion(line):
            if first_credit_pos is None:
                first_credit_pos = log_text.find(line)
                out["excerpt"] = line[:400]
            if out["credit_hits"] == 0:
                out["credit_hits"] = 1
            break

    out["transient"] = transient

    if out["credit_hits"]:
        out["credit_death"] = True
        out["failure_class"] = CREDIT_EXHAUSTED
        if first_credit_pos is not None:
            before = log_text[:first_credit_pos]
            prior = [int(x) for x in _STEP_LINE_RE.findall(before)]
            out["credit_at_step"] = (max(prior) + 1) if prior else 0
    elif AUTH_RE.search(log_text) and _HARD_ERROR_RE.search(log_text):
        out["failure_class"] = AUTH_FAILED
    elif transient:
        for cls in (OVERLOADED, RATE_LIMITED, TIMEOUT, CONNECTION):
            if cls in transient:
                out["failure_class"] = cls
                break

    return out


def scan_log_file(path: str) -> dict:
    """``scan_log_text`` for a path; a missing/unreadable log scans as clean."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return scan_log_text(f.read())
    except OSError:
        return scan_log_text("")
