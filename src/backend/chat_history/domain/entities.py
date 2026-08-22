"""Domain entities for the chat history module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ChatRole(StrEnum):
    HUMAN = "human"
    AI = "ai"


@dataclass(frozen=True)
class ChatMessage:
    message_id: UUID
    session_id: str
    role: ChatRole
    content: str
    created_at: datetime


@dataclass(frozen=True)
class ChatSession:
    session_id: str
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
