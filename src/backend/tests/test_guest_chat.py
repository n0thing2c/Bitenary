from __future__ import annotations

from uuid import uuid4

import pytest

from guest_chat.service import (
    GuestChatRateLimitExceeded,
    GuestChatRateLimiter,
    GuestIdentityCodec,
)


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = seconds
        return True


def test_guest_identity_cookie_is_signed_and_reusable() -> None:
    codec = GuestIdentityCodec("guest-test-secret")
    guest_id = uuid4()

    token = codec.encode(guest_id)

    assert codec.decode(token) == guest_id
    assert codec.decode(f"{token}tampered") is None


@pytest.mark.asyncio
async def test_rate_limiter_rejects_guest_minute_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = GuestChatRateLimiter("redis://unused", per_minute=2, per_day=50)
    limiter._redis = FakeRedis()  # type: ignore[assignment]
    monkeypatch.setattr("guest_chat.service.time.time", lambda: 120)
    guest_id = uuid4()

    await limiter.check(guest_id=guest_id, remote_ip="192.0.2.1")
    await limiter.check(guest_id=guest_id, remote_ip="192.0.2.1")

    with pytest.raises(GuestChatRateLimitExceeded) as exc_info:
        await limiter.check(guest_id=guest_id, remote_ip="192.0.2.1")

    assert exc_info.value.retry_after == 60


@pytest.mark.asyncio
async def test_rate_limiter_combines_different_guests_by_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = GuestChatRateLimiter("redis://unused", per_minute=2, per_day=50)
    limiter._redis = FakeRedis()  # type: ignore[assignment]
    monkeypatch.setattr("guest_chat.service.time.time", lambda: 150)

    await limiter.check(guest_id=uuid4(), remote_ip="192.0.2.10")
    await limiter.check(guest_id=uuid4(), remote_ip="192.0.2.10")

    with pytest.raises(GuestChatRateLimitExceeded):
        await limiter.check(guest_id=uuid4(), remote_ip="192.0.2.10")


@pytest.mark.asyncio
async def test_rate_limiter_enforces_daily_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = GuestChatRateLimiter("redis://unused", per_minute=100, per_day=2)
    limiter._redis = FakeRedis()  # type: ignore[assignment]
    monkeypatch.setattr("guest_chat.service.time.time", lambda: 3600)
    guest_id = uuid4()

    await limiter.check(guest_id=guest_id, remote_ip="198.51.100.5")
    await limiter.check(guest_id=guest_id, remote_ip="198.51.100.5")

    with pytest.raises(GuestChatRateLimitExceeded) as exc_info:
        await limiter.check(guest_id=guest_id, remote_ip="198.51.100.5")

    assert exc_info.value.retry_after == 82800
