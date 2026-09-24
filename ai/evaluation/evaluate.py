"""Tiny evaluator for the AI Assistant.

Measures:
    - retrieval_hit_rate:        fraction of in-domain questions whose top
                                retrieved chunk is from the expected document.
    - scope_refusal_accuracy:   fraction of out-of-domain questions that the
                                scope check classifies as out_of_domain.

Skips LLM cost entirely (does not call the LLM). Useful as a smoke test for
retrieval + scope after every reindex.

Usage:
    python -m ai.evaluation.evaluate

If `sentence-transformers` is not installed yet, the evaluator prints a clear
hint and exits non-zero rather than printing a stack trace. Install
dependencies first:
    pip install -r requirements.txt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ai.guardrails.scope_check import (
    ScopeDecision,
    classify_scope,
)


QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"


def load_questions() -> list[dict]:
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate() -> dict:
    questions = load_questions()
    if not questions:
        print("No questions to evaluate.")
        return {}

    try:
        from ai.retrieval.retriever import get_default_retriever
        retriever = get_default_retriever()
    except RuntimeError as exc:
        # Raised by LocalSentenceTransformerProvider._load when the
        # sentence-transformers package is missing.
        print(f"Evaluator aborted: {exc}", file=sys.stderr)
        print(
            "Run `pip install -r requirements.txt` and try again.",
            file=sys.stderr,
        )
        sys.exit(2)

    in_domain_hits = 0
    in_domain_total = 0
    out_of_domain_refusals = 0
    out_of_domain_total = 0

    # Detailed report (printed at the end).
    rows: list[dict] = []

    for q in questions:
        qtype = q.get("type")

        if qtype in ("in_domain", "in_domain_paraphrase"):
            in_domain_total += 1
            hits = retriever.retrieve(q["question"])
            top_doc = hits[0].document if hits else None
            ok = bool(hits) and (
                q.get("expected_doc") is None
                or top_doc == q["expected_doc"]
            )
            if ok:
                in_domain_hits += 1
            rows.append({
                "id": q["id"],
                "type": qtype,
                "expected": q.get("expected_doc"),
                "top_doc": top_doc,
                "ok": ok,
            })

        elif qtype == "out_of_domain":
            out_of_domain_total += 1
            scope = classify_scope(q["question"])
            ok = scope.decision == ScopeDecision.OUT_OF_DOMAIN
            if ok:
                out_of_domain_refusals += 1
            rows.append({
                "id": q["id"],
                "type": qtype,
                "scope": scope.decision.value,
                "ok": ok,
            })

        elif qtype in ("unsupported", "unsupported_in_v1"):
            # We measure these separately — the expected behavior is "no
            # strong hits" rather than refusal.
            hits = retriever.retrieve(q["question"])
            rows.append({
                "id": q["id"],
                "type": qtype,
                "hits": len(hits),
                "ok": True,  # informational; no expectation to fail
            })

    report = {
        "retrieval_hit_rate": (
            round(in_domain_hits / in_domain_total, 3)
            if in_domain_total else None
        ),
        "scope_refusal_accuracy": (
            round(out_of_domain_refusals / out_of_domain_total, 3)
            if out_of_domain_total else None
        ),
        "in_domain_total": in_domain_total,
        "in_domain_hits": in_domain_hits,
        "out_of_domain_total": out_of_domain_total,
        "out_of_domain_correct_refusals": out_of_domain_refusals,
        "details": rows,
    }
    return report


def _print(report: dict) -> None:
    print("\n=== FoodShare AI Evaluation ===")
    for k in (
        "retrieval_hit_rate",
        "scope_refusal_accuracy",
        "in_domain_total",
        "in_domain_hits",
        "out_of_domain_total",
        "out_of_domain_correct_refusals",
    ):
        print(f"  {k}: {report.get(k)}")
    print("  details:")
    for row in report.get("details", []):
        print(f"    - {row}")


def main() -> int:
    report = evaluate()
    if report:
        _print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())