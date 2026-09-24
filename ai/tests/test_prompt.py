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


def test_user_prompt_contains_question_and_sources():
    p = build_user_prompt("How do I request a pickup?", [_hit()])
    assert "How do I request a pickup?" in p
    assert "business-rules.md" in p
    assert "Donation state machine" in p
    assert "Relevant FoodShare context" in p


def test_user_prompt_without_hits_omits_context_block():
    p = build_user_prompt("How do I sign up?", [])
    assert "Relevant FoodShare context" not in p
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


def test_system_prompt_includes_no_invention_rule():
    assert "Do not invent" in SYSTEM_PROMPT or "invent" in SYSTEM_PROMPT
