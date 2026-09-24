"""Prompt template for the FoodShare AI Assistant.

Single source of truth for the system + context + user template. Kept as a
plain string so it is easy to inspect and so test code can pin to a known
value.
"""

from __future__ import annotations

from ai.retrieval.models import RetrievalHit


PROMPT_VERSION = "v2"


SYSTEM_PROMPT = """You are the FoodShare AI Assistant.

Your job is to help users understand how to use the FoodShare application.

Rules:
1. Use ONLY the supplied FoodShare context to answer. Do not invent features,
   rules, workflows, or policies.
2. If the supplied context does not contain enough information to answer the
   question, say exactly: "I could not find enough information about that in
   the FoodShare knowledge base."
3. Do not answer questions unrelated to FoodShare. If asked, respond with:
   "I can only answer questions about how to use the FoodShare application
   and its documented features."
4. Answer naturally and fluidly as a helpful human assistant. Do NOT mention
    documents, sources, citations, context, retrieval, or the knowledge base.
    Present the relevant facts directly and never add a "Sources" section.
5. Do not perform any action. You cannot create donations, request pickups,
   approve accounts, or change statuses. Just explain.
6. Be concise. Prefer short paragraphs and bullet points.
"""


def build_user_prompt(
    question: str,
    hits: list[RetrievalHit],
    recent_turns: list[tuple[str, str]] | None = None,
) -> str:
    """Build the user-side prompt: context block + question (+ optional turns).

    recent_turns is a list of (role, content) where role is "user" or "assistant".
    """
    parts: list[str] = []

    if recent_turns:
        parts.append("Conversation so far:")
        for role, content in recent_turns[-4:]:
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {content}")
        parts.append("")

    if hits:
        parts.append("Relevant FoodShare information:")
        for i, hit in enumerate(hits, start=1):
            parts.append(f"Information {i}:\n{hit.text}")
        parts.append("")

    parts.append(f"User question: {question}")
    parts.append("")
    parts.append(
        "Answer using only the information above. Be concise and answer directly; "
        "do not mention where the information came from."
    )

    return "\n".join(parts)


def render_prompt(
    question: str,
    hits: list[RetrievalHit],
    recent_turns: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) — ready for the LLMProvider."""
    return SYSTEM_PROMPT, build_user_prompt(
        question=question,
        hits=hits,
        recent_turns=recent_turns,
    )