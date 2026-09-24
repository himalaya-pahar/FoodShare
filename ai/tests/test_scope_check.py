"""Offline tests for the scope guardrail."""

from ai.guardrails.scope_check import (
    ScopeDecision,
    classify_scope,
)


def test_in_domain_when_keyword_matches():
    cases = [
        "How does an NGO request a pickup?",
        "What does Reserved mean?",
        "How do I sign up as a restaurant?",
        "Tell me about the donation workflow.",
        "What can an admin do?",
    ]
    for msg in cases:
        result = classify_scope(msg)
        assert result.decision == ScopeDecision.IN_DOMAIN, msg


def test_out_of_domain_when_only_offtopic_keyword_matches():
    cases = [
        "Tell me a joke.",
        "What is the weather today?",
        "How do I invest in crypto?",
        "Explain quantum physics.",
    ]
    for msg in cases:
        result = classify_scope(msg)
        assert result.decision == ScopeDecision.OUT_OF_DOMAIN, msg


def test_in_domain_beats_out_of_domain_on_overlap():
    # "investment" is out-of-domain but "restaurant" is in-domain → in_domain.
    msg = "Should my restaurant invest in better packaging?"
    result = classify_scope(msg)
    assert result.decision == ScopeDecision.IN_DOMAIN


def test_unsure_for_ambiguous_message():
    msg = "Hello there."
    result = classify_scope(msg)
    assert result.decision == ScopeDecision.UNSURE
