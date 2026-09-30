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


# Words that strongly suggest a FoodShare question.
IN_DOMAIN_KEYWORDS: tuple[str, ...] = (
    # roles
    "restaurant", "ngo", "charity", "admin", "administrator", "account",
    # auth / lifecycle
    "signup", "sign up", "register", "login", "log in", "approve",
    "approval", "pending", "reject", "verification", "verify", "email",
    # donations
    "donation", "donate", "donating", "donated", "surplus", "leftover",
    "quantity", "pickup deadline", "deadline", "prepared",
    # status
    "available", "reserved", "collected", "completed", "cancelled", "expired",
    # pickup requests
    "pickup", "pick up", "pick-up", "request", "withdraw", "withdrawn",
    "accept", "accepted", "rejected",
    # app navigation
    "area", "address", "location", "filter",
    "image", "photo", "video", "media", "upload", "profile",
    # general app refs
    "foodshare", "the app", "the application", "the platform",
    "food share",
)


# Words that strongly suggest the question is off-topic OR is asking the
# assistant to DO or CREATE something it must not do.
OUT_OF_DOMAIN_KEYWORDS: tuple[str, ...] = (
    # clearly off-topic topics
    "weather", "forecast",
    "joke", "funny", "meme",
    "politician", "election", "vote",
    "quantum", "relativity", "physics",
    "investment", "stock", "crypto", "bitcoin",
    "how to cook", "cooking", "bake",
    "translate", "translation",
    "python", "javascript", "java", "rust", "coding", "programming",
    "homework", "essay", "thesis",
    "news", "sport", "game", "movie", "music",
    # action/content-generation requests the assistant must never do
    "write a description", "write description", "write me a description",
    "generate a description", "generate description",
    "write a title", "write me a title",
    "write a caption", "write caption",
    "write a post", "write post",
    "write a message", "write message",
    "draft a", "draft me",
    "create a description", "create description",
    "suggest a description", "suggest description",
    "make a description", "make description",
    "help me write", "help write",
    "write marketing", "marketing copy", "promotional",
    "recipe", "meal idea", "meal plan",
)


@dataclass(frozen=True)
class ScopeResult:
    decision: ScopeDecision
    matched_keyword: str | None = None


def classify_scope(message: str) -> ScopeResult:
    """Return the scope decision for a user message.

    Rules:
        - Any ACTION/CONTENT-GENERATION keyword -> out_of_domain (hard block).
        - Any IN_DOMAIN keyword -> in_domain (even if other keywords appear).
        - Any OUT_OF_DOMAIN keyword AND no IN_DOMAIN keyword -> out_of_domain.
        - Otherwise -> unsure (system prompt handles it).
    """
    text = message.lower()

    in_hit = next((kw for kw in IN_DOMAIN_KEYWORDS if kw in text), None)
    out_hit = next((kw for kw in OUT_OF_DOMAIN_KEYWORDS if kw in text), None)

    # Action/content-generation requests: block ALWAYS, even if foodshare is mentioned.
    _action_keywords = {kw for kw in OUT_OF_DOMAIN_KEYWORDS if any(
        verb in kw for verb in (
            "write", "generate", "draft", "create", "suggest", "make",
            "help me", "recipe", "marketing", "promotional",
        )
    )}
    action_hit = next((kw for kw in _action_keywords if kw in text), None)
    if action_hit:
        return ScopeResult(ScopeDecision.OUT_OF_DOMAIN, action_hit)

    if in_hit is not None:
        return ScopeResult(ScopeDecision.IN_DOMAIN, in_hit)

    if out_hit is not None:
        return ScopeResult(ScopeDecision.OUT_OF_DOMAIN, out_hit)

    return ScopeResult(ScopeDecision.UNSURE, None)


# Refusal messages — kept verbatim so tests can assert on them.
OUT_OF_DOMAIN_REFUSAL = (
    "I can only explain how to use FoodShare. "
    "How can I help you with the app?"
)

ACTION_REFUSAL = (
    "I can only explain how to use FoodShare. "
    "I cannot create content or perform actions."
)
