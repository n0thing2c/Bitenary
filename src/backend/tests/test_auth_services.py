from datetime import UTC, datetime
from uuid import uuid4

import pytest

from identity.domain.entities import CurrentUser, User, UserStatus
from identity.domain.errors import AuthenticationError, DisabledUserError
from identity.service.auth_service import extract_profile
from identity.service.current_user import CurrentUserService
from identity.service.oidc_transaction import OidcTransactionService, validate_return_to


class FakeJwtVerifier:
    def __init__(self, claims: dict[str, object]) -> None:
        self.claims = claims

    async def verify_access_token(self, token: str) -> dict[str, object]:
        return self.claims


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_by_authentik_sub(self, authentik_sub: str) -> User | None:
        if self.user and self.user.authentik_sub == authentik_sub:
            return self.user
        return None


def make_user(status: UserStatus = UserStatus.ACTIVE) -> User:
    now = datetime.now(UTC)
    return User(
        user_id=uuid4(),
        authentik_sub="authentik-user-1",
        username="Ada",
        email="ada@example.com",
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_oidc_transaction_round_trips_signed_state() -> None:
    service = OidcTransactionService("test-secret")

    transaction = service.create("/dashboard")
    loaded = service.load(transaction.state)

    assert loaded.nonce == transaction.nonce
    assert loaded.code_verifier == transaction.code_verifier
    assert loaded.code_challenge == transaction.code_challenge
    assert loaded.return_to == "/dashboard"


def test_oidc_transaction_rejects_tampered_state() -> None:
    service = OidcTransactionService("test-secret")
    transaction = service.create("/")

    with pytest.raises(AuthenticationError):
        service.load(f"{transaction.state}tampered")


@pytest.mark.parametrize(
    ("return_to", "expected"),
    [
        (None, "/"),
        ("/mcp", "/mcp"),
        ("https://evil.example.com", "/"),
        ("//evil.example.com", "/"),
        ("\\evil", "/"),
        ("relative", "/"),
    ],
)
def test_validate_return_to_allows_only_relative_paths(
    return_to: str | None,
    expected: str,
) -> None:
    assert validate_return_to(return_to) == expected


def test_extract_profile_prefers_authentik_claims() -> None:
    profile = extract_profile(
        {
            "sub": "authentik-user-1",
            "preferred_username": "ada",
            "email": "ada@example.com",
        }
    )

    assert profile == {
        "authentik_sub": "authentik-user-1",
        "username": "ada",
        "email": "ada@example.com",
    }


def test_extract_profile_requires_subject() -> None:
    with pytest.raises(AuthenticationError):
        extract_profile({"email": "ada@example.com"})


@pytest.mark.anyio
async def test_current_user_service_returns_active_user() -> None:
    user = make_user()
    service = CurrentUserService(
        jwt_verifier=FakeJwtVerifier({"sub": user.authentik_sub}),
        user_repository=FakeUserRepository(user),
    )

    current_user = await service.from_access_token("access-token")

    assert isinstance(current_user, CurrentUser)
    assert current_user.user_id == user.user_id
    assert current_user.authentik_sub == user.authentik_sub


@pytest.mark.anyio
async def test_current_user_service_rejects_disabled_user() -> None:
    user = make_user(UserStatus.DISABLED)
    service = CurrentUserService(
        jwt_verifier=FakeJwtVerifier({"sub": user.authentik_sub}),
        user_repository=FakeUserRepository(user),
    )

    with pytest.raises(DisabledUserError):
        await service.from_access_token("access-token")


@pytest.mark.anyio
async def test_current_user_service_rejects_missing_local_user() -> None:
    service = CurrentUserService(
        jwt_verifier=FakeJwtVerifier({"sub": "authentik-user-1"}),
        user_repository=FakeUserRepository(None),
    )

    with pytest.raises(AuthenticationError):
        await service.from_access_token("access-token")
