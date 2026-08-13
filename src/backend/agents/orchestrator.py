"""LLM Orchestrator — the AI brain of Bitenary.

Architecture
------------
This module implements the **MCP Client** side of the Bitenary system.
The orchestrator wraps Google Gemini with a LangGraph ReAct agent and
connects it to the Bitenary MCP Server via the standard MCP protocol.

Flow
----
User message
    → RedisChatMessageHistory (load history)
    → MultiServerMCPClient.get_tools()  ← MCP handshake
    → LangGraph ReAct agent (Gemini decides whether to call a tool)
    → MCP call_tool (if needed)         ← MCP tool execution
    → Gemini generates final answer
    → RedisChatMessageHistory (save history)
    → Return response string
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.prompts import build_system_prompt
from bitenary_mcp.service.tokens import MCPTokenCodec
from chat_history.domain.entities import ChatMessage, ChatSession
from chat_history.service.history import ChatHistoryService
from core.config import Settings

if TYPE_CHECKING:
    from health_profile.domain.entities import HealthProfile
    from virtual_fridge.domain.entities import FridgeItem

logger = logging.getLogger(__name__)

# Default Gemini model — can be overridden via settings in the future.
_GEMINI_MODEL = "gemini-3-flash-preview"

# Maximum conversation history turns to send to Gemini.
# Each "turn" = 1 HumanMessage + 1 AIMessage, so 10 turns = 20 messages.
_MAX_HISTORY_TURNS = 10

# Redis key template: chat:v1:<user_id>:<session_id>
# Using user_id prefix ensures one user cannot access another user's history.
_REDIS_KEY_PREFIX = "chat:v1:"


class BitenaryChatOrchestrator:
    """Stateless orchestrator that processes one chat turn per ``chat`` call.

    The orchestrator is intentionally stateless itself — all persistence
    is split between two stores:

    - **Redis**: Hot cache for the active conversation window. Fast O(1) reads,
      24-hour TTL. Used as the authoritative source when loading context into
      the LLM (per the architecture requirement).
    - **Postgres**: Durable write-through store. Every turn is synced here in
      the background so users can access their full history beyond the Redis
      TTL window (powers the Sidebar / History UI).

    This makes it safe to instantiate once per app lifetime and call
    concurrently from multiple requests.
    """

    def __init__(
        self,
        settings: Settings,
        token_codec: MCPTokenCodec,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._token_codec = token_codec
        self._chat_history = ChatHistoryService(session_factory)
        self._llm = ChatGoogleGenerativeAI(
            model=_GEMINI_MODEL,
            google_api_key=settings.google_api_key,
            temperature=0.2,   # Low temperature → more factual, less hallucination
        )
        self._redis: aioredis.Redis | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Open the Redis connection. Call once during app startup."""
        self._redis = await aioredis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("BitenaryChatOrchestrator: Redis connected at %s", self._settings.redis_url)

    async def shutdown(self) -> None:
        """Close the Redis connection. Call once during app shutdown."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("BitenaryChatOrchestrator: Redis connection closed.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        *,
        user_id: "UUID",
        session_id: str,
        user_message: str,
        health_profile: "HealthProfile | None" = None,
        expiring_items: "tuple[FridgeItem, ...] | None" = None,
    ) -> str:
        """Process one chat turn and return the AI's response.

        Args:
            user_id: The authenticated user's UUID (used as Redis namespace).
            session_id: A secondary key to support multiple chat sessions
                per user (e.g. a frontend-generated UUID).
            user_message: The raw message typed by the user.
            health_profile: The user's health profile, or ``None`` if the
                user has not completed onboarding. The profile is injected
                into the system prompt to personalise every AI response.
            expiring_items: Fridge items that are expiring soon (Push context).
                When provided, the system prompt will proactively instruct the
                AI to remind the user and prioritise these ingredients.
                Pass ``None`` (or omit) when no items are expiring.

        Returns:
            A plain-text string containing the assistant's reply.

        Raises:
            RuntimeError: If ``startup()`` has not been called.
        """
        if self._redis is None:
            raise RuntimeError(
                "Orchestrator not started. Call ``await orchestrator.startup()`` first."
            )

        # 1. Load history from Redis
        history = await self._load_history(user_id, session_id)
        logger.debug("Session %s/%s: loaded %d history messages.", user_id, session_id, len(history))

        # 2. Build personalised system prompt using the user's health profile
        # and any fridge items that are expiring soon (proactive push context).
        system_prompt = build_system_prompt(health_profile, expiring_items=expiring_items)

        # 3. Build the full messages list for the agent
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            *history,
            HumanMessage(content=user_message),
        ]

        # 4. Connect to MCP Server and invoke the agent
        mcp_config = self._build_mcp_config(user_id)
        
        mcp_client = MultiServerMCPClient(mcp_config)
        try:
            tools = await mcp_client.get_tools()
            logger.debug("Session %s/%s: loaded %d MCP tools.", user_id, session_id, len(tools))
    
            agent = create_react_agent(self._llm, tools)
            result: dict[str, Any] = await agent.ainvoke({"messages": messages})
        finally:
            if hasattr(mcp_client, "close"):
                await mcp_client.close()
            elif hasattr(mcp_client, "aclose"):
                await mcp_client.aclose()

        # 5. Extract the final text reply
        reply = _extract_reply(result)

        # 6. Persist this turn back to Redis
        await self._save_turn(user_id, session_id, user_message, reply)
        logger.debug("Session %s/%s: saved turn to Redis.", user_id, session_id)

        return reply

    async def clear_history(self, user_id: UUID, session_id: str) -> None:
        """Delete the entire conversation history for a session (Redis + Postgres)."""
        if self._redis:
            await self._redis.delete(_make_redis_key(user_id, session_id))
        await self._chat_history.clear_session(session_id)

    async def list_sessions(self, user_id: UUID, limit: int = 20) -> list[ChatSession]:
        """List recent chat sessions from Postgres."""
        return await self._chat_history.list_sessions(user_id, limit)

    async def get_session_messages(
        self, session_id: str, user_id: UUID
    ) -> list[ChatMessage]:
        """Get all messages for a session from Postgres."""
        return await self._chat_history.get_session_messages(session_id, user_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_mcp_config(self, user_id: "UUID") -> dict[str, Any]:
        """Build the MultiServerMCPClient config pointing to our own MCP server.

        We connect to the Bitenary MCP server via Streamable HTTP.
        This guarantees we speak the full MCP protocol (list_tools → call_tool)
        just like any external agent would.

        An ephemeral internal token is generated per request and scoped to
        ``user_id``. It is verified server-side via HMAC without a DB hit.
        """
        mcp_server_url = self._settings.backend_public_url.rstrip("/") + "/mcp"
        token = self._token_codec.generate_internal_token(user_id)
        return {
            "bitenary": {
                "transport": "streamable_http",
                "url": mcp_server_url,
                "headers": {
                    "Authorization": f"Bearer {token}",
                },
            }
        }

    async def _load_history(
        self, user_id: "UUID", session_id: str
    ) -> list[BaseMessage]:
        """Return the last N turns of conversation from Redis."""
        key = _make_redis_key(user_id, session_id)
        # Messages are stored as a Redis list: [role, content, role, content, ...]
        raw: list[str] = await self._redis.lrange(key, 0, -1)  # type: ignore[union-attr]

        messages: list[BaseMessage] = []
        # Each pair is (role, content)
        for i in range(0, len(raw) - 1, 2):
            role, content = raw[i], raw[i + 1]
            if role == "human":
                messages.append(HumanMessage(content=content))
            elif role == "ai":
                messages.append(AIMessage(content=content))

        # Trim to the last N turns (2 messages per turn)
        max_msgs = _MAX_HISTORY_TURNS * 2
        return messages[-max_msgs:] if len(messages) > max_msgs else messages

    async def _save_turn(
        self,
        user_id: UUID,
        session_id: str,
        user_message: str,
        ai_reply: str,
    ) -> None:
        """Append this turn to Redis (hot cache) and sync to Postgres (durable)."""
        key = _make_redis_key(user_id, session_id)
        await self._redis.rpush(key, "human", user_message, "ai", ai_reply)  # type: ignore[union-attr]
        await self._redis.expire(key, 86400)  # 24 hours TTL

        # Durable write-through: sync to Postgres in the background.
        # Errors are swallowed inside ChatHistoryService so a DB hiccup never
        # blocks the chat response from reaching the user.
        await self._chat_history.sync_turn(
            user_id=user_id,
            session_id=session_id,
            human_message=user_message,
            ai_reply=ai_reply,
        )


def _make_redis_key(user_id: "UUID", session_id: str) -> str:
    """Build a scoped Redis key to prevent cross-user data leakage."""
    return f"{_REDIS_KEY_PREFIX}{user_id}:{session_id}"


def _extract_reply(agent_result: dict[str, Any]) -> str:
    """Pull the last AIMessage content from a LangGraph agent response.

    Gemini sometimes returns ``content`` as a list of content blocks
    (e.g. ``[{"type": "text", "text": "..."}]``).  We normalise both
    the plain-string and the list-of-blocks cases here.
    """
    messages: list[BaseMessage] = agent_result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            # Case 1: plain string
            if isinstance(content, str):
                return content
            # Case 2: list of content blocks (Gemini multimodal format)
            if isinstance(content, list):
                text_parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                joined = "\n".join(part for part in text_parts if part)
                if joined:
                    return joined
    return "Xin lỗi, tôi không thể tạo ra câu trả lời lúc này. Vui lòng thử lại."
