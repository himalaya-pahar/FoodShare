"""Ingestion orchestrator: loader → chunker → embedder → vector store.

Run as a script:
    python -m ai.ingestion.indexer
"""

from __future__ import annotations

import logging
import sys

from ai.ingestion.chunker import chunk_document
from ai.ingestion.loader import (
    assert_no_env_keys_present,
    load_all_documents,
)
from ai.retrieval.embedder import get_default_embedding_provider
from ai.retrieval.models import Chunk
from ai.retrieval.vector_store import get_default_vector_store
from ai.setup_db import ensure


logger = logging.getLogger("foodshare.ai.indexer")


def _chunks_from_documents(documents) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in documents:
        assert_no_env_keys_present(doc.content, doc.name)
        chunks.extend(chunk_document(doc.name, doc.content))
    return chunks


def reindex(
    clear_first: bool = True,
    progress: bool = True,
) -> dict:
    """Rebuild the entire vector index from the knowledge base.

    Returns a small report dict (counts + how long it took).
    """
    import time

    started = time.perf_counter()
    ensure()

    documents = load_all_documents()
    if progress:
        print(f"Loaded {len(documents)} document(s) from knowledge base.")

    chunks = _chunks_from_documents(documents)
    if progress:
        print(f"Produced {len(chunks)} chunk(s).")

    if not chunks:
        return {
            "documents": len(documents),
            "chunks": 0,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }

    embedder = get_default_embedding_provider()
    store = get_default_vector_store()

    if clear_first:
        store.clear()

    # Embed in batches to keep payload sizes sane.
    BATCH = 32
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        vectors = embedder.embed([c.text for c in batch])
        store.add_chunks(batch, vectors)
        if progress:
            print(f"  indexed {i + len(batch)}/{len(chunks)}")

    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = list(sys.argv[1:] if argv is None else argv)
    clear_first = "--no-clear" not in args

    report = reindex(clear_first=clear_first, progress=True)
    print(f"Done. Indexed {report['chunks']} chunks from "
          f"{report['documents']} documents in {report['elapsed_seconds']}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
