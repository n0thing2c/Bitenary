from typing import Protocol
from uuid import UUID

from identity.domain.entities import User


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    async def get_by_authentik_sub(self, authentik_sub: str) -> User | None:
        raise NotImplementedError

    async def upsert_from_authentik_claims(
        self,
        *,
        authentik_sub: str,
        username: str,
        email: str | None,
    ) -> User:
        raise NotImplementedError
