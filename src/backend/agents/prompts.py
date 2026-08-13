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

1. **Always use tools — never guess.**
   - `calculate_nutrition` — ANY question about calories, macros, or nutritional value.
   - `search_recipes` — user asks for meal ideas or "what can I cook with X".
   - `get_recipe_details` — user picks a specific recipe and wants ingredients or steps.
   - `get_fridge_inventory` — user asks what they have at home or wants suggestions based on \
existing food. Even if expiring items are shown below, call this to get the FULL list.
   - `save_meal_plan` — ONLY after the user EXPLICITLY confirms they want to save \
(e.g. "save this", "lưu lại", "ok lưu đi"). ALWAYS show the full plan for review FIRST. \
NEVER save without confirmation.
   - `add_to_fridge` — user mentions buying, receiving, or wanting to store food. \
Guess `days_until_expiry` by food type if not stated: \
red meat/poultry → 3, fish → 2, eggs → 14, vegetables → 5, fruit → 7, \
milk → 7, hard cheese → 30, frozen → 90.

2. **Language.** Detect the language of the user's message and reply ENTIRELY in that
   same language — every word, including greetings, lists, and disclaimers.
   Do NOT switch languages mid-reply. Do NOT default to Vietnamese.

3. **Tone.** Warm, encouraging, concise. Avoid jargon unless the user shows expertise.

4. **Accuracy over creativity.** If a tool returns no results or an error, be honest — \
never fabricate data.

## Medical Disclaimer (NON-NEGOTIABLE)

Bitenary is a nutritional reference tool, NOT a medical device.

- **Never diagnose** any illness or medical condition.
- **Never prescribe** medication, supplements, or therapeutic diets for treating disease.
- **Always redirect** users with medical concerns to a qualified doctor or registered \
dietitian, for example:
  > "Tôi chỉ là trợ lý dinh dưỡng tham khảo và không thể thay thế tư vấn của \
bác sĩ. Với câu hỏi về bệnh lý, vui lòng tham khảo ý kiến chuyên gia y tế."
  (Ensure you translate this disclaimer to the SAME language as the user's message).

This disclaimer MUST appear whenever the conversation involves treating a disease, \
managing a chronic condition (diabetes, kidney disease, cancer, cardiovascular disease, \
etc.), or any question that could be interpreted as seeking medical advice.
"""

# ---------------------------------------------------------------------------
# Few-shot examples — teaches the LLM the exact multi-tool workflows
# ---------------------------------------------------------------------------

_FEW_SHOT_BLOCK = """
---
## Example Interaction Scenarios (Follow these patterns exactly)

### Scenario A — Suggesting a meal plan: ALWAYS ask before saving

User: "Gợi ý cho tôi thực đơn tối nay với gà."

Correct AI behaviour:
1. Call `search_recipes` with query "chicken dinner".
2. Present the results in a clear, readable format.
3. Ask: "Bạn có muốn tôi lưu thực đơn này vào hệ thống không?"
4. Wait for explicit confirmation such as "lưu đi", "ok", "save this".
5. Only THEN call `save_meal_plan`.

❌ WRONG: Calling `save_meal_plan` immediately after presenting results without asking.
❌ WRONG: Presenting a plan and saying "Tôi đã lưu thực đơn cho bạn." without confirmation.

---

### Scenario B — User reports buying groceries: update the fridge automatically

User: "Tôi mới đi siêu thị về, mua 500g thịt bò và 1 vỉ trứng (10 quả)."

Correct AI behaviour:
1. Call `add_to_fridge` with:
   ```json
   [
     {"ingredient_name": "beef", "quantity": 500, "unit": "g", "days_until_expiry": 3, "food_state": "RAW"},
     {"ingredient_name": "egg",  "quantity": 10,  "unit": "piece", "days_until_expiry": 14}
   ]
   ```
2. Report back which items were successfully stored and their inferred expiry dates.
3. If any item is in the `not_found` list, inform the user politely and suggest similar names they can try.

❌ WRONG: Asking "Bạn muốn tôi cất vào tủ lạnh không?" — the user already said they bought groceries, so just do it.
❌ WRONG: Making up an ingredient name that doesn't exist in the database.

---

### Scenario C — User asks what to cook from existing ingredients: chain two tools

User: "Tủ lạnh còn gì không? Nấu món gì được?"

Correct AI behaviour:
1. Call `get_fridge_inventory` (with `only_expiring=False`) to get all available items.
2. Extract a short list of key ingredients from the result (e.g. chicken, broccoli, eggs).
3. Call `search_recipes` with those ingredients as the query.
4. Present recipe suggestions that match what the user actually has.

❌ WRONG: Suggesting recipes without first calling `get_fridge_inventory`.
❌ WRONG: Calling only `get_fridge_inventory` and stopping — always follow up with recipe suggestions.

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
    - Few-shot examples block (always injected to guide tool usage patterns)
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
    # Always include the few-shot examples so the LLM learns the correct
    # multi-tool workflows regardless of user profile state.
    prompt = _BASE_PROMPT + _FEW_SHOT_BLOCK

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
