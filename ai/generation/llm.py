"""LLM providers.

`LLMProvider` is the interface every concrete provider implements. The
factory `get_provider()` picks one based on `LLM_PROVIDER` env var.

Provider waterfall strategy:
    1. GroqProvider  — primary (fast LPU inference, ~300ms)
    2. GeminiProvider — fallback (1M tokens/day free tier)

If Groq hits its rate limit (429) `get_provider_with_fallback()` automatically
switches to Gemini for that request. No other code needs to change.

Adding more providers = create another `LLMProvider` subclass and register
it in `_PROVIDERS`. No other code needs to change.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from config import (
    GEMINI_API_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
)


logger = logging.getLogger("foodshare.ai.llm")


class LLMError(RuntimeError):
    """Raised for any provider-level failure. Message is safe to log."""


class LLMRateLimitError(LLMError):
    """Raised specifically when a provider returns a 429 / rate-limit error."""


class LLMProvider(ABC):
    """Abstract LLM provider."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 150,
        temperature: float = 0.2,
    ) -> str: ...


# ---------------------------------------------------------------------------
# Groq  (primary — fast LPU inference, OpenAI-compatible API)
# ---------------------------------------------------------------------------


class GroqProvider(LLMProvider):
    """Groq via the `openai` SDK pointed at Groq's OpenAI-compatible endpoint.

    Required env: GROQ_API_KEY.
    Default model: llama-3.1-8b-instant  (fast, generous free tier).
    """

    _BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or GROQ_API_KEY or LLM_API_KEY or ""
        self.model = model or GROQ_MODEL
        if not self.api_key:
            raise LLMError(
                "GROQ_API_KEY is not configured. Set it in .env to use the "
                "Groq provider."
            )
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise LLMError(
                "openai SDK is not installed. "
                "Run `pip install openai` and try again."
            ) from exc
        self._client: Any = OpenAI(api_key=self.api_key, base_url=self._BASE_URL)

    @property
    def name(self) -> str:
        return "groq"

    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 150,
        temperature: float = 0.2,
    ) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "rate limit" in exc_str or "rate_limit" in exc_str:
                logger.warning("Groq rate limit hit: %s", exc)
                raise LLMRateLimitError("Groq rate limit reached") from exc
            logger.warning("Groq API error: %s", exc)
            raise LLMError("LLM provider failed") from exc

        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise LLMError("LLM provider returned empty response")
        return text


# ---------------------------------------------------------------------------
# Gemini  (fallback — 1M tokens/day free tier)
# ---------------------------------------------------------------------------


class GeminiProvider(LLMProvider):
    """Google Gemini via the `google-genai` SDK.

    Required env: GEMINI_API_KEY (or generic LLM_API_KEY).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or GEMINI_API_KEY or LLM_API_KEY or ""
        self.model = model or LLM_MODEL
        if not self.api_key:
            raise LLMError(
                "GEMINI_API_KEY is not configured. Set it in .env to use the "
                "Gemini provider."
            )
        # Import lazily so the module is loadable without the SDK installed.
        try:
            from google import genai  # type: ignore
        except ImportError as exc:
            raise LLMError(
                "google-genai SDK is not installed. "
                "Run `pip install google-genai` and try again."
            ) from exc
        self._client: Any = genai.Client(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "gemini"

    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 150,
        temperature: float = 0.2,
    ) -> str:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config={
                    "system_instruction": system,
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        except Exception as exc:  # noqa: BLE001 — wrap any provider error
            logger.warning("Gemini API error: %s", exc)
            raise LLMError("LLM provider failed") from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMError("LLM provider returned empty response")
        return text


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """Add a new provider at runtime. Useful for tests / future expansion."""
    _PROVIDERS[name.lower()] = cls


def get_provider(name: str | None = None) -> LLMProvider:
    """Pick a provider by env var (or override)."""
    chosen = (name or LLM_PROVIDER or "groq").lower()
    cls = _PROVIDERS.get(chosen)
    if cls is None:
        raise LLMError(
            f"Unknown LLM_PROVIDER: {chosen}. "
            f"Known: {sorted(_PROVIDERS)}. Register a new one via "
            "register_provider()."
        )
    return cls()


def get_provider_with_fallback() -> tuple[LLMProvider, LLMProvider | None]:
    """Return (primary, fallback) providers.

    Primary  = Groq  (fast, free, rate-limited)
    Fallback = Gemini (slower, 1M tokens/day)

    If either key is missing the corresponding provider is None.
    The caller should catch `LLMRateLimitError` from primary and retry
    with fallback.
    """
    primary: LLMProvider | None = None
    fallback: LLMProvider | None = None

    try:
        primary = GroqProvider()
    except LLMError as exc:
        logger.warning("Groq provider unavailable: %s", exc)

    try:
        fallback = GeminiProvider()
    except LLMError as exc:
        logger.warning("Gemini provider unavailable: %s", exc)

    if primary is None and fallback is None:
        raise LLMError(
            "No LLM provider is configured. "
            "Set GROQ_API_KEY and/or GEMINI_API_KEY in .env."
        )

    # If only one is available, use it as primary
    if primary is None:
        return fallback, None  # type: ignore[return-value]

    return primary, fallback


def generate_with_fallback(
    *,
    system: str,
    user: str,
    max_tokens: int = 150,
    temperature: float = 0.2,
) -> tuple[str, str]:
    """Generate a response using Groq, falling back to Gemini on rate limit.

    Returns (response_text, provider_name_used).
    """
    primary, fallback = get_provider_with_fallback()

    try:
        text = primary.generate(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return text, primary.name
    except LLMError as exc:
        # Fall back to Gemini on ANY Groq error: rate limit, bad model,
        # invalid key, network issues, etc.
        if fallback is None:
            raise LLMError(
                f"Primary provider ({primary.name}) failed and no fallback is "
                "configured. Set GEMINI_API_KEY in .env."
            ) from exc
        logger.info(
            "Primary provider (%s) failed (%s) — switching to Gemini fallback.",
            primary.name, exc,
        )
        text = fallback.generate(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return text, fallback.name
