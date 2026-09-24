"""Scope guardrail.

Decides whether a user question is "about FoodShare" or off-topic. v1 uses a
simple, transparent keyword-based heuristic rather than an LLM call.

Three outcomes:
    - "in_domain"       -> proceed with RAG pipeline
    - "out_of_domain"   -> return the controlled refusal (do not call LLM)
    - "unsure"          -> default to in_domain so the RAG prompt's "I don't
                          know" instruction can take over. We do not want to
                          over-refuse legitimate questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScopeDecision(str, Enum):
    IN_DOMAIN = "in_domain"
    OUT_OF_DOMAIN = "out_of_domain"
    UNSURE = "unsure"


# Words that strongly suggest a FoodShare question. Sourced from the
# knowledge-base section titles + role/state names in the codebase.
IN_DOMAIN_KEYWORDS: tuple[str, ...] = (
    # roles
    "restaurant", "ngo", "admin", "administrator", "account",
    # auth / lifecycle
    "signup", "sign up", "register", "login", "log in", "approve",
    "approval", "pending", "reject", "reject", "pending approval",
    # donations
    "donation", "donate", "donating", "donated",
    "quantity", "pickup deadline", "deadline", "prepared",
    "food", "surplus", "leftover",
    # status
    "available", "reserved", "collected", "completed",
    "cancelled", "expired",
    # pickup requests
    "pickup", "pick up", "pick-up", "request", "withdraw",
    "withdrawn", "accept", "accepted", "reject", "rejected",
    # area / location
    "area", "address", "location",
    # media
    "image", "photo", "video", "media", "upload", "bucket", "supabase",
    "profile image", "profile picture",
    # general
    "foodshare", "the app", "the application", "the platform",
    "how do i", "how can i", "how to", "what happens", "why",
    "endpoint", "api", "route",
)


# Words that strongly suggest the question is off-topic.
OUT_OF_DOMAIN_KEYWORDS: tuple[str, ...] = (
    "weather", "temperature", "forecast",
    "joke", "funny", "meme",
    "politician", "election", "vote",
    "quantum", "relativity", "physics",
    "investment", "stock", "crypto", "bitcoin",
    "recipe", "cook", "ingredient", "how to cook",
    "translate", "translation",
    "python", "javascript", "java", "rust",
    "homework", "essay",
)


@dataclass(frozen=True)
class ScopeResult:
    decision: ScopeDecision
    matched_keyword: str | None = None


def classify_scope(message: str) -> ScopeResult:
    """Return the scope decision for a user message.

    Rules:
        - Any OUT_OF_DOMAIN keyword AND no IN_DOMAIN keyword -> out_of_domain.
        - Any IN_DOMAIN keyword -> in_domain (even if out_of_domain keywords also appear).
        - Otherwise -> unsure (default to in_domain downstream).

    The OR-with-in-domain precedence protects legitimate "how do I avoid
    investing in restaurants?" style questions from being misrefused.
    """
    text = message.lower()

    in_hit = next((kw for kw in IN_DOMAIN_KEYWORDS if kw in text), None)
    out_hit = next((kw for kw in OUT_OF_DOMAIN_KEYWORDS if kw in text), None)

    if in_hit is not None:
        return ScopeResult(ScopeDecision.IN_DOMAIN, in_hit)

    if out_hit is not None:
        return ScopeResult(ScopeDecision.OUT_OF_DOMAIN, out_hit)

    return ScopeResult(ScopeDecision.UNSURE, None)


# Controlled refusal text — kept verbatim and exportable so tests can assert.
OUT_OF_DOMAIN_REFUSAL = (
    "I can only answer questions about how to use the FoodShare application "
    "and its documented features."
)
