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
from config import EMBEDDING_DIM, IVFFLAT_MIN_ROWS


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

SQL_CREATE_INDEX_IVFFLAT = """
CREATE INDEX IF NOT EXISTS ai_chunks_embedding_ivf
ON ai_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = :lists);
"""


# pgvector's recommended `lists` is roughly sqrt(row_count), clamped to a
# sensible range. With lists = sqrt(rows), each list holds ~sqrt(rows) rows
# and a probe touches ~1 list for an exact match — the sweet spot.
# (Threshold `IVFFLAT_MIN_ROWS` is defined in config.py so it can be tuned
# via the AI_IVFFLAT_MIN_ROWS env var without editing source.)
def _ivfflat_lists_for_rows(row_count: int) -> int:
    """Pick `lists` for ivfflat based on current row count.

    - Below IVFFLAT_MIN_ROWS: caller should skip index creation entirely.
    - Otherwise: lists = clamp(round(sqrt(rows)), 10, 1000).
    """
    return max(10, min(1000, int(round(row_count ** 0.5))))


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


def _table_row_count(conn) -> int:
    """Return current row count of ai_chunks (0 if missing)."""
    from sqlalchemy import text

    try:
        return int(
            conn.execute(text("SELECT COUNT(*) FROM ai_chunks;")).scalar() or 0
        )
    except Exception:
        return 0


def _ivfflat_index_exists(conn) -> bool:
    """True if the ivfflat index is already present."""
    from sqlalchemy import text

    return bool(
        conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM pg_indexes "
                "  WHERE tablename = 'ai_chunks' "
                "    AND indexname = 'ai_chunks_embedding_ivf'"
                ");"
            )
        ).scalar()
    )


def ensure() -> None:
    """Idempotent: extension + table + (best-effort, sized) ivfflat index.

    The ivfflat index is only created when there are enough rows to make it
    useful (`>= IVFFLAT_MIN_ROWS`), and with a `lists` value scaled to the
    current row count. Below the threshold we skip it — sequential scan is
    faster and avoids the silent-empty-result bug from over-partitioned
    ivfflat (lists=100 on a 50-row table is pathological).
    """
    ensure_pgvector_available()

    from sqlalchemy import text

    with d_b.engine.begin() as conn:
        conn.execute(text(SQL_CREATE_EXTENSION))
        conn.execute(text(SQL_CREATE_TABLE))

        rows = _table_row_count(conn)
        if rows < IVFFLAT_MIN_ROWS:
            logger.info(
                "Skipping ivfflat index (rows=%d < %d). "
                "Sequential scan is faster for small tables.",
                rows,
                IVFFLAT_MIN_ROWS,
            )
            return

        # Already present with any lists value — leave it alone. If someone
        # needs to resize they can DROP and let ensure() recreate it.
        if _ivfflat_index_exists(conn):
            logger.info(
                "ivfflat index already present on ai_chunks (rows=%d).", rows
            )
            return

        lists = _ivfflat_lists_for_rows(rows)
        try:
            conn.execute(text(SQL_CREATE_INDEX_IVFFLAT), {"lists": lists})
            logger.info(
                "Created ivfflat index on ai_chunks (rows=%d, lists=%d).",
                rows,
                lists,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping ivfflat index creation (rows=%d, lists=%d): %s",
                rows,
                lists,
                exc,
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
