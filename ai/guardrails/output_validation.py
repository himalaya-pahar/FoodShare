"""Output validation for safe, user-facing assistant answers."""

from __future__ import annotations

import logging
import re

from ai.guardrails.scope_check import (
    OUT_OF_DOMAIN_REFUSAL,
    OUT_OF_DOMAIN_KEYWORDS,
)


logger = logging.getLogger("foodshare.ai.guardrails.output")


SAFE_FALLBACK_NO_EVIDENCE = (
    "I can help with FoodShare accounts, donations, pickup requests, and "
    "the steps available in the app. Please ask about one of those."
)
SAFE_FALLBACK_TEMPORARY = (
    "The FoodShare assistant is temporarily unavailable. Please try again later."
)
SAFE_FALLBACK_PRIVATE = (
    "I can explain how to use FoodShare, but I cannot provide private "
    "technical or security details."
)


# Tiny blocklist for post-generation drift detection. Used as a soft signal:
# if the LLM answer contains a strong out-of-domain cue AND no in-domain cue,
# we surface the safe-fallback instead of an answer that wandered off-topic.
_DRIFT_HINT_RE = re.compile(
    r"(?i)\b(" + "|".join(re.escape(w) for w in OUT_OF_DOMAIN_KEYWORDS) + r")\b"
)
_ONDOMAIN_HINT_RE = re.compile(
    r"(?i)\b(foodshare|donation|pickup|ngo|restaurant|admin|signup|approval)\b"
)


def safe_fallback_no_evidence() -> str:
    return SAFE_FALLBACK_NO_EVIDENCE


def safe_fallback_temporary() -> str:
    return SAFE_FALLBACK_TEMPORARY


def safe_fallback_private() -> str:
    return SAFE_FALLBACK_PRIVATE


def looks_like_offtopic_drift(answer: str) -> bool:
    """Cheap check: LLM answer mentions out-of-domain cues with no in-domain ones."""
    drift = _DRIFT_HINT_RE.search(answer)
    if not drift:
        return False
    return not _ONDOMAIN_HINT_RE.search(answer)


def sanitize(answer: str) -> str:
    """Last-resort secret redaction. Belt-and-suspenders — the model should not leak keys."""
    # Redact anything that looks like a JWT (3 dot-separated base64url segments).
    answer = re.sub(
        r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        "[REDACTED_JWT]",
        answer,
    )
    # Redact obvious sk- / sb_secret_ / supabase keys.
    answer = re.sub(
        r"(sk-[A-Za-z0-9_\-]{16,}|sb_secret_[A-Za-z0-9_\-]{16,})",
        "[REDACTED_KEY]",
        answer,
    )
    return answer


# Internal implementation details are never part of the user-facing product
# help surface, even when a model has inferred or repeated them.
_PRIVATE_DETAIL_RE = re.compile(
    r"(?ix)"
    r"(https?://|/v\d+/|\b(api_key|endpoint|bearer\s+token|secret_key|"
    r"database|supabase|pgvector|repository|schema|source code|stack trace|"
    r"system prompt|system instruction|internal instruction|config|"
    r"knowledge\s+base|source\s+document|citation|sources\s+section)\b|"
    r"\b[\w-]+\.(md|py|sql|env|json)\b)"
)


def contains_private_detail(answer: str) -> bool:
    """Return True when an answer exposes implementation or security details."""
    return bool(_PRIVATE_DETAIL_RE.search(answer))


def ensure_in_domain(answer: str) -> str:
    """If the answer drifted off-topic, return the controlled refusal instead."""
    if looks_like_offtopic_drift(answer):
        logger.warning("Output validation: drift detected, returning refusal.")
        return OUT_OF_DOMAIN_REFUSAL
    answer = sanitize(answer)
    if contains_private_detail(answer):
        logger.warning("Output validation: private detail detected, returning refusal.")
        return SAFE_FALLBACK_PRIVATE
    return answer