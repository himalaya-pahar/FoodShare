"""Answer parsing + structural validation."""

from __future__ import annotations

from typing import Any

from ai.api.schemas import SourceItem
from ai.guardrails.output_validation import (
    ensure_in_domain,
    safe_fallback_no_evidence,
)
from ai.retrieval.models import RetrievalHit


def build_sources(hits: list[Any] | None = None) -> list[SourceItem]:
    """De-duplicate (document, section) pairs in the order they appear."""
    if not hits:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[SourceItem] = []
    for hit in hits:
        doc = getattr(hit, "document", "")
        sec = getattr(hit, "section", "")
        if not doc and not sec:
            continue
        key = (doc, sec)
        if key in seen:
            continue
        seen.add(key)
        out.append(SourceItem(document=doc, section=sec))
    return out


def validate_answer(
    raw_answer: str | None,
    hits: list[Any] | None = None,
) -> tuple[str, list[SourceItem]]:
    """Return (final_answer, sources).

    - If raw_answer is empty or None, return the safe-fallback.
    - Otherwise, run output-validation (drift check + secret redaction).
    - Retrieval metadata is intentionally not exposed to chat clients. The
      response keeps an empty sources field for backwards compatibility.
    """
    sources: list[SourceItem] = []

    if not raw_answer or not raw_answer.strip():
        return safe_fallback_no_evidence(), sources

    final = raw_answer.strip()
    final = ensure_in_domain(final)
    return final, sources