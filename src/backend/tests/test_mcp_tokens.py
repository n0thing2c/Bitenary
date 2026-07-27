from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from bitenary_mcp.domain.entities import (
    MCPAuthRecord,
    MCPClient,
    MCPClientStatus,
    MCPClientType,
)
from bitenary_mcp.domain.errors import DuplicateTokenPrefixError
from bitenary_mcp.service.authentication import MCPAuthenticationService
from bitenary_mcp.service.connections import MCPConnectionService
from bitenary_mcp.service.tokens import MCPTokenCodec


def make_client(
    *,
    token_prefix: str,
    token_digest: str,
    expires_at: datetime | None = None,
    status: MCPClientStatus = MCPClientStatus.ACTIVE,
    revoked_at: datetime | None = None,
) -> MCPClient:
    now = datetime.now(UTC)
    return MCPClient(
        client_id=uuid4(),
        user_id=uuid4(),
        client_type=MCPClientType.CODEX,
        display_name="My Codex",
        token_prefix=token_prefix,
        token_digest=token_digest,
        status=status,
        expires_at=expires_at or now + timedelta(days=90),
        revoked_at=revoked_at,
        last_used_at=None,
        created_at=now,
        updated_at=now,
    )


class FakeClientRepository:
    def __init__(
        self,
        *,
        auth_record: MCPAuthRecord | None = None,
        collisions: int = 0,
    ) -> None:
        self.auth_record = auth_record
        self.collisions = collisions
        self.created_digests: list[str] = []

    async def create(self, **values: object) -> MCPClient:
        self.created_digests.append(str(values["token_digest"]))
        if self.collisions:
            self.collisions -= 1
            raise DuplicateTokenPrefixError
        return make_client(
            token_prefix=str(values["token_prefix"]),
            token_digest=str(values["token_digest"]),
            expires_at=values["expires_at"],  # type: ignore[arg-type]
        )

    async def get_auth_record_by_prefix(
        self,
        token_prefix: str,
    ) -> MCPAuthRecord | None:
        if (
            self.auth_record is not None
            and self.auth_record.connection.token_prefix == token_prefix
        ):
            return self.auth_record
        return None


def test_token_codec_generates_expected_format_and_digest() -> None:
    codec = MCPTokenCodec(
        "pepper",
        lookup_factory=lambda: "a1b2c3d4",
        secret_factory=lambda: "s" * 43,
    )

    token, prefix, digest = codec.generate()

    assert token == f"bty_mcp_a1b2c3d4.{'s' * 43}"
    assert prefix == "bty_mcp_a1b2c3d4"
    assert len(digest) == 64
    assert codec.parse_prefix(token) == prefix
    assert codec.matches(token, digest) is True
    assert codec.matches(f"{token}x", digest) is False


@pytest.mark.parametrize(
    "token",
    [
        "",
        "Bearer token",
        "bty_mcp_short.secret",
        f"bty_mcp_ABCDEF12.{'s' * 43}",
        f"bty_mcp_abcdef12.{'s' * 20}",
    ],
)
def test_token_codec_rejects_malformed_tokens(token: str) -> None:
    assert MCPTokenCodec("pepper").parse_prefix(token) is None


@pytest.mark.anyio
async def test_connection_creation_retries_prefix_collision() -> None:
    repository = FakeClientRepository(collisions=1)
    lookups = iter(["11111111", "22222222"])
    codec = MCPTokenCodec(
        "pepper",
        lookup_factory=lambda: next(lookups),
        secret_factory=lambda: "s" * 43,
    )
    service = MCPConnectionService(
        repository=repository,  # type: ignore[arg-type]
        token_codec=codec,
        token_ttl_days=90,
    )

    created = await service.create(
        user_id=uuid4(),
        client_type=MCPClientType.CODEX,
        display_name="My Codex",
    )

    assert created.connection.token_prefix == "bty_mcp_22222222"
    assert created.connection.expires_at > datetime.now(UTC) + timedelta(days=89)
    assert len(repository.created_digests) == 2
    assert created.plaintext_token not in repository.created_digests


@pytest.mark.anyio
async def test_authentication_accepts_valid_token() -> None:
    codec = MCPTokenCodec(
        "pepper",
        lookup_factory=lambda: "a1b2c3d4",
        secret_factory=lambda: "s" * 43,
    )
    token, prefix, digest = codec.generate()
    client = make_client(token_prefix=prefix, token_digest=digest)
    repository = FakeClientRepository(
        auth_record=MCPAuthRecord(connection=client, user_is_active=True)
    )

    principal = await MCPAuthenticationService(
        repository=repository,  # type: ignore[arg-type]
        token_codec=codec,
    ).authenticate(token)

    assert principal is not None
    assert principal.client_id == client.client_id
    assert principal.user_id == client.user_id


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("connection_change", "user_is_active"),
    [
        ({"expires_at": datetime.now(UTC) - timedelta(seconds=1)}, True),
        ({"revoked_at": datetime.now(UTC)}, True),
        ({"status": MCPClientStatus.DISABLED}, True),
        ({}, False),
    ],
)
async def test_authentication_rejects_inactive_credentials(
    connection_change: dict[str, object],
    user_is_active: bool,
) -> None:
    codec = MCPTokenCodec(
        "pepper",
        lookup_factory=lambda: "a1b2c3d4",
        secret_factory=lambda: "s" * 43,
    )
    token, prefix, digest = codec.generate()
    client = make_client(
        token_prefix=prefix,
        token_digest=digest,
        **connection_change,  # type: ignore[arg-type]
    )
    repository = FakeClientRepository(
        auth_record=MCPAuthRecord(
            connection=client,
            user_is_active=user_is_active,
        )
    )

    principal = await MCPAuthenticationService(
        repository=repository,  # type: ignore[arg-type]
        token_codec=codec,
    ).authenticate(token)

    assert principal is None


@pytest.mark.anyio
async def test_authentication_rejects_wrong_secret() -> None:
    codec = MCPTokenCodec("pepper")
    prefix = "bty_mcp_a1b2c3d4"
    stored_token = f"{prefix}.{'s' * 43}"
    presented_token = f"{prefix}.{'x' * 43}"
    repository = FakeClientRepository(
        auth_record=MCPAuthRecord(
            connection=make_client(
                token_prefix=prefix,
                token_digest=codec.digest(stored_token),
            ),
            user_is_active=True,
        )
    )

    principal = await MCPAuthenticationService(
        repository=repository,  # type: ignore[arg-type]
        token_codec=codec,
    ).authenticate(presented_token)

    assert principal is None
