"""REST API endpoint for the Bitenary AI chat feature.

The endpoint proxies user messages to the LLM Orchestrator, which manages
Gemini, MCP tool-calling, and Redis-backed conversation memory.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette import status


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat payload from the frontend."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique session or user ID used to scope conversation history.",
        examples=["user-uuid-1234"],
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


class ClearHistoryRequest(BaseModel):
    """Payload for clearing conversation history."""

    session_id: str = Field(..., min_length=1, max_length=128)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the Bitenary AI assistant",
    description=(
        "Forwards the user's message to the LLM Orchestrator (Gemini + MCP Tools). "
        "The assistant can automatically call nutrition and recipe tools as needed. "
        "Conversation history is stored server-side in Redis, keyed by `session_id`."
    ),
)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Main chat endpoint.

    The orchestrator is retrieved from ``app.state`` where it was placed
    during application startup (see ``app/main.py``).
    """
    orchestrator = request.app.state.orchestrator

    try:
        reply = await orchestrator.chat(
            session_id=body.session_id,
            user_message=body.message,
        )
    except Exception as exc:
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
async def clear_history(request: Request, body: ClearHistoryRequest) -> None:
    """Delete all stored conversation turns for the given session_id."""
    orchestrator = request.app.state.orchestrator
    await orchestrator.clear_history(body.session_id)
