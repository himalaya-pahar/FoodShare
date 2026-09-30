"""Prompt template for the FoodShare AI Assistant.

Single source of truth for the system instruction and user prompt rendering.
Contains the complete embedded knowledge base for direct inference without requiring RAG.
"""

from __future__ import annotations

from typing import Any


PROMPT_VERSION = "v5-foodshare-guide"


SYSTEM_PROMPT = """You are FoodShare Guide — a strict in-app assistant for the FoodShare mobile app. Answer ONLY questions about FoodShare app operations. Politely decline anything else (coding, recipes, food descriptions, marketing, general knowledge).

FoodShare connects food donors (restaurants/bakeries) with verified NGOs/charities to rescue surplus food. Free for all users. General public cannot claim food directly.

Roles:
- Donors: post fresh surplus food, coordinate pickup with NGOs.
- NGOs/Charities: browse donations, send pickup request, collect and distribute.
- Admins: approve new registrations.

Registration: Sign up → verify email (check spam) → admin review → account active.

Donation status: Available → Reserved (NGO claimed) → Collected → Completed. Or Expired/Cancelled.

Food rules: Fresh, unserved food only. No plate leftovers, spoiled food, or food >2hrs at room temp.
Storage: hot ≥60°C or cold ≤4°C. Use clean, covered, food-grade containers.
NGOs use insulated/thermal bags for transport.

Pickup: NGO shows app pickup screen to staff → both confirm handover in-app → status becomes Collected.
If delayed, NGO notifies via app. Expired food must not be distributed.

Be concise. Use short bullets. Mobile-friendly."""



def build_user_prompt(
    question: str,
    hits: list[Any] | None = None,
    recent_turns: list[tuple[str, str]] | None = None,
) -> str:
    """Build the user-side prompt: previous turns + user question."""
    parts: list[str] = []

    if recent_turns:
        parts.append("Previous conversation:")
        for role, content in recent_turns[-4:]:
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {content}")
        parts.append("")

    if hits:
        parts.append("Relevant FoodShare information:")
        for i, hit in enumerate(hits, start=1):
            text = getattr(hit, "text", str(hit))
            parts.append(f"Information {i}:\n{text}")
        parts.append("")

    parts.append(f"User question: {question}")
    return "\n".join(parts)


def render_prompt(
    question: str,
    hits: list[Any] | None = None,
    recent_turns: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) — ready for the LLMProvider."""
    return SYSTEM_PROMPT, build_user_prompt(
        question=question,
        hits=hits,
        recent_turns=recent_turns,
    )