"""Vector store: thin abstraction + Supabase pgvector implementation.

The module deliberately keeps the public surface small so we can swap
implementations later. All methods are synchronous and chunk-level.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterable

from sqlalchemy import text

import database as d_b
from ai.retrieval.embedder import EmbeddingProvider, get_default_embedding_provider
from ai.retrieval.models import Chunk, RetrievalHit
from ai.setup_db import ensure_pgvector_available


logger = logging.getLogger("foodshare.ai.vector_store")


class VectorStore(ABC):
    @abstractmethod
    def add_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    @abstractmethod
    def search(
        self, query_vector: list[float], top_k: int
    ) -> list[RetrievalHit]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...


class SupabasePgVectorStore(VectorStore):
    """pgvector-backed store in the same Postgres DB the app already uses."""

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        ensure_pgvector_available()
        self.embedder = embedder or get_default_embedding_provider()

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------

    def add_chunks(
        self, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        if not chunks:
            return

        # pgvector accepts the textual form `[a,b,c,...]` cast to `::vector`.
        # Binding a Python list[float] directly works only when SQLAlchemy
        # knows about the VECTOR type via pgvector.sqlalchemy.Vector at
        # column level. We're using raw `text()` SQL with bound params here,
        # so we render the vector literal into the SQL string for safety +
        # version-agnostic behavior across pgvector releases.
        def vec_literal(v: list[float]) -> str:
            return "[" + ",".join(repr(float(x)) for x in v) + "]"

        rows = [
            {
                "chunk_id": c.chunk_id,
                "document": c.document,
                "section": c.section,
                "content": c.text,
                "embedding": vec_literal(v),
            }
            for c, v in zip(chunks, vectors)
        ]

        with d_b.engine.begin() as conn:
            # ON CONFLICT DO UPDATE makes this rerunnable on the same content.
            conn.execute(
                text(
                    """
                    INSERT INTO ai_chunks
                        (chunk_id, document, section, content, embedding)
                    VALUES
                        (:chunk_id, :document, :section, :content,
                         CAST(:embedding AS vector))
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        document = EXCLUDED.document,
                        section = EXCLUDED.section,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding
                    """
                ),
                rows,
            )

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------

    def search(self, query_vector: list[float], top_k: int) -> list[RetrievalHit]:
        # pgvector cosine distance: 1 - cosine similarity.
        # We expose similarity (0..1) by computing 1 - distance.
        # Same reasoning as add_chunks: render the vector literal + cast.
        qvec_literal = (
            "[" + ",".join(repr(float(x)) for x in query_vector) + "]"
        )
        sql = text(
            """
            SELECT
                chunk_id,
                document,
                section,
                content,
                1 - (embedding <=> CAST(:qvec AS vector)) AS score
            FROM ai_chunks
            ORDER BY embedding <=> CAST(:qvec AS vector) ASC
            LIMIT :limit
            """
        )

        with d_b.engine.connect() as conn:
            rows = conn.execute(
                sql,
                {"qvec": qvec_literal, "limit": int(top_k)},
            ).fetchall()

        hits: list[RetrievalHit] = []
        for row in rows:
            score = float(row.score)
            # Clamp to [0, 1] — pgvector may yield slightly negative for orthogonal
            # vectors.
            score = max(0.0, min(1.0, score))
            hits.append(
                RetrievalHit(
                    chunk_id=row.chunk_id,
                    document=row.document,
                    section=row.section,
                    text=row.content,
                    score=score,
                )
            )
        return hits

    def count(self) -> int:
        with d_b.engine.connect() as conn:
            return int(
                conn.execute(text("SELECT COUNT(*) FROM ai_chunks;")).scalar() or 0
            )

    def clear(self) -> None:
        with d_b.engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE ai_chunks RESTART IDENTITY;"))


def get_default_vector_store() -> VectorStore:
    return SupabasePgVectorStore()
