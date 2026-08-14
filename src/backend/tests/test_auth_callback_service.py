from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from identity.domain.entities import User, UserStatus
from identity.domain.errors import AuthenticationError
from identity.infrastructure.authentik_client import TokenSet
from identity.service.auth_service import AuthService
from identity.service.oidc_transaction import OidcTransaction


class FakeAuthentikClient:
    def __init__(
        self,
        token_set: TokenSet,
        userinfo: dict[str, Any] | None = None,
    ) -> None:
        self.token_set = token_set
        self.userinfo_response = userinfo or {}
        self.userinfo_calls = 0

    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenSet:
        return self.token_set

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        self.userinfo_calls += 1
        return self.userinfo_response


class FakeCallbackJwtVerifier:
    def __init__(
        self,
        *,
        id_token_claims: dict[str, Any],
        access_token_claims: dict[str, Any],
    ) -> None:
        self.id_token_claims = id_token_claims
        self.access_token_claims = access_token_claims
        self.expected_nonce: str | None = None

    async def verify_id_token(
        self,
        token: str,
        *,
        expected_nonce: str,
    ) -> dict[str, Any]:
        self.expected_nonce = expected_nonce
        return self.id_token_claims

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        return self.access_token_claims


class FakeCallbackUserRepository:
    def __init__(self) -> None:
        self.upserted_profile: dict[str, str | None] | None = None

    async def upsert_from_authentik_claims(
        self,
        *,
        authentik_sub: str,
        username: str,
        email: str | None,
    ) -> User:
        self.upserted_profile = {
            "authentik_sub": authentik_sub,
            "username": username,
            "email": email,
        }
        now = datetime.now(UTC)
        return User(
            user_id=uuid4(),
            authentik_sub=authentik_sub,
            username=username,
            email=email,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )


def make_transaction() -> OidcTransaction:
    return OidcTransaction(
        state="state",
        nonce="expected-nonce",
        code_verifier="code-verifier",
        code_challenge="code-challenge",
        return_to="/",
    )


def make_token_set(*, id_token: str | None = "id-token") -> TokenSet:
    return TokenSet(
        access_token="access-token",
        refresh_token="refresh-token",
        id_token=id_token,
        expires_in=900,
    )


def make_service(
    *,
    token_set: TokenSet | None = None,
    id_token_claims: dict[str, Any] | None = None,
    access_token_claims: dict[str, Any] | None = None,
    userinfo: dict[str, Any] | None = None,
) -> tuple[
    AuthService,
    FakeAuthentikClient,
    FakeCallbackJwtVerifier,
    FakeCallbackUserRepository,
]:
    client = FakeAuthentikClient(token_set or make_token_set(), userinfo)
    verifier = FakeCallbackJwtVerifier(
        id_token_claims=id_token_claims
        or {
            "sub": "authentik-user-1",
            "preferred_username": "ada",
            "email": "ada@example.com",
        },
        access_token_claims=access_token_claims
        or {"sub": "authentik-user-1"},
    )
    repository = FakeCallbackUserRepository()
    service = AuthService(
        authentik_client=client,  # type: ignore[arg-type]
        jwt_verifier=verifier,  # type: ignore[arg-type]
        user_repository=repository,  # type: ignore[arg-type]
    )
    return service, client, verifier, repository


@pytest.mark.anyio
async def test_complete_callback_validates_id_token_with_transaction_nonce() -> None:
    service, client, verifier, repository = make_service()

    _token_set, user = await service.complete_callback(
        code="authorization-code",
        transaction=make_transaction(),
    )

    assert verifier.expected_nonce == "expected-nonce"
    assert client.userinfo_calls == 0
    assert repository.upserted_profile == {
        "authentik_sub": "authentik-user-1",
        "username": "ada",
        "email": "ada@example.com",
    }
    assert user.authentik_sub == "authentik-user-1"


@pytest.mark.anyio
async def test_complete_callback_rejects_missing_id_token() -> None:
    service, _client, verifier, repository = make_service(
        token_set=make_token_set(id_token=None)
    )

    with pytest.raises(AuthenticationError):
        await service.complete_callback(
            code="authorization-code",
            transaction=make_transaction(),
        )

    assert verifier.expected_nonce is None
    assert repository.upserted_profile is None


@pytest.mark.anyio
async def test_complete_callback_rejects_access_token_for_another_subject() -> None:
    service, _client, _verifier, repository = make_service(
        access_token_claims={"sub": "different-user"}
    )

    with pytest.raises(AuthenticationError):
        await service.complete_callback(
            code="authorization-code",
            transaction=make_transaction(),
        )

    assert repository.upserted_profile is None


@pytest.mark.anyio
async def test_complete_callback_rejects_userinfo_for_another_subject() -> None:
    service, client, _verifier, repository = make_service(
        id_token_claims={"sub": "authentik-user-1"},
        userinfo={
            "sub": "different-user",
            "preferred_username": "mallory",
            "email": "mallory@example.com",
        },
    )

    with pytest.raises(AuthenticationError):
        await service.complete_callback(
            code="authorization-code",
            transaction=make_transaction(),
        )

    assert client.userinfo_calls == 1
    assert repository.upserted_profile is None


@pytest.mark.anyio
async def test_complete_callback_accepts_userinfo_with_matching_subject() -> None:
    service, client, _verifier, repository = make_service(
        id_token_claims={"sub": "authentik-user-1"},
        userinfo={
            "sub": "authentik-user-1",
            "preferred_username": "ada",
            "email": "ada@example.com",
        },
    )

    await service.complete_callback(
        code="authorization-code",
        transaction=make_transaction(),
    )

    assert client.userinfo_calls == 1
    assert repository.upserted_profile == {
        "authentik_sub": "authentik-user-1",
        "username": "ada",
        "email": "ada@example.com",
    }
