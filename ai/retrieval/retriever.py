"""Retriever: embed a query, search the vector store, return hits.

Kept as a thin orchestrator so it can be invoked directly in tests without
spinning up the FastAPI app.
"""

from __future__ import annotations

import logging

from config import SIMILARITY_THRESHOLD, TOP_K
from ai.retrieval.embedder import EmbeddingProvider, get_default_embedding_provider
from ai.retrieval.models import RetrievalHit
from ai.retrieval.vector_store import VectorStore, get_default_vector_store


logger = logging.getLogger("foodshare.ai.retriever")


class Retriever:
    def __init__(
        self,
        store: VectorStore | None = None,
        embedder: EmbeddingProvider | None = None,
        similarity_threshold: float | None = None,
        top_k: int | None = None,
    ) -> None:
        self.store = store or get_default_vector_store()
        self.embedder = embedder or get_default_embedding_provider()
        self.threshold = (
            similarity_threshold if similarity_threshold is not None
            else SIMILARITY_THRESHOLD
        )
        self.top_k = top_k if top_k is not None else TOP_K

    def retrieve(self, query: str) -> list[RetrievalHit]:
        """Embed + search. Returns hits above the similarity threshold.

        If the top hit is below the threshold, returns an empty list (this
        signals "no relevant information" downstream).
        """
        if not query or not query.strip():
            return []
        vec = self.embedder.embed_query(query)
        hits = self.store.search(vec, self.top_k)
        if not hits:
            return []
        # Threshold gate: if the best hit is too weak, treat as no evidence.
        if hits[0].score < self.threshold:
            return []
        return hits


def get_default_retriever() -> Retriever:
    return Retriever()


def retrieve(query: str) -> list[RetrievalHit]:
    """Convenience wrapper."""
    return get_default_retriever().retrieve(query)
