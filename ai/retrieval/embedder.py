"""Embedding providers.

v1 ships with one provider:

    `LocalSentenceTransformerProvider` — runs a sentence-transformers model
    in-process. The model is downloaded the first time the provider is
    instantiated and cached on disk (default `~/.cache/huggingface/hub/`).
    On subsequent boots the model is loaded from the cache, so no network
    is required.

Production deployment notes:
    - For Docker images: pre-download the model inside the image by running
      `RUN python -c "from sentence_transformers import SentenceTransformer; \\
          SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"`
      during the build. This bakes the model into a layer so the first
      server boot has no cold-start latency and no internet requirement.
    - For serverless platforms with ephemeral filesystems (Vercel, AWS
      Lambda): override `SENTENCE_TRANSFORMERS_HOME` to a path you control
      and use a layer / image to ship the model. Otherwise cold starts will
      re-download it on every invocation (~80 MB).
    - For hardware-bound environments: the model uses ~200-500 MB of RAM
      after load and runs in ~5-30 ms per query on a modern CPU.
"""

from __future__ import annotations

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from functools import lru_cache

from config import (
    EMBEDDING_DIM,
    EMBEDDING_PROVIDER,
    EMBEDDINGS_MODEL,
    GEMINI_API_KEY,
    LLM_API_KEY,
    SENTENCE_TRANSFORMERS_HOME,
)


logger = logging.getLogger("foodshare.ai.embedder")


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class LocalSentenceTransformerProvider(EmbeddingProvider):
    """In-process sentence-transformers provider.

    Lazily loads the underlying SentenceTransformer on first use so that
    importing this module does not pay the model-load cost. Subsequent
    calls are fast (~5-30 ms per query on CPU).
    """

    def __init__(
        self,
        model_name: str = EMBEDDINGS_MODEL,
        cache_size: int = 256,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self._cache: dict[str, list[float]] = {}
        self._cache_size = cache_size
        self._device = device  # None => library default (cuda if available)
        self._model = None  # lazy

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The 'sentence-transformers' Python package is not installed. "
                "Run `pip install sentence-transformers` and try again."
            ) from exc

        if SENTENCE_TRANSFORMERS_HOME:
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = SENTENCE_TRANSFORMERS_HOME

        logger.info(
            "Loading sentence-transformers model %r (one-time cost)...",
            self.model_name,
        )
        kwargs = {}
        if self._device:
            kwargs["device"] = self._device
        self._model = SentenceTransformer(self.model_name, **kwargs)
        logger.info("Model loaded.")
        return self._model

    @property
    def dim(self) -> int:
        return EMBEDDING_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        # SentenceTransformer.encode returns numpy float32 vectors; convert.
        vectors = model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=False,
        )
        result: list[list[float]] = []
        for text, vec in zip(texts, vectors):
            as_list = [float(x) for x in vec]
            result.append(as_list)
            self._cache_put(text, as_list)
        return result

    def embed_query(self, text: str) -> list[float]:
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        [vec] = self.embed([text])
        return vec

    # Tiny cache ----------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_get(self, text: str) -> list[float] | None:
        return self._cache.get(self._cache_key(text))

    def _cache_put(self, text: str, vec: list[float]) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            self._cache.pop(oldest, None)
        self._cache[self._cache_key(text)] = vec


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Cloud embedding provider using Google Gemini via google-genai SDK.

    Default model: text-embedding-004 (768 dimensions).
    Fast, serverless-friendly, and requires no local PyTorch or GPU dependencies.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        cache_size: int = 256,
    ) -> None:
        self.api_key = api_key or GEMINI_API_KEY or LLM_API_KEY or ""
        self.model_name = model_name or EMBEDDINGS_MODEL
        self._cache: dict[str, list[float]] = {}
        self._cache_size = cache_size
        self._client = None

        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY (or LLM_API_KEY) is not configured in .env. "
                "Set it to use the Gemini embedding provider."
            )

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "The 'google-genai' SDK is not installed. "
                    "Run `pip install google-genai` and try again."
                ) from exc
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @property
    def dim(self) -> int:
        return EMBEDDING_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        client = self._get_client()
        result: list[list[float]] = []
        batch_size = 50

        from google.genai import types  # type: ignore

        config = types.EmbedContentConfig(output_dimensionality=self.dim)

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.models.embed_content(
                model=self.model_name,
                contents=batch,
                config=config,
            )
            embeddings = getattr(response, "embeddings", None)
            if not embeddings:
                if hasattr(response, "embedding"):
                    embeddings = [response.embedding]
                else:
                    raise RuntimeError("Gemini embed_content returned no embeddings")

            for text, emb in zip(batch, embeddings):
                values = getattr(emb, "values", emb)
                as_list = [float(x) for x in values]
                result.append(as_list)
                self._cache_put(text, as_list)

        return result

    def embed_query(self, text: str) -> list[float]:
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        [vec] = self.embed([text])
        return vec

    # Cache helpers --------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_get(self, text: str) -> list[float] | None:
        return self._cache.get(self._cache_key(text))

    def _cache_put(self, text: str, vec: list[float]) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            self._cache.pop(oldest, None)
        self._cache[self._cache_key(text)] = vec


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_provider: EmbeddingProvider | None = None


def get_default_embedding_provider() -> EmbeddingProvider:
    """Process-wide singleton embedding provider."""
    global _provider
    if _provider is None:
        provider_type = (EMBEDDING_PROVIDER or "gemini").lower()
        if provider_type in ("sentence-transformers", "local"):
            _provider = LocalSentenceTransformerProvider()
        else:
            _provider = GeminiEmbeddingProvider()
    return _provider


def reset_default_embedding_provider() -> None:
    """Used by tests to force a fresh provider."""
    global _provider
    _provider = None
