"""Tests for the retriever using a stub EmbeddingProvider + stub VectorStore.

No network, no DB. Verifies the threshold gate + glue.
"""

from dataclasses import dataclass

from ai.retrieval.embedder import EmbeddingProvider
from ai.retrieval.models import RetrievalHit
from ai.retrieval.retriever import Retriever
from ai.retrieval.vector_store import VectorStore


@dataclass
class StubEmbedder(EmbeddingProvider):
    dim: int = 8

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Deterministic per-text embeddings so tests are reproducible.
        return [
            [float((hash(t) % 9)) / 10.0] * self.dim for t in texts
        ]

    def embed_query(self, text: str) -> list[float]:
        return [float((hash(text) % 9)) / 10.0] * self.dim


@dataclass
class StubStore(VectorStore):
    hits_to_return: list[RetrievalHit] = None

    def __post_init__(self):
        if self.hits_to_return is None:
            self.hits_to_return = []
        self.queries = []

    def add_chunks(self, chunks, vectors):
        return None

    def search(self, query_vector, top_k):
        self.queries.append((query_vector, top_k))
        return list(self.hits_to_return)[:top_k]

    def count(self) -> int:
        return len(self.hits_to_return)

    def clear(self) -> None:
        return None


def test_returns_empty_for_empty_query():
    r = Retriever(store=StubStore(), embedder=StubEmbedder())
    assert r.retrieve("") == []


def test_returns_empty_when_top_score_below_threshold():
    weak_hit = RetrievalHit(
        chunk_id="x-1",
        document="d.md",
        section="s",
        text="low",
        score=0.10,
    )
    r = Retriever(
        store=StubStore(hits_to_return=[weak_hit]),
        embedder=StubEmbedder(),
        similarity_threshold=0.55,
    )
    assert r.retrieve("anything") == []


def test_returns_hits_when_above_threshold():
    strong_hit = RetrievalHit(
        chunk_id="x-1",
        document="d.md",
        section="s",
        text="hi",
        score=0.95,
    )
    r = Retriever(
        store=StubStore(hits_to_return=[strong_hit, strong_hit]),
        embedder=StubEmbedder(),
        similarity_threshold=0.55,
        top_k=2,
    )
    out = r.retrieve("anything")
    assert len(out) == 2
    assert all(h.score >= 0.55 for h in out)


def test_top_k_is_respected():
    many = [
        RetrievalHit(
            chunk_id=f"x-{i}",
            document="d.md",
            section="s",
            text="t",
            score=0.9,
        )
        for i in range(10)
    ]
    r = Retriever(
        store=StubStore(hits_to_return=many),
        embedder=StubEmbedder(),
        top_k=3,
    )
    assert len(r.retrieve("q")) == 3


def test_embedder_is_called():
    store = StubStore(hits_to_return=[
        RetrievalHit(chunk_id="x", document="d.md", section="s", text="t", score=0.9)
    ])
    r = Retriever(store=store, embedder=StubEmbedder())
    r.retrieve("hello world")
    assert len(store.queries) == 1
