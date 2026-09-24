"""Data models for the retrieval layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    """A single piece of indexed knowledge-base content."""

    chunk_id: str
    document: str
    section: str
    text: str
    order: int = 0

    model_config = ConfigDict(from_attributes=True)


class RetrievalHit(BaseModel):
    """One top-K result returned by the vector store."""

    chunk_id: str
    document: str
    section: str
    text: str
    score: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)