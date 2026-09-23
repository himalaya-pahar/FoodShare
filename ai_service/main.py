"""FastAPI entry point for the separately deployed AI service."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.api.routes import router as ai_router
from config import AI_CORS_ORIGINS


app = FastAPI(
    title="FoodShare AI Service",
    description="Read-only, knowledge-grounded FoodShare assistance.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=AI_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(ai_router)


@app.get("/health", tags=["Health"], include_in_schema=False)
def health() -> dict[str, str]:
    """Basic liveness check for the hosting platform."""
    return {"status": "ok"}
