"""Query rewrite: restate follow-up questions as standalone questions.

Two layers, cheap-first:
    1. Heuristic: concatenate recent user turns + current question. Free.
    2. LLM fallback: when the heuristic looks weak (very short current
       message, or no keyword overlap with prior turns), call the LLM to
       rewrite the question. One tiny call.

The orchestrator decides which layer ran (see ai.repository.ai_service).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ai.guardrails.scope_check import (
    IN_DOMAIN_KEYWORDS,
    ScopeDecision,
    classify_scope,
)


logger = logging.getLogger("foodshare.ai.query_rewrite")


@dataclass(frozen=True)
class RewriteResult:
    rewritten_question: str
    method: str            # "none" | "heuristic" | "llm"
    confidence: float      # 0..1


def heuristic_rewrite(
    current: str,
    recent_user_turns: list[str],
) -> RewriteResult:
    """Concatenate last 1-2 prior turns + current. Free, no LLM.

    Confidence is higher when:
        - the current message is short (it likely relies on prior context),
        - but it shares some vocabulary with prior turns (so the rewrite
          is likely to stay on-topic).
    """
    if not recent_user_turns:
        return RewriteResult(
            rewritten_question=current, method="none", confidence=1.0
        )

    prior_tail = recent_user_turns[-2:]
    prior_text = " ".join(prior_tail)
    combined = f"{prior_text} {current}".strip()

    cur_words = set(current.lower().split())
    prior_words = set(prior_text.lower().split())
    overlap = len(cur_words & prior_words) / max(1, len(cur_words))

    # Short current message → high prior influence.
    length_factor = 1.0 if len(current) < 30 else 0.5
    confidence = max(0.3, min(0.95, 0.4 + 0.4 * overlap + 0.2 * length_factor))

    return RewriteResult(
        rewritten_question=combined,
        method="heuristic",
        confidence=confidence,
    )


def llm_rewrite(
    current: str,
    recent_user_turns: list[str],
    llm_provider,
) -> RewriteResult:
    """Use the LLM to produce a single standalone question.

    Prompt is intentionally tiny — we only need the rewrite, not the answer.
    """
    history = "\n".join(f"User: {t}" for t in recent_user_turns[-4:])
    system = (
        "You rewrite a user's follow-up question into a single self-contained "
        "question that includes all needed context from the conversation so far. "
        "Do not answer the question. Output only the rewritten question, "
        "nothing else."
    )
    user = (
        f"Conversation so far:\n{history}\n\n"
        f"Latest question: {current}\n\n"
        "Rewritten standalone question:"
    )

    text = llm_provider.generate(system=system, user=user, max_tokens=200)
    rewritten = (text or "").strip().strip('"').strip()
    if not rewritten:
        rewritten = current

    return RewriteResult(
        rewritten_question=rewritten,
        method="llm",
        confidence=0.9,
    )


def should_use_llm_fallback(
    current: str,
    recent_user_turns: list[str],
    heuristic_result: RewriteResult,
) -> bool:
    """Decide whether to spend an LLM call on rewriting.

    Conservative: only escalate when heuristic confidence is low AND the
    message is clearly a follow-up (short, on-topic, prior turns exist).
    """
    if not recent_user_turns:
        return False
    if heuristic_result.confidence >= 0.7:
        return False
    if len(current) > 200:
        return False  # long messages already carry context
    scope = classify_scope(current)
    if scope.decision == ScopeDecision.OUT_OF_DOMAIN:
        return False  # rewriting off-topic is wasteful
    return True
