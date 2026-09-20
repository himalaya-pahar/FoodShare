"""Input validation for the AI chat endpoint.

The pydantic layer in api/schemas.py enforces structural bounds (length,
session_id shape). This module holds deeper semantic checks that don't
belong in the schema (e.g. detecting obvious prompt-injection attempts).
"""

from __future__ import annotations

import re

from ai.api.schemas import (
    MAX_MESSAGE_LEN,
    MIN_MESSAGE_LEN,
    coerce_session_id,
)


class InputValidationError(ValueError):
    """Raised when user input fails a guardrail check."""


def validate_message(message: str) -> str:
    """Strip + return the message, or raise InputValidationError.

    - Trims surrounding whitespace.
    - Rejects empty messages.
    - Rejects messages that are obviously not a question / command (e.g. only punctuation).
    - Best-effort detection of common prompt-injection patterns. These are still
      answered if in-domain, but logged so we can see attempts.
    """
    if not isinstance(message, str):
        raise InputValidationError("message must be a string")

    text = message.strip()
    if len(text) < MIN_MESSAGE_LEN:
        raise InputValidationError("message is empty")
    if len(text) > MAX_MESSAGE_LEN:
        raise InputValidationError(
            f"message exceeds {MAX_MESSAGE_LEN} characters"
        )
    if not re.search(r"[A-Za-z0-9]", text):
        raise InputValidationError(
            "message must contain at least one letter or digit"
        )
    return text


def validate_session_id(raw: str | None) -> str | None:
    """Validate + canonicalize the session_id.

    Returns None when no id is supplied (caller should mint a new one).
    Raises InputValidationError when the id is non-empty but malformed.
    """
    if raw is None or raw == "":
        return None
    try:
        uid = coerce_session_id(raw)
    except ValueError as exc:
        raise InputValidationError(str(exc)) from exc
    return str(uid)


_INJECTION_HINTS = re.compile(
    r"(?i)\b(ignore (the )?(previous|above|system)"
    r"|disregard (the )?(instructions|prompt)"
    r"|act as (an? )?admin"
    r"|reveal (your|the) (system|hidden) prompt"
    r"|print (your|the) (system|hidden) prompt"
    r"|jailbreak"
    r"|developer mode)\b"
)


def looks_like_injection(message: str) -> bool:
    """Cheap heuristic for prompt-injection style phrasing.

    Not a security guarantee — the system prompt is the real defense. This is
    only for logging so we can see attempts.
    """
    return bool(_INJECTION_HINTS.search(message))
