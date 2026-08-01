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
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from redis import asyncio as aioredis

from agents.prompts import SYSTEM_PROMPT
from core.config import Settings

logger = logging.getLogger(__name__)

# Default Gemini model — can be overridden via settings in the future.
_GEMINI_MODEL = "gemini-3.0-flash"

# Maximum conversation history turns to send to Gemini.
# Each "turn" = 1 HumanMessage + 1 AIMessage, so 10 turns = 20 messages.
_MAX_HISTORY_TURNS = 10

# Redis key template: chat:v1:<session_id>
_REDIS_KEY_PREFIX = "chat:v1:"


class BitenaryChatOrchestrator:
    """Stateless orchestrator that processes one chat turn per ``chat`` call.

    The orchestrator is intentionally stateless itself — all persistence
    happens in Redis. This makes it safe to instantiate once per app
    lifetime and call concurrently from multiple requests.

    Usage::

        orchestrator = BitenaryChatOrchestrator(settings)
        response = await orchestrator.chat(
            session_id="user-uuid-or-session-token",
            user_message="a bowl of pho bao nhiêu calo?",
        )
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
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

    async def chat(self, session_id: str, user_message: str) -> str:
        """Process one chat turn and return the AI's response.

        Args:
            session_id: A unique identifier for the conversation (e.g. user
                ID or anonymous session token). Used as the Redis key.
            user_message: The raw message typed by the user.

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
        history = await self._load_history(session_id)
        logger.debug("Session %s: loaded %d history messages.", session_id, len(history))

        # 2. Build the full messages list for the agent
        messages: list[BaseMessage] = [
            SystemMessage(content=SYSTEM_PROMPT),
            *history,
            HumanMessage(content=user_message),
        ]

        # 3. Connect to MCP Server and invoke the agent
        mcp_config = self._build_mcp_config()
        async with MultiServerMCPClient(mcp_config) as mcp_client:
            tools = mcp_client.get_tools()
            logger.debug("Session %s: loaded %d MCP tools.", session_id, len(tools))

            agent = create_react_agent(self._llm, tools)
            result: dict[str, Any] = await agent.ainvoke({"messages": messages})

        # 4. Extract the final text reply
        reply = _extract_reply(result)

        # 5. Persist this turn back to Redis
        await self._save_turn(session_id, user_message, reply)
        logger.debug("Session %s: saved turn to Redis.", session_id)

        return reply

    async def clear_history(self, session_id: str) -> None:
        """Delete the entire conversation history for a session."""
        if self._redis:
            await self._redis.delete(_REDIS_KEY_PREFIX + session_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_mcp_config(self) -> dict[str, Any]:
        """Build the MultiServerMCPClient config pointing to our own MCP server.

        We connect to the Bitenary MCP server via Streamable HTTP.
        This guarantees we speak the full MCP protocol (list_tools → call_tool)
        just like any external agent would.
        """
        mcp_server_url = self._settings.backend_public_url.rstrip("/") + "/mcp"
        return {
            "bitenary": {
                "transport": "streamable_http",
                "url": mcp_server_url,
            }
        }

    async def _load_history(self, session_id: str) -> list[BaseMessage]:
        """Return the last N turns of conversation from Redis."""
        key = _REDIS_KEY_PREFIX + session_id
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
        session_id: str,
        user_message: str,
        ai_reply: str,
    ) -> None:
        """Append this turn to the Redis list and set a 24-hour expiry."""
        key = _REDIS_KEY_PREFIX + session_id
        await self._redis.rpush(key, "human", user_message, "ai", ai_reply)  # type: ignore[union-attr]
        await self._redis.expire(key, 86400)  # 24 hours TTL


def _extract_reply(agent_result: dict[str, Any]) -> str:
    """Pull the last AIMessage content from a LangGraph agent response."""
    messages: list[BaseMessage] = agent_result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return "Xin lỗi, tôi không thể tạo ra câu trả lời lúc này. Vui lòng thử lại."
