"""AI orchestrator: scope → rewrite → retrieve → build context → LLM → validate.

The single function `handle_chat()` is what the FastAPI route calls. It owns
all the failure-mode logic so the route stays thin.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from ai.api.schemas import SourceItem
from ai.generation.answer_parser import validate_answer
from ai.generation.llm import LLMProvider, get_provider
from ai.generation.prompt import render_prompt
from ai.guardrails.output_validation import (
    safe_fallback_no_evidence,
    safe_fallback_temporary,
)
from ai.guardrails.scope_check import (
    OUT_OF_DOMAIN_REFUSAL,
    ScopeDecision,
    classify_scope,
)
from ai.repository.sessions import Session, SessionStore, get_store
from ai.retrieval.query_rewrite import (
    RewriteResult,
    heuristic_rewrite,
    llm_rewrite,
    should_use_llm_fallback,
)
from ai.retrieval.retriever import Retriever, get_default_retriever


logger = logging.getLogger("foodshare.ai.service")


@dataclass
class ChatResult:
    session_id: str
    answer: str
    sources: list[SourceItem] = field(default_factory=list)
    scope_decision: str = "in_domain"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    latency_ms: int = 0
    retrieval_count: int = 0
    rewrite_method: str = "none"
    model: str = ""


def handle_chat(
    *,
    user_id: int,
    message: str,
    session_id: Optional[str],
    store: SessionStore | None = None,
    retriever: Retriever | None = None,
    llm: LLMProvider | None = None,
) -> ChatResult:
    """End-to-end chat handler.

    Errors are caught and translated into a controlled user-facing answer.
    Stack traces are never returned to the user.
    """
    started = time.perf_counter()
    request_id = str(uuid.uuid4())
    store = store or get_store()
    session = store.get_or_create(user_id, session_id)

    log_extra = {
        "request_id": request_id,
        "user_id": user_id,
    }

    try:
        retriever = retriever or get_default_retriever()
        llm = llm or get_provider()
    except Exception as exc:
        logger.error("AI service initialization failed: %s", exc)
        answer = safe_fallback_temporary()
        return _finalize(
            session=session,
            answer=answer,
            sources=[],
            scope_decision="no_evidence",
            request_id=request_id,
            started=started,
            retrieval_count=0,
            rewrite_method="none",
            model="(error)",
        )

    # 2. Scope check.
    scope = classify_scope(message)
    log_extra["scope"] = scope.decision.value

    if scope.decision == ScopeDecision.OUT_OF_DOMAIN:
        answer = OUT_OF_DOMAIN_REFUSAL
        store.append_turn(session, "user", message)
        store.append_turn(session, "assistant", answer)
        logger.info("chat.out_of_domain %s", log_extra)
        return _finalize(
            session=session,
            answer=answer,
            sources=[],
            scope_decision=scope.decision.value,
            request_id=request_id,
            started=started,
            retrieval_count=0,
            rewrite_method="none",
            model="(no-llm)",
        )

    # 3. Query rewrite for follow-ups (heuristic first; LLM fallback if needed).
    recent_user_turns = [
        t.content for t in session.turns if t.role == "user"
    ]
    rewrite = heuristic_rewrite(message, recent_user_turns)
    if should_use_llm_fallback(message, recent_user_turns, rewrite):
        try:
            rewrite = llm_rewrite(message, recent_user_turns, llm)
        except Exception:  # noqa: BLE001
            logger.warning("LLM rewrite failed; using heuristic.", exc_info=True)
            rewrite = RewriteResult(
                rewritten_question=rewrite.rewritten_question,
                method="heuristic",
                confidence=rewrite.confidence,
            )
    log_extra["rewrite"] = rewrite.method

    # 4. Retrieve relevant chunks.
    try:
        hits = retriever.retrieve(rewrite.rewritten_question)
    except Exception as exc:
        logger.warning("retrieval failure: %s %s", exc, log_extra)
        answer = safe_fallback_temporary()
        store.append_turn(session, "user", message)
        store.append_turn(session, "assistant", answer)
        return _finalize(
            session=session,
            answer=answer,
            sources=[],
            scope_decision="no_evidence",
            request_id=request_id,
            started=started,
            retrieval_count=0,
            rewrite_method=rewrite.method,
            model=llm.name,
        )

    log_extra["hits"] = len(hits)

    if not hits:
        answer = safe_fallback_no_evidence()
        store.append_turn(session, "user", message)
        store.append_turn(session, "assistant", answer)
        logger.info("chat.no_evidence %s", log_extra)
        return _finalize(
            session=session,
            answer=answer,
            sources=[],
            scope_decision="no_evidence",
            request_id=request_id,
            started=started,
            retrieval_count=0,
            rewrite_method=rewrite.method,
            model=llm.name,
        )

    # 5. Build prompt + call LLM.
    recent_for_prompt = [
        (t.role, t.content) for t in session.turns[-6:]
    ]
    system, user_prompt = render_prompt(
        question=message,  # show the original question to the LLM
        hits=hits,
        recent_turns=recent_for_prompt,
    )

    try:
        raw = llm.generate(
            system=system,
            user=user_prompt,
            max_tokens=500,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM failure: %s %s", exc, log_extra)
        answer = safe_fallback_temporary()
        store.append_turn(session, "user", message)
        store.append_turn(session, "assistant", answer)
        return _finalize(
            session=session,
            answer=answer,
            sources=[],
            scope_decision="in_domain",
            request_id=request_id,
            started=started,
            retrieval_count=len(hits),
            rewrite_method=rewrite.method,
            model=llm.name,
        )

    answer, sources = validate_answer(raw, hits)

    # 6. Persist this turn in the session.
    store.append_turn(session, "user", message)
    store.append_turn(session, "assistant", answer)

    logger.info(
        "chat.ok hits=%d rewrite=%s %s",
        len(hits),
        rewrite.method,
        log_extra,
    )
    return _finalize(
        session=session,
        answer=answer,
        sources=sources,
        scope_decision="in_domain",
        request_id=request_id,
        started=started,
        retrieval_count=len(hits),
        rewrite_method=rewrite.method,
        model=llm.name,
    )


def _finalize(
    *,
    session: Session,
    answer: str,
    sources: list[SourceItem],
    scope_decision: str,
    request_id: str,
    started: float,
    retrieval_count: int,
    rewrite_method: str,
    model: str,
) -> ChatResult:
    latency_ms = int((time.perf_counter() - started) * 1000)
    return ChatResult(
        session_id=session.id,
        answer=answer,
        sources=sources,
        scope_decision=scope_decision,
        request_id=request_id,
        latency_ms=latency_ms,
        retrieval_count=retrieval_count,
        rewrite_method=rewrite_method,
        model=model,
    )