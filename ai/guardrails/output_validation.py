"""Output validation.

Wraps the LLM's raw text and ensures the user-facing answer is well-formed.
The bulk of structural validation lives in ai.generation.answer_parser;
this module is the *guardrail* layer that:

- replaces an invalid LLM response with a safe-fallback,
- redacts obvious secrets if any leaked (defense in depth — should never happen),
- ensures the answer does not look like out-of-domain drift.
"""

from __future__ import annotations

import logging
import re

from ai.guardrails.scope_check import (
    OUT_OF_DOMAIN_REFUSAL,
    OUT_OF_DOMAIN_KEYWORDS,
)


logger = logging.getLogger("foodshare.ai.guardrails.output")


SAFE_FALLBACK_NO_EVIDENCE = (
    "I could not find enough information about that in the FoodShare "
    "knowledge base."
)
SAFE_FALLBACK_TEMPORARY = (
    "The FoodShare assistant is temporarily unavailable. Please try again later."
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


def ensure_in_domain(answer: str) -> str:
    """If the answer drifted off-topic, return the controlled refusal instead."""
    if looks_like_offtopic_drift(answer):
        logger.warning("Output validation: drift detected, returning refusal.")
        return OUT_OF_DOMAIN_REFUSAL
    return sanitize(answer)