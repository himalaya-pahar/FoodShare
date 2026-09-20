"""HTTP routes for the AI Assistant.

Single endpoint:
    POST /ai/chat  — requires a logged-in user (CurrentUserDep).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ai.api.schemas import ChatRequest, ChatResponse
from ai.guardrails.input_validation import (
    InputValidationError,
    looks_like_injection,
    validate_message,
    validate_session_id,
)
from ai.repository.ai_service import handle_chat
from security.oauth2 import CurrentUserDep


logger = logging.getLogger("foodshare.ai.routes")

router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
)


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the FoodShare AI Assistant a question",
)
def chat(
    payload: ChatRequest,
    current_user: CurrentUserDep,
) -> ChatResponse:
    # 1. Validate input (separate from the pydantic schema so we can log + raise 422 explicitly).
    try:
        message = validate_message(payload.message)
        session_id = validate_session_id(payload.session_id)
    except InputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if looks_like_injection(message):
        # Don't refuse outright (the system prompt is the real defense).
        # Just log so we can see attempts in development.
        logger.warning(
            "ai.chat possible-injection user_id=%s",
            getattr(current_user, "id", None),
        )

    # 2. Hand off to the service layer.
    result = handle_chat(
        user_id=current_user.id,
        message=message,
        session_id=session_id,
    )

    return ChatResponse(
        session_id=result.session_id,
        answer=result.answer,
        sources=result.sources,
        scope_decision=result.scope_decision,
    )