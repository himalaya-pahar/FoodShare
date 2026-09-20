"""Idempotent setup for the AI vector store.

Runs:
    1. CREATE EXTENSION IF NOT EXISTS vector;
    2. CREATE TABLE IF NOT EXISTS ai_chunks (...);

Safe to call multiple times. Called by ai.ingestion.indexer before indexing
and by scripts/reindex_kb.py.

Note on `register_vector`: pgvector's older releases exposed a
`pgvector.sqlalchemy.register_vector()` helper that registered the VECTOR
type on a SQLAlchemy 1.x Dialect. That function is gone in newer pgvector
releases (0.4+) because SQLAlchemy 2.x + the pgvector `Vector` type work
together natively — you import `Vector` from `pgvector.sqlalchemy` and use
it directly. This module therefore does NOT call `register_vector`.
"""

from __future__ import annotations

import logging

import database as d_b
from config import EMBEDDING_DIM


logger = logging.getLogger("foodshare.ai.setup_db")


SQL_CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector;"

SQL_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS ai_chunks (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    document TEXT NOT NULL,
    section TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SQL_CREATE_INDEX_IVFFLAT = f"""
CREATE INDEX IF NOT EXISTS ai_chunks_embedding_ivf
ON ai_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
"""


def ensure_pgvector_available() -> None:
    """Fail fast with a helpful message if pgvector Python package is missing.

    Does NOT register the type on the dialect — that step is unnecessary
    with SQLAlchemy 2.x and modern pgvector releases.
    """
    try:
        from pgvector.sqlalchemy import Vector  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "The 'pgvector' Python package is not installed. "
            "Run `pip install pgvector` and try again."
        ) from exc


def ensure() -> None:
    """Idempotent: extension + table + (best-effort) ivfflat index."""
    ensure_pgvector_available()

    with d_b.engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(text(SQL_CREATE_EXTENSION))
        conn.execute(text(SQL_CREATE_TABLE))

        # ivfflat requires rows before it can be created on some Postgres
        # versions; swallow errors and skip. Index on cosine is the goal but
        # exact (slow) search works fine for a few thousand rows anyway.
        try:
            conn.execute(text(SQL_CREATE_INDEX_IVFFLAT))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping ivfflat index creation (will retry later): %s", exc
            )


def drop_all() -> None:
    """Hard reset. Used by reindex script."""
    ensure_pgvector_available()
    with d_b.engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(text("DROP TABLE IF EXISTS ai_chunks CASCADE;"))


def count_rows() -> int:
    ensure_pgvector_available()
    with d_b.engine.connect() as conn:
        from sqlalchemy import text

        return int(conn.execute(text("SELECT COUNT(*) FROM ai_chunks;")).scalar() or 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure()
    print(f"ai_chunks ready (rows={count_rows()})")
