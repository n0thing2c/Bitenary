"""MCP tool: get_fridge_inventory

Exposes the authenticated user's Virtual Fridge contents to AI agents
through the Bitenary MCP server. Follows the same factory + auditor pattern
used by ``tools/nutrition.py`` and ``tools/recipe.py``.

Security model
--------------
The tool always scopes its query to ``current_principal().user_id``, which is
resolved from the verified Bearer token present on every MCP request. This
means an external agent (e.g. Claude Desktop) can *only* read the fridge of
the person who issued the token — it is impossible to accidentally leak data
across user boundaries.

Session management
------------------
A fresh ``AsyncSession`` is opened and closed for every tool invocation via
the ``session_factory`` context manager. This is consistent with how
``MCPInvocationAuditor`` manages its own sessions.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from bitenary_mcp.service.auditing import MCPInvocationAuditor
from bitenary_mcp.tools.status import current_principal
from virtual_fridge.domain.entities import (
    ExpiryStatus,
    FridgeItem,
    expiry_status_for,
)
from virtual_fridge.infrastructure.sqlalchemy_fridge import SqlAlchemyFridgeItemRepository
from virtual_fridge.service.fridge import VirtualFridgeService


TOOL_NAME = "get_fridge_inventory"

# Safety cap: never return more than this many items to keep the context lean.
_MAX_ITEMS = 50


def _item_to_dict(item: FridgeItem, *, today: date) -> dict:
    """Serialise a FridgeItem into a compact JSON-friendly dict for the LLM."""
    status = expiry_status_for(item.expiry_date, today=today)
    return {
        "name": item.ingredient.name,
        "variant": item.ingredient.variant,
        "category": item.ingredient.category,
        "quantity": float(item.quantity),
        "unit": item.unit,
        "food_state": item.food_state.value if item.food_state else None,
        "expiry_date": item.expiry_date.isoformat(),
        "expiry_status": status.value,
        "days_until_expiry": (item.expiry_date - today).days,
    }


def build_fridge_inventory_tool(
    auditor: MCPInvocationAuditor,
    session_factory: Any,
    warning_days: int = 3,
) -> Callable[[bool], Awaitable[dict]]:
    """Return a ready-to-register ``get_fridge_inventory`` MCP tool function.

    Args:
        auditor: Shared invocation auditor that logs every tool call to the DB.
        session_factory: Async SQLAlchemy session factory (``AsyncSessionLocal``).
            A fresh session is opened per tool invocation to avoid session
            contamination across concurrent requests.
        warning_days: Number of days used to define the EXPIRING_SOON window.
            Should come from ``settings.fridge_expiry_warning_days``.

    Returns:
        An async callable suitable for ``mcp_server.add_tool(...)``.
    """

    @asynccontextmanager
    async def _session_scope() -> AsyncGenerator[VirtualFridgeService, None]:
        """Open a per-invocation DB session and yield a VirtualFridgeService."""
        async with session_factory() as session:
            repo = SqlAlchemyFridgeItemRepository(session)
            yield VirtualFridgeService(repo, warning_days=warning_days)

    async def get_fridge_inventory(only_expiring: bool = False) -> dict:
        """List the food items currently stored in the user's virtual fridge.

        Retrieves all non-expired ingredients (or only soon-to-expire ones)
        from the authenticated user's Virtual Fridge. Use this tool whenever
        the user asks about what they have at home, wants recipe suggestions
        based on available ingredients, or wants to plan a meal using existing
        food.

        Args:
            only_expiring: When ``True``, returns only items whose expiry status
                is ``EXPIRING_TODAY`` or ``EXPIRING_SOON``. Use this when you
                only need to highlight urgent items, for example when the user
                asks "what should I use before it goes bad?". When ``False``
                (the default), returns all available non-expired items.

        Returns:
            A JSON-serialisable dict with the structure::

                {
                    "total": 5,
                    "only_expiring": false,
                    "items": [
                        {
                            "name": "Chicken Breast",
                            "variant": "Chicken Breast, Raw",
                            "category": "Poultry",
                            "quantity": 500.0,
                            "unit": "g",
                            "food_state": "RAW",
                            "expiry_date": "2026-08-06",
                            "expiry_status": "EXPIRING_SOON",
                            "days_until_expiry": 1
                        },
                        ...
                    ]
                }

        Note:
            Results are capped at 50 items to keep the context window lean.
            Items are ordered by expiry date ascending (most urgent first).
        """
        principal = current_principal()
        today = date.today()

        async def fridge_operation() -> dict:
            async with _session_scope() as fridge_service:
                all_items = await fridge_service.get_available_ingredients(
                    user_id=principal.user_id,
                    today=today,
                )

            if only_expiring:
                urgent_statuses = {
                    ExpiryStatus.EXPIRING_SOON,
                    ExpiryStatus.EXPIRING_TODAY,
                }
                items: tuple[FridgeItem, ...] = tuple(
                    item
                    for item in all_items
                    if expiry_status_for(item.expiry_date, today=today) in urgent_statuses
                )
            else:
                items = all_items

            # Cap to avoid context overflow
            items = items[:_MAX_ITEMS]

            return {
                "total": len(items),
                "only_expiring": only_expiring,
                "items": [_item_to_dict(item, today=today) for item in items],
            }

        return await auditor.invoke(
            principal=principal,
            tool_name=TOOL_NAME,
            operation=fridge_operation,
        )

    get_fridge_inventory.__name__ = TOOL_NAME
    return get_fridge_inventory


# ---------------------------------------------------------------------------
# Tool: add_to_fridge
# ---------------------------------------------------------------------------

ADD_TOOL_NAME = "add_to_fridge"

# Maximum items accepted in one call — prevents oversized payloads.
_MAX_ADD_ITEMS = 20


def build_add_to_fridge_tool(
    auditor: MCPInvocationAuditor,
    session_factory: Any,
    warning_days: int = 3,
) -> Callable[..., Awaitable[dict]]:
    """Return a ready-to-register ``add_to_fridge`` MCP tool function.

    Args:
        auditor: Shared invocation auditor for audit logging.
        session_factory: Async SQLAlchemy session factory.
        warning_days: Forwarded to ``VirtualFridgeService`` for expiry logic.

    Returns:
        An async callable suitable for ``mcp_server.add_tool(...)``.
    """
    from decimal import Decimal

    from ingredients.infrastructure.sqlalchemy_ingredients import SqlAlchemyIngredientRepository
    from virtual_fridge.domain.entities import FoodState

    @asynccontextmanager
    async def _session_scope() -> AsyncGenerator[tuple[VirtualFridgeService, Any], None]:
        """Open a per-invocation DB session and yield both services."""
        async with session_factory() as session:
            fridge_repo = SqlAlchemyFridgeItemRepository(session)
            ingredient_repo = SqlAlchemyIngredientRepository(session)
            yield VirtualFridgeService(fridge_repo, warning_days=warning_days), ingredient_repo

    async def add_to_fridge(items: str) -> dict:
        """Add one or more food items to the authenticated user's virtual fridge.

        Call this tool whenever the user mentions they bought new groceries,
        received food, or explicitly wants to add items to their fridge.

        Args:
            items: A JSON string (list of objects). Each object must have:

                - ``ingredient_name`` (str): The name of the food item in plain
                  language (e.g. ``"chicken breast"``, ``"cà chua"``).
                - ``quantity`` (float): Amount to store (must be > 0).
                - ``unit`` (str): Unit of measurement (e.g. ``"g"``, ``"kg"``,
                  ``"piece"``, ``"bottle"``).
                - ``days_until_expiry`` (int): How many days until the item
                  expires. Make a sensible guess based on food type if the user
                  does not specify:
                  fresh red meat / poultry → 3,
                  fish / seafood → 2,
                  eggs → 14,
                  fresh vegetables → 5,
                  fresh fruit → 7,
                  dairy milk → 7,
                  hard cheese → 30,
                  frozen items → 90.
                - ``food_state`` (str, optional): One of ``"RAW"``, ``"COOKED"``,
                  ``"FROZEN"``, ``"PREPPED"``. Defaults to ``"RAW"``.

                Example::

                    [
                        {"ingredient_name": "chicken breast", "quantity": 500,
                         "unit": "g", "days_until_expiry": 3, "food_state": "RAW"},
                        {"ingredient_name": "milk", "quantity": 1,
                         "unit": "litre", "days_until_expiry": 7}
                    ]

        Returns:
            A dict summarising the operation::

                {
                    "added": [
                        {"ingredient_name": "chicken breast", "matched_as": "Chicken Breast",
                         "quantity": 500.0, "unit": "g", "expiry_date": "2026-08-10"}
                    ],
                    "not_found": ["foobar ingredient"],
                    "total_added": 1,
                    "total_not_found": 1
                }
        """
        import json
        from datetime import timedelta

        principal = current_principal()
        today = date.today()

        async def add_operation() -> dict:
            # ----------------------------------------------------------------
            # 1. Parse and validate the items JSON string from the LLM
            # ----------------------------------------------------------------
            try:
                raw_items: list[dict] = json.loads(items)
            except json.JSONDecodeError as exc:
                raise ValueError(f"items must be a valid JSON string: {exc}") from exc

            if not isinstance(raw_items, list) or not raw_items:
                raise ValueError("items must be a non-empty JSON array")

            if len(raw_items) > _MAX_ADD_ITEMS:
                raise ValueError(
                    f"Too many items in one call (max {_MAX_ADD_ITEMS}). Split into batches."
                )

            added: list[dict] = []
            not_found: list[str] = []

            async with _session_scope() as (fridge_service, ingredient_repo):
                for raw in raw_items:
                    name: str = str(raw.get("ingredient_name", "")).strip()
                    if not name:
                        not_found.append("<empty name>")
                        continue

                    # ------------------------------------------------------------
                    # 2. Auto-resolve ingredient name → ingredient_id via ILIKE
                    # ------------------------------------------------------------
                    matches = await ingredient_repo.search(
                        q=name,
                        only_default=False,
                        size=1,
                    )
                    if not matches:
                        not_found.append(name)
                        continue

                    ingredient = matches[0]

                    # ------------------------------------------------------------
                    # 3. Validate quantity / unit / food_state / days
                    # ------------------------------------------------------------
                    try:
                        quantity = Decimal(str(raw.get("quantity", 0)))
                    except Exception:
                        not_found.append(name)
                        continue

                    unit: str = str(raw.get("unit", "piece")).strip() or "piece"

                    days_raw = raw.get("days_until_expiry", 3)
                    try:
                        days = max(1, int(days_raw))
                    except (TypeError, ValueError):
                        days = 3
                    expiry_date = today + timedelta(days=days)

                    food_state_raw: str | None = raw.get("food_state")
                    food_state: FoodState | None = None
                    if food_state_raw:
                        try:
                            food_state = FoodState(food_state_raw.upper())
                        except ValueError:
                            pass  # ignore unknown values, fall back to None

                    # ------------------------------------------------------------
                    # 4. Persist via VirtualFridgeService
                    # ------------------------------------------------------------
                    try:
                        item = await fridge_service.create_item(
                            user_id=principal.user_id,
                            ingredient_id=ingredient.ingredient_id,
                            quantity=quantity,
                            unit=unit,
                            food_state=food_state,
                            expiry_date=expiry_date,
                        )
                        added.append({
                            "ingredient_name": name,
                            "matched_as": ingredient.name,
                            "quantity": float(item.quantity),
                            "unit": item.unit,
                            "expiry_date": item.expiry_date.isoformat(),
                        })
                    except Exception as exc:
                        # Surface domain errors (invalid quantity etc.) as not_found
                        not_found.append(f"{name} (error: {exc})")

            return {
                "added": added,
                "not_found": not_found,
                "total_added": len(added),
                "total_not_found": len(not_found),
            }

        return await auditor.invoke(
            principal=principal,
            tool_name=ADD_TOOL_NAME,
            operation=add_operation,
        )

    add_to_fridge.__name__ = ADD_TOOL_NAME
    return add_to_fridge
