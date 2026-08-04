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
