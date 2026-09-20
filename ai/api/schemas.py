"""Pydantic schemas for the AI Assistant API.

Mirror the style of the project's main schemas.py (BaseModel + Field).
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Bounds — kept here so route + guardrails agree on a single source of truth.
MIN_MESSAGE_LEN = 1
MAX_MESSAGE_LEN = 1000
MAX_SESSION_ID_LEN = 64


class ChatRequest(BaseModel):
    """Body for POST /ai/chat.

    `session_id` is optional: if absent or null, the server creates a new one
    and returns it. Otherwise it must be a UUID-shaped string of bounded length.
    """

    message: str = Field(
        ...,
        min_length=MIN_MESSAGE_LEN,
        max_length=MAX_MESSAGE_LEN,
        description="The user's question about FoodShare.",
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=MAX_SESSION_ID_LEN,
        description="Optional session id for multi-turn chat. Created if absent.",
    )


class SourceItem(BaseModel):
    """Citation returned alongside an answer."""

    document: str = Field(..., description="Knowledge-base document filename.")
    section: str = Field(..., description="Section heading inside that document.")


class ChatResponse(BaseModel):
    """Body returned from POST /ai/chat."""

    session_id: str = Field(..., description="Session id to use on follow-up turns.")
    answer: str = Field(..., description="The assistant's grounded answer.")
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Citations backing the answer (may be empty).",
    )
    scope_decision: str = Field(
        ...,
        description="One of: in_domain | out_of_domain | no_evidence.",
    )

    model_config = ConfigDict(from_attributes=True)


def coerce_session_id(raw: Optional[str]) -> Optional[uuid.UUID]:
    """Best-effort parse of a client-provided session id.

    Returns None if raw is empty/None. Raises ValueError if non-empty but malformed.
    The route layer is responsible for translating that into a 422.
    """
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise ValueError("session_id must be a UUID") from exc
