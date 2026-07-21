from uuid import UUID

from pydantic import BaseModel

from identity.domain.entities import UserStatus


class CurrentUserResponse(BaseModel):
    user_id: UUID
    authentik_sub: str
    username: str
    email: str | None
    status: UserStatus


class CsrfResponse(BaseModel):
    csrf_token: str
