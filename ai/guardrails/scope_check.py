"""Scope guardrail.

Decides whether a user question is "about FoodShare" or off-topic before
hitting the LLM. Saves tokens and enforces hard limits.

Three outcomes:
    - "in_domain"       -> proceed with LLM
    - "out_of_domain"   -> return controlled refusal, do NOT call LLM
    - "unsure"          -> default to in_domain so the system prompt handles it
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScopeDecision(str, Enum):
    IN_DOMAIN = "in_domain"
    OUT_OF_DOMAIN = "out_of_domain"
    UNSURE = "unsure"


# Words that indicate a FoodShare related question.
IN_DOMAIN_KEYWORDS: tuple[str, ...] = (
    # roles
    "restaurant", "ngo", "charity", "admin", "administrator", "account",
    # auth / lifecycle
    "signup", "sign up", "register", "login", "log in", "approve",
    "approval", "pending", "reject", "verification", "verify", "email",
    "password", "forgot password", "reset password",
    # donations
    "donation", "donate", "donating", "donated", "surplus", "leftover",
    "quantity", "pickup deadline", "deadline", "prepared", "food",
    "meal", "expiry", "expire", "allergens", "storage",
    # status
    "available", "reserved", "collected", "completed", "cancelled", "expired",
    # pickup requests
    "pickup", "pick up", "pick-up", "request", "withdraw", "withdrawn",
    "accept", "accepted", "rejected", "handoff", "handover", "collect",
    # app navigation & features
    "area", "address", "location", "filter",
    "image", "photo", "video", "media", "upload", "profile",
    "description", "post", "listing",
    # general app refs
    "foodshare", "the app", "the application", "the platform", "food share",
    "how to use", "how does", "help",
)


# Strictly off-topic topics that have zero connection to FoodShare.
OUT_OF_DOMAIN_KEYWORDS: tuple[str, ...] = (
    "weather", "forecast",
    "joke", "funny meme",
    "politician", "presidential election", "who to vote for",
    "quantum physics", "relativity theory", "explain quantum",
    "crypto", "cryptocurrency", "bitcoin", "ethereum", "stock trading", "forex",
    "python programming", "write java code", "debug this code",
    "homework essay", "write my essay", "write a poem", "write a story",
    "nba score", "football match", "cricket score", "movie review",
)

TECHNICAL_KEYWORDS: tuple[str, ...] = (
    "source code", "api endpoint", "rest api", "database schema",
    "sql query", "database table", "table schema",
    "server architecture", "fastapi backend", "backend api",
)


@dataclass(frozen=True)
class ScopeResult:
    decision: ScopeDecision
    matched_keyword: str | None = None


def classify_scope(message: str) -> ScopeResult:
    """Return the scope decision for a user message.

    Rules:
        - Technical probe keywords -> out_of_domain (hard block).
        - Any IN_DOMAIN keyword -> in_domain (even if other keywords appear).
        - Any OUT_OF_DOMAIN keyword AND no IN_DOMAIN keyword -> out_of_domain.
        - Otherwise -> unsure (LLM handles it contextually).
    """
    text = message.lower()

    # Technical / backend probes: block immediately
    tech_hit = next((kw for kw in TECHNICAL_KEYWORDS if kw in text), None)
    if tech_hit:
        return ScopeResult(ScopeDecision.OUT_OF_DOMAIN, tech_hit)

    in_hit = next((kw for kw in IN_DOMAIN_KEYWORDS if kw in text), None)
    out_hit = next((kw for kw in OUT_OF_DOMAIN_KEYWORDS if kw in text), None)

    if in_hit is not None:
        return ScopeResult(ScopeDecision.IN_DOMAIN, in_hit)

    if out_hit is not None:
        return ScopeResult(ScopeDecision.OUT_OF_DOMAIN, out_hit)

    return ScopeResult(ScopeDecision.UNSURE, None)


# Refusal messages — direct, straightforward, relevant.
OUT_OF_DOMAIN_REFUSAL = (
    "I can only help with questions about using the FoodShare app."
)

ACTION_REFUSAL = (
    "I cannot write descriptions or perform actions in the app."
)

TECHNICAL_REFUSAL = (
    "I can only help with how to use the FoodShare app."
)
