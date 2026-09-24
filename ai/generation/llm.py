"""LLM providers.

`LLMProvider` is the interface every concrete provider implements. The
factory `get_provider()` picks one based on `LLM_PROVIDER` env var.

v1 ships with:
    - GeminiProvider   (initial; uses the google-genai SDK)

Adding more providers (OpenAI, Anthropic, Ollama, …) = create another
`LLMProvider` subclass and register it in `_PROVIDERS`. No other code
needs to change.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from config import (
    GEMINI_API_KEY,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
)


logger = logging.getLogger("foodshare.ai.llm")


class LLMError(RuntimeError):
    """Raised for any provider-level failure. Message is safe to log."""


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
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> str: ...


# ---------------------------------------------------------------------------
# Gemini
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
        max_tokens: int = 500,
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
    "gemini": GeminiProvider,
}


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """Add a new provider at runtime. Useful for tests / future expansion."""
    _PROVIDERS[name.lower()] = cls


def get_provider(name: str | None = None) -> LLMProvider:
    """Pick a provider by env var (or override)."""
    chosen = (name or LLM_PROVIDER or "gemini").lower()
    cls = _PROVIDERS.get(chosen)
    if cls is None:
        raise LLMError(
            f"Unknown LLM_PROVIDER: {chosen}. "
            f"Known: {sorted(_PROVIDERS)}. Register a new one via "
            "register_provider()."
        )
    return cls()
