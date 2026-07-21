from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class User:
    user_id: UUID
    authentik_sub: str
    username: str
    email: str | None
    status: UserStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    authentik_sub: str
    username: str
    email: str | None
    status: UserStatus
