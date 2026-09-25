"""Offline tests for the prompt builder."""

from ai.generation.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from ai.retrieval.models import RetrievalHit


def _hit():
    return RetrievalHit(
        chunk_id="x-1",
        document="business-rules.md",
        section="Donation state machine",
        text="Donations start as AVAILABLE.",
        score=0.92,
    )


def test_system_prompt_has_version_marker():
    assert PROMPT_VERSION  # non-empty


def test_user_prompt_contains_question_without_source_metadata():
    p = build_user_prompt("How do I request a pickup?", [_hit()])
    assert "How do I request a pickup?" in p
    assert "Donations start as AVAILABLE." in p
    assert "Relevant FoodShare information" in p
    assert "source:" not in p
    assert "business-rules.md" not in p
    assert "score:" not in p


def test_user_prompt_without_hits_omits_context_block():
    p = build_user_prompt("How do I sign up?", [])
    assert "Relevant FoodShare information" not in p
    assert "How do I sign up?" in p


def test_user_prompt_includes_recent_turns_when_provided():
    p = build_user_prompt(
        "And then?",
        [_hit()],
        recent_turns=[("user", "How does it start?"),
                      ("assistant", "Donations start as AVAILABLE.")],
    )
    assert "How does it start?" in p
    assert "Donations start as AVAILABLE." in p


def test_system_prompt_contains_app_overview_and_roles():
    assert "FoodShare In-App Assistant" in SYSTEM_PROMPT
    assert "RESTAURANTS / DONORS" in SYSTEM_PROMPT
    assert "CHARITIES / NGOS" in SYSTEM_PROMPT
    assert "ADMINS" in SYSTEM_PROMPT


def test_system_prompt_contains_lifecycle_and_food_safety():
    assert "ACCOUNT REGISTRATION & VERIFICATION FLOW" in SYSTEM_PROMPT
    assert "DONATION & PICKUP STATUS LIFECYCLE" in SYSTEM_PROMPT
    assert "BASIC FOOD SAFETY & PACKAGING RULES" in SYSTEM_PROMPT
    assert "FREQUENTLY ASKED IN-APP QUESTIONS" in SYSTEM_PROMPT
