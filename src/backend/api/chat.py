"""REST API endpoint for the Bitenary AI chat feature.

The endpoint proxies user messages to the LLM Orchestrator, which manages
Gemini, MCP tool-calling, and Redis-backed conversation memory.

All routes require an authenticated session. The user's health profile is
automatically injected into the AI's system prompt so responses are
personalised (goals, allergies, dietary restrictions, etc.).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette import status

from health_profile.domain.entities import HealthProfile, HealthProfileOnboardingState
from health_profile.service.profiles import HealthProfileService
from health_profile.wiring import get_health_profile_service
from identity.domain.entities import CurrentUser
from identity.wiring import get_current_user
from virtual_fridge.domain.entities import ExpiryStatus, FridgeItem, expiry_status_for
from virtual_fridge.service.fridge import VirtualFridgeService
from virtual_fridge.wiring import get_virtual_fridge_service


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat payload from the frontend."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description=(
            "A frontend-generated session identifier (e.g. a UUID). "
            "Multiple sessions per user are supported. "
            "The server namespaces Redis keys by user_id + session_id."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The user's message.",
        examples=["Một tô phở bò có bao nhiêu calo?"],
    )


class ChatResponse(BaseModel):
    """Outgoing chat payload to the frontend."""

    session_id: str
    reply: str


class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    updated_at: str

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ClearHistoryRequest(BaseModel):
    """Payload for clearing conversation history."""

    session_id: str = Field(..., min_length=1, max_length=128)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the Bitenary AI assistant",
    description=(
        "Forwards the user's message to the LLM Orchestrator (Gemini + MCP Tools). "
        "The AI is automatically personalised with the authenticated user's health "
        "profile (weight, goals, allergies, etc.) so responses are tailored and safe. "
        "Conversation history is stored server-side in Redis, keyed by user + session."
    ),
)
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    profile_service: HealthProfileService = Depends(get_health_profile_service),
    fridge_service: VirtualFridgeService = Depends(get_virtual_fridge_service),
) -> ChatResponse:
    """Main chat endpoint.

    1. Authenticates the user via cookie (via ``get_current_user``).
    2. Fetches the user's health profile (if onboarding is complete).
    3. Fetches any fridge items that are expiring soon (Push context).
    4. Passes everything to the Orchestrator which calls Gemini + MCP tools.
    """
    orchestrator = request.app.state.orchestrator

    # Fetch health profile — ``None`` if user skipped onboarding or has no profile yet.
    health_profile: HealthProfile | None = await _resolve_profile(
        profile_service, current_user
    )

    # Fetch expiring fridge items for proactive push context.
    # Errors are swallowed so a DB hiccup never blocks the chat feature.
    expiring_items: tuple[FridgeItem, ...] = await _resolve_expiring_items(
        fridge_service, current_user
    )

    try:
        reply = await orchestrator.chat(
            user_id=current_user.user_id,
            session_id=body.session_id,
            user_message=body.message,
            health_profile=health_profile,
            expiring_items=expiring_items or None,
        )
    except Exception as exc:
        import traceback
        import logging
        logging.getLogger(__name__).error("Chat orchestrator failed:\n%s", traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service temporarily unavailable: {exc}",
        ) from exc

    return ChatResponse(session_id=body.session_id, reply=reply)


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear conversation history for a session",
)
async def clear_history(
    request: Request,
    body: ClearHistoryRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete all stored conversation turns for the given session_id.

    Only the authenticated user can clear their own history.
    """
    orchestrator = request.app.state.orchestrator
    await orchestrator.clear_history(
        user_id=current_user.user_id,
        session_id=body.session_id,
    )


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="Get recent chat sessions for the current user",
)
async def list_sessions(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ChatSessionResponse]:
    orchestrator = request.app.state.orchestrator
    sessions = await orchestrator.list_sessions(current_user.user_id)
    return [
        ChatSessionResponse(
            session_id=s.session_id,
            title=s.title,
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    summary="Get all messages for a specific chat session",
)
async def get_session_messages(
    session_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ChatMessageResponse]:
    orchestrator = request.app.state.orchestrator
    messages = await orchestrator.get_session_messages(session_id, current_user.user_id)
    if not messages:
        # If no messages or not authorized, return empty.
        # Alternatively we could raise 404, but returning empty array is safe.
        return []
        
    return [
        ChatMessageResponse(
            id=str(m.message_id),
            role=str(m.role),
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _resolve_profile(
    service: HealthProfileService,
    user: CurrentUser,
) -> HealthProfile | None:
    """Return the health profile for the given user, or None.

    We intentionally swallow any repository errors here and fall back to
    ``None`` so a database hiccup does not block the user from chatting.
    The AI will simply respond without personalised context.
    """
    try:
        state = await service.get_state(user.user_id)
        if state.onboarding_state == HealthProfileOnboardingState.COMPLETED:
            return state.profile
        return None
    except Exception:
        return None


async def _resolve_expiring_items(
    service: VirtualFridgeService,
    user: CurrentUser,
) -> tuple[FridgeItem, ...]:
    """Return only items that are expiring today or very soon.

    We filter in-memory (not in SQL) because ``get_available_ingredients``
    already limits results to non-expired items and is indexed on
    ``(user_id, expiry_date)``. The expected result set is small (< 100 rows)
    so this is fast and keeps the query simple.

    Errors are swallowed — the chat feature must never depend on fridge data.
    """
    try:
        today = date.today()
        urgent_statuses = {ExpiryStatus.EXPIRING_SOON, ExpiryStatus.EXPIRING_TODAY}
        all_items = await service.get_available_ingredients(
            user_id=user.user_id,
            today=today,
        )
        return tuple(
            item
            for item in all_items
            if expiry_status_for(item.expiry_date, today=today) in urgent_statuses
        )
    except Exception:
        return ()
