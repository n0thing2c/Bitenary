"""SQLAlchemy ORM models and repository for chat history persistence.

Design rationale
----------------
- ``chat_sessions``: one row per (user_id, session_id) pair.  The ``session_id``
  is the *frontend-generated* UUID string that already keys the Redis entry, so
  we reuse it as a natural primary key — no surrogate key needed.
- ``chat_messages``: append-only table.  Messages are never updated, only
  inserted (and deleted on session clear via CASCADE).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from chat_history.domain.entities import ChatMessage, ChatRole, ChatSession
from core.database import Base


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_chat_sessions_user_id", "user_id"),
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True
    )
    session_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Domain ↔ ORM converters
# ---------------------------------------------------------------------------

def _session_to_domain(m: ChatSessionModel) -> ChatSession:
    return ChatSession(
        session_id=m.session_id,
        user_id=m.user_id,
        title=m.title,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _message_to_domain(m: ChatMessageModel) -> ChatMessage:
    return ChatMessage(
        message_id=m.message_id,
        session_id=m.session_id,
        role=ChatRole(m.role),
        content=m.content,
        created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class SqlAlchemyChatHistoryRepository:
    """Postgres-backed repository for chat sessions and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Return the ChatSession row, or None if not found."""
        row = await self._session.get(ChatSessionModel, session_id)
        return _session_to_domain(row) if row else None

    async def create_session(
        self, *, session_id: str, user_id: UUID, title: str
    ) -> ChatSession:
        """Insert a new ChatSession row and flush to obtain server defaults."""
        now = datetime.now(UTC)
        model = ChatSessionModel(
            session_id=session_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _session_to_domain(model)

    async def touch_session(self, session_id: str) -> None:
        """Update updated_at so the session floats to the top of Sidebar lists."""
        await self._session.execute(
            update(ChatSessionModel)
            .where(ChatSessionModel.session_id == session_id)
            .values(updated_at=func.now())
        )

    async def append_messages(
        self, *, session_id: str, human_content: str, ai_content: str
    ) -> None:
        """Append a human + AI message pair in one flush."""
        now = datetime.now(UTC)
        self._session.add_all([
            ChatMessageModel(
                message_id=uuid.uuid4(),
                session_id=session_id,
                role=ChatRole.HUMAN,
                content=human_content,
                created_at=now,
            ),
            ChatMessageModel(
                message_id=uuid.uuid4(),
                session_id=session_id,
                role=ChatRole.AI,
                content=ai_content,
                # offset by 1µs so AI message always sorts after human message
                created_at=now.replace(microsecond=now.microsecond + 1),
            ),
        ])
        await self._session.flush()

    async def delete_session(self, session_id: str) -> None:
        """Delete the session and all its messages (CASCADE)."""
        row = await self._session.get(ChatSessionModel, session_id)
        if row:
            await self._session.delete(row)
            await self._session.flush()

    async def list_sessions_for_user(
        self, user_id: UUID, *, limit: int = 20
    ) -> list[ChatSession]:
        """Return the N most recently active sessions for a user."""
        stmt = (
            select(ChatSessionModel)
            .where(ChatSessionModel.user_id == user_id)
            .order_by(ChatSessionModel.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_session_to_domain(m) for m in result.scalars().all()]
