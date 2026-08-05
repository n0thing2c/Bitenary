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
    from virtual_fridge.domain.entities import FridgeItem

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
   - You MUST call `get_fridge_inventory` when the user asks what they have \
at home, wants recipe suggestions based on available ingredients, or wants to \
plan a meal using their existing food. Note: if expiring items are already \
listed below in the URGENT block, those represent only the soon-to-expire \
subset — call the tool to get the FULL fridge contents.
   - You MUST call `save_meal_plan` to persist a meal plan ONLY when the user \
explicitly confirms they want to save it (e.g. "save this", "lock it in", \
"looks good, save it"). Never save a plan the user has not approved. Present \
the full plan for review BEFORE saving.

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

# Expiring items block — injected dynamically only when items exist
_EXPIRING_BLOCK_HEADER = """
---
## ⚠️ URGENT: Ingredients Expiring Soon (Proactive Reminder)

The following items in the user's fridge are about to expire. You should:
- **Gently remind** the user at a natural point in the conversation \
(do NOT make it the first thing you say unless the user is already \
asking about food or cooking).
- **Proactively suggest** recipes that use these ingredients, especially \
if the user asks what to eat or cook.
- Do NOT suggest that the user throw away these items unless they are already \
expired. Always prefer recipes that use them first.

"""

_EXPIRING_BLOCK_FOOTER = """
> [!NOTE]
> This is only a summary of items expiring soon. If the user asks about their
> full fridge contents, call the `get_fridge_inventory` tool to get all items.
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


def build_system_prompt(
    profile: "HealthProfile | None",
    *,
    expiring_items: "tuple[FridgeItem, ...] | None" = None,
) -> str:
    """Build the full system prompt for the LLM.

    Combines the static base prompt with optional context blocks:
    - Health profile block (injected when ``profile`` is not ``None``)
    - Expiring fridge items block (injected when ``expiring_items`` is not
      empty, acting as a proactive reminder to the AI)

    Args:
        profile: The authenticated user's health profile, or ``None`` for
            anonymous / onboarding-skipped users.
        expiring_items: A tuple of fridge items that are expiring soon.
            Pass ``None`` or an empty tuple when there are no urgent items.

    Returns:
        A complete system prompt string ready to be injected as a
        ``SystemMessage``.
    """
    prompt = _BASE_PROMPT

    if profile is not None:
        prompt += _PROFILE_BLOCK_HEADER + _format_profile_block(profile)

    if expiring_items:
        prompt += _EXPIRING_BLOCK_HEADER + _format_expiring_block(expiring_items) + _EXPIRING_BLOCK_FOOTER

    return prompt


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


def _format_expiring_block(items: "tuple[FridgeItem, ...]") -> str:
    """Render expiring fridge items as a compact bullet list for the LLM.

    Each line follows the pattern:
        - {quantity} {unit} {name} [{food_state}] — expires {date} ({N} day(s) left)
    """
    from virtual_fridge.domain.entities import expiry_status_for

    today = datetime.now(UTC).date()
    lines: list[str] = []
    for item in items:
        status = expiry_status_for(item.expiry_date, today=today)
        days = (item.expiry_date - today).days
        state_str = f" [{item.food_state.value}]" if item.food_state else ""
        if days == 0:
            when = "expires TODAY"
        elif days < 0:
            when = f"EXPIRED {abs(days)} day(s) ago"
        else:
            when = f"expires in {days} day(s) ({item.expiry_date.isoformat()})"
        lines.append(
            f"- **{item.ingredient.name}**{state_str}: "
            f"{item.quantity} {item.unit} — {when} [Status: {status.value}]"
        )
    return "\n".join(lines) + "\n"
