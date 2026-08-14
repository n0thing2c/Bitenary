"""Business-logic service for persisting chat history to PostgreSQL.

This service runs *in addition to* the Redis cache — it is a write-through
sync layer that stores messages permanently so users can retrieve their
conversation history across multiple sessions and browser restarts.

Redis remains the authoritative fast-path for loading context into the LLM.
Postgres is the durable store for the Sidebar / History UI feature.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from chat_history.domain.entities import ChatMessage, ChatSession
from chat_history.infrastructure.sqlalchemy_history import SqlAlchemyChatHistoryRepository

logger = logging.getLogger(__name__)

# Maximum title length derived from the first human message.
_TITLE_MAX_CHARS = 80


class ChatHistoryService:
    """Syncs one chat turn to Postgres after it has been saved to Redis.

    Usage::

        service = ChatHistoryService(session_factory)
        await service.sync_turn(
            user_id=user.id,
            session_id="abc123",
            human_message="Hello!",
            ai_reply="Hi there!",
        )
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def sync_turn(
        self,
        *,
        user_id: UUID,
        session_id: str,
        human_message: str,
        ai_reply: str,
    ) -> None:
        """Persist one Human+AI turn to Postgres.

        If this is the very first message in the session, a new ChatSession row
        is automatically created and its title is derived from the first 80
        characters of the human message.

        Args:
            user_id:        The authenticated user's UUID.
            session_id:     The frontend-generated session identifier (same key
                            used for the Redis entry).
            human_message:  The raw text sent by the user.
            ai_reply:       The full AI response text.
        """
        try:
            async with self._session_factory() as db:
                repo = SqlAlchemyChatHistoryRepository(db)

                # 1. Ensure the session row exists
                existing = await repo.get_session(session_id)
                if existing is None:
                    title = _derive_title(human_message)
                    await repo.create_session(
                        session_id=session_id,
                        user_id=user_id,
                        title=title,
                    )
                else:
                    if existing.user_id != user_id:
                        logger.warning(
                            "Rejected chat history sync for session %s: "
                            "session owner does not match user %s",
                            session_id,
                            user_id,
                        )
                        return

                    # Push the session to the top of Sidebar listing
                    await repo.touch_session(
                        user_id=user_id,
                        session_id=session_id,
                    )

                # 2. Append the message pair
                await repo.append_messages(
                    session_id=session_id,
                    human_content=human_message,
                    ai_content=ai_reply,
                )

                await db.commit()
        except Exception:
            # Swallow DB errors — a Postgres hiccup must never block the chat.
            logger.exception(
                "ChatHistoryService.sync_turn failed for session %s", session_id
            )

    async def list_sessions(self, user_id: UUID, limit: int = 20) -> list[ChatSession]:
        """Return the N most recently active sessions for a user."""
        async with self._session_factory() as db:
            repo = SqlAlchemyChatHistoryRepository(db)
            return await repo.list_sessions_for_user(user_id, limit=limit)

    async def get_session_messages(
        self, session_id: str, user_id: UUID
    ) -> list[ChatMessage]:
        """Return all messages for a session, ensuring the user owns it."""
        async with self._session_factory() as db:
            repo = SqlAlchemyChatHistoryRepository(db)
            session = await repo.get_session(session_id)
            if not session or session.user_id != user_id:
                # If session doesn't exist or belongs to someone else, return empty list
                return []
            return await repo.get_messages_for_session(session_id)

    async def clear_session(self, *, user_id: UUID, session_id: str) -> None:
        """Delete the Postgres session and all its messages (CASCADE).

        Errors are swallowed so that Redis-side deletion still succeeds even
        if Postgres is unavailable.
        """
        try:
            async with self._session_factory() as db:
                repo = SqlAlchemyChatHistoryRepository(db)
                await repo.delete_session(
                    user_id=user_id,
                    session_id=session_id,
                )
                await db.commit()
        except Exception:
            logger.exception(
                "ChatHistoryService.clear_session failed for session %s", session_id
            )


def _derive_title(human_message: str) -> str:
    """Return a short title derived from the first human message."""
    stripped = human_message.strip()
    if len(stripped) <= _TITLE_MAX_CHARS:
        return stripped
    return stripped[:_TITLE_MAX_CHARS].rsplit(" ", 1)[0] + "…"
