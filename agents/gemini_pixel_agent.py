"""Gemini 3.1 Pro PIXEL / Set-of-Mark browser agent.

Thin specialisation of :class:`OpenAIPixelAgent` pointed at Google's
OpenAI-compatible Gemini endpoint (AI Studio or Vertex). Same SoM
perception, multi-tab tools, ``eval_mode``, and dynamic context guard as
the Qwen / openai_pixel agents.

Configure via env:

  AI Studio (default):
    GEMINI_API_KEY=<key>                      (or GOOGLE_API_KEY)
    GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    GEMINI_MODEL=gemini-3.1-pro-preview

  Vertex OpenAI-compatible (optional):
    GEMINI_USE_VERTEX=1
    GOOGLE_CLOUD_PROJECT=<project>
    GEMINI_VERTEX_LOCATION=global             (or us-central1, etc.)
    # Auth: Application Default Credentials / Cloud Run SA
    # GEMINI_API_KEY may be omitted when Vertex ADC is available; the OpenAI
    # client still needs a bearer — set GEMINI_API_KEY to an OAuth access
    # token, or prefer AI Studio / OpenRouter for the simplest path.

  OpenRouter proxy (optional):
    GEMINI_BASE_URL=https://openrouter.ai/api/v1
    GEMINI_API_KEY=<openrouter key>
    GEMINI_MODEL=google/gemini-3.1-pro-preview

Default model id: ``gemini-3.1-pro-preview`` (Gemini 3.1 Pro preview).
"""

from __future__ import annotations

import os

from agents.openai_pixel_agent import OpenAIPixelAgent

_DEFAULT_AISTUDIO = "https://generativelanguage.googleapis.com/v1beta/openai/"
_DEFAULT_MODEL = "gemini-3.1-pro-preview"


def _vertex_base_url() -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or ""
    location = os.getenv("GEMINI_VERTEX_LOCATION", "global")
    if not project:
        raise RuntimeError(
            "GEMINI_USE_VERTEX=1 requires GOOGLE_CLOUD_PROJECT (or GCP_PROJECT)"
        )
    # Vertex OpenAI-compatible endpoint
    return (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/"
        f"{project}/locations/{location}/endpoints/openapi"
    )


def default_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)


def resolve_gemini_endpoint() -> tuple[str, str | None]:
    """Return (base_url, api_key) for the OpenAI-compatible client."""
    if os.getenv("GEMINI_USE_VERTEX", "").strip() in ("1", "true", "TRUE", "yes"):
        base = os.getenv("GEMINI_BASE_URL") or _vertex_base_url()
    else:
        base = os.getenv("GEMINI_BASE_URL") or _DEFAULT_AISTUDIO
    key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
    )
    return base, key


class GeminiPixelAgent(OpenAIPixelAgent):
    """SoM + multi-tab agent driven by Gemini 3.1 Pro over OpenAI-compat."""

    def __init__(self, model: str | None = None, max_steps: int | None = None,
                 verbose: bool = True, eval_mode: bool | None = None):
        base_url, api_key = resolve_gemini_endpoint()
        if not api_key and not os.getenv("GEMINI_MOCK"):
            # OpenAI client requires a non-empty key string even for some
            # ADC-backed Vertex setups that inject auth elsewhere.
            api_key = api_key or "UNUSED"
        super().__init__(
            model=model or default_gemini_model(),
            max_steps=max_steps,
            verbose=verbose,
            base_url=base_url,
            api_key=api_key,
            eval_mode=eval_mode,
        )
