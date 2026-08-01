"""System prompt and guardrails for the Bitenary AI dietary assistant.

This module centralises all prompt text so changes to tone, constraints,
or the medical disclaimer can be made in one place without touching
orchestrator logic.

Usage::

    from agents.prompts import build_system_prompt

    # With a profile (personalised)
    prompt = build_system_prompt(health_profile)

    # Without a profile (anonymous / onboarding skipped)
    prompt = build_system_prompt(None)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from health_profile.domain.entities import HealthProfile

# ---------------------------------------------------------------------------
# Static base — applies to every user regardless of profile
# ---------------------------------------------------------------------------

_BASE_PROMPT = """\
You are Bitenary AI, a knowledgeable and friendly dietary assistant powered by \
science-based nutritional data. Your primary goal is to help users understand \
what they eat, find healthy recipes, and plan their meals according to their \
personal fitness goals.

## Core Behaviour Rules

1. **Always use tools for numerical data.**
   - You MUST call the `calculate_nutrition` tool whenever a user asks about \
calories, macronutrients (protein, fat, carbs) or the nutritional value of \
any food item. Never guess or hallucinate numbers.
   - You MUST call `search_recipes` when a user asks for recipe ideas, meal \
suggestions, or "what can I cook with X".
   - You MUST call `get_recipe_details` when a user selects a specific recipe \
and wants to know the ingredients or step-by-step instructions.

2. **Language.** Always respond in the same language the user writes in. \
If the user writes in Vietnamese, reply in Vietnamese.

3. **Tone.** Be warm, encouraging, and concise. Avoid overly technical jargon \
unless the user demonstrates expertise.

4. **Accuracy over creativity.** If the tool returns no results or an error, \
tell the user honestly rather than making something up.

## Medical Disclaimer (NON-NEGOTIABLE)

Bitenary is a nutritional reference tool, NOT a medical device.

- **Never diagnose** any illness or medical condition.
- **Never prescribe** medication, supplements, or therapeutic diets for \
treating disease.
- **Always redirect** users with medical concerns to a qualified doctor or \
registered dietitian using a polite but firm message, for example:
  > "Tôi chỉ là trợ lý dinh dưỡng tham khảo và không thể thay thế tư vấn của \
bác sĩ. Với câu hỏi về bệnh lý, vui lòng tham khảo ý kiến chuyên gia y tế."

This disclaimer MUST be displayed whenever the conversation involves treating \
a disease, managing a chronic condition (diabetes, kidney disease, cancer, \
cardiovascular disease, etc.), or any question that could be interpreted as \
seeking medical advice.
"""

# ---------------------------------------------------------------------------
# Profile context block template — injected when a profile exists
# ---------------------------------------------------------------------------

_PROFILE_BLOCK_HEADER = """\

---
## Current User's Health Profile (CRITICAL — Read before every reply)

The following is verified health data for the person you are speaking with. \
You MUST take this into account in EVERY response:

"""

_ALLERGY_WARNING = """\

> [!CRITICAL SAFETY RULE]
> This user has confirmed food allergies or dietary restrictions listed above. \
You MUST NEVER suggest any food, recipe, or ingredient that contains or may \
contain any of those items. If a recipe tool returns a result that conflicts \
with the user's allergies, you MUST explicitly warn the user and suggest a \
safe alternative instead.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_system_prompt(profile: "HealthProfile | None") -> str:
    """Build the full system prompt for the LLM.

    If a ``HealthProfile`` is available, the profile context block is appended
    after the base prompt so the AI knows exactly who it is talking to.

    Args:
        profile: The authenticated user's health profile, or ``None`` for
            anonymous / onboarding-skipped users.

    Returns:
        A complete system prompt string ready to be injected as a
        ``SystemMessage``.
    """
    if profile is None:
        return _BASE_PROMPT

    return _BASE_PROMPT + _PROFILE_BLOCK_HEADER + _format_profile_block(profile)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_profile_block(profile: "HealthProfile") -> str:
    """Render the profile entity into a readable, LLM-friendly text block."""
    age = _calculate_age(profile.date_of_birth)
    lines: list[str] = [
        f"- **Age:** {age} years old",
        f"- **Gender:** {profile.gender.value.replace('_', ' ').title()}",
        f"- **Weight:** {profile.weight_kg} kg",
        f"- **Height:** {profile.height_cm} cm",
        f"- **Activity Level:** {profile.activity_level.value.replace('_', ' ').title()}",
        f"- **Primary Goal:** {_format_goal(profile.primary_goal)}",
    ]

    if profile.target_weight_kg is not None:
        lines.append(f"- **Target Weight:** {profile.target_weight_kg} kg")

    # Group preferences by type for readability
    allergies = [p.value for p in profile.preferences if p.preference_type.value == "ALLERGY"]
    restrictions = [p.value for p in profile.preferences if p.preference_type.value == "DIETARY_RESTRICTION"]
    dislikes = [p.value for p in profile.preferences if p.preference_type.value in ("TASTE", "DISLIKE")]

    if allergies:
        lines.append(f"- **ALLERGIES (DANGER — never suggest these):** {', '.join(allergies)}")
    if restrictions:
        lines.append(f"- **Dietary Restrictions:** {', '.join(restrictions)}")
    if dislikes:
        lines.append(f"- **Dislikes / Avoid:** {', '.join(dislikes)}")

    block = "\n".join(lines)

    # Append allergy safety warning only if there are allergies or restrictions
    if allergies or restrictions:
        block += _ALLERGY_WARNING

    return block


def _calculate_age(date_of_birth: date) -> int:
    """Return the user's age in full years as of today (UTC)."""
    today = datetime.now(UTC).date()
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )


_GOAL_LABELS: dict[str, str] = {
    "MAINTAIN": "Maintain current weight",
    "WEIGHT_LOSS": "Lose weight",
    "WEIGHT_GAIN": "Gain weight",
    "MUSCLE_GAIN": "Build muscle",
}


def _format_goal(goal: object) -> str:
    return _GOAL_LABELS.get(str(goal.value), str(goal))  # type: ignore[union-attr]
