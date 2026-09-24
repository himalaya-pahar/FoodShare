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

from config import EMBEDDING_DIM, EMBEDDINGS_MODEL, SENTENCE_TRANSFORMERS_HOME


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
            from sentence_transformers import SentenceTransformer
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


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_provider: EmbeddingProvider | None = None


def get_default_embedding_provider() -> EmbeddingProvider:
    """Process-wide singleton embedding provider."""
    global _provider
    if _provider is None:
        _provider = LocalSentenceTransformerProvider()
    return _provider


def reset_default_embedding_provider() -> None:
    """Used by tests to force a fresh provider."""
    global _provider
    _provider = None
