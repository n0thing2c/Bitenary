from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from itsdangerous import BadSignature, URLSafeSerializer
from redis import asyncio as aioredis


GUEST_COOKIE_NAME = "bitenary_guest"
GUEST_COOKIE_PATH = "/api/chat/guest"
_GUEST_COOKIE_SALT = "bitenary-guest-chat-v1"


class GuestIdentityCodec:
    def __init__(self, secret: str) -> None:
        self._serializer = URLSafeSerializer(secret, salt=_GUEST_COOKIE_SALT)

    def encode(self, guest_id: UUID) -> str:
        return self._serializer.dumps(str(guest_id))

    def decode(self, token: str | None) -> UUID | None:
        if not token:
            return None
        try:
            value = self._serializer.loads(token)
            return UUID(str(value))
        except (BadSignature, TypeError, ValueError):
            return None

    def resolve(self, token: str | None) -> tuple[UUID, str, bool]:
        guest_id = self.decode(token)
        if guest_id is not None:
            return guest_id, token or "", False
        guest_id = uuid4()
        return guest_id, self.encode(guest_id), True


@dataclass(frozen=True)
class GuestChatRateLimitExceeded(Exception):
    retry_after: int


class GuestChatRateLimiter:
    def __init__(
        self,
        redis_url: str,
        *,
        per_minute: int,
        per_day: int,
    ) -> None:
        self._redis_url = redis_url
        self._per_minute = per_minute
        self._per_day = per_day
        self._redis: aioredis.Redis | None = None

    async def startup(self) -> None:
        self._redis = aioredis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def check(self, *, guest_id: UUID, remote_ip: str) -> None:
        if self._redis is None:
            raise RuntimeError("Guest chat rate limiter is not started")

        ip_digest = hashlib.sha256(remote_ip.encode("utf-8")).hexdigest()[:24]
        now = int(time.time())
        checks = (
            (f"guest:{guest_id}:minute", self._per_minute, 60),
            (f"guest:{guest_id}:day", self._per_day, 86400),
            (f"ip:{ip_digest}:minute", self._per_minute, 60),
            (f"ip:{ip_digest}:day", self._per_day, 86400),
        )

        retry_after = 0
        for identity, limit, window in checks:
            bucket = now // window
            key = f"guest-chat:v1:{identity}:{bucket}"
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, window + 1)
            if count > limit:
                retry_after = max(retry_after, window - (now % window))

        if retry_after:
            raise GuestChatRateLimitExceeded(retry_after=retry_after)
