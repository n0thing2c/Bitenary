from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import csrf_headers
from app.main import create_app
from bitenary_mcp.domain.entities import (
    CreatedMCPConnection,
    MCPClient,
    MCPClientStatus,
    MCPClientType,
)
from bitenary_mcp.domain.errors import MCPConnectionNotFoundError
from bitenary_mcp.wiring import get_mcp_connection_service
from identity.domain.entities import CurrentUser, UserStatus
from identity.wiring import get_current_user


def make_connection(*, user_id=None) -> MCPClient:
    now = datetime.now(UTC)
    return MCPClient(
        client_id=uuid4(),
        user_id=user_id or uuid4(),
        client_type=MCPClientType.CODEX,
        display_name="My Codex",
        token_prefix="bty_mcp_a1b2c3d4",
        token_digest="digest-that-must-never-be-returned",
        status=MCPClientStatus.ACTIVE,
        expires_at=now + timedelta(days=90),
        revoked_at=None,
        last_used_at=None,
        created_at=now,
        updated_at=now,
    )


class FakeConnectionService:
    def __init__(self, connection: MCPClient) -> None:
        self.connection = connection
        self.fail_revoke = False

    async def create(self, **_values: object) -> CreatedMCPConnection:
        return CreatedMCPConnection(
            connection=self.connection,
            plaintext_token=f"{self.connection.token_prefix}.{'s' * 43}",
        )

    async def list_for_user(self, _user_id):
        return [self.connection]

    async def revoke(self, **_values: object) -> None:
        if self.fail_revoke:
            raise MCPConnectionNotFoundError


@pytest.fixture()
def mcp_route_client() -> tuple[TestClient, FakeConnectionService, CurrentUser]:
    user = CurrentUser(
        user_id=uuid4(),
        authentik_sub="authentik-user-1",
        username="Ada",
        email="ada@example.com",
        status=UserStatus.ACTIVE,
    )
    service = FakeConnectionService(make_connection(user_id=user.user_id))
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_mcp_connection_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, user
    app.dependency_overrides.clear()


def test_create_connection_requires_csrf(
    mcp_route_client: tuple[TestClient, FakeConnectionService, CurrentUser],
) -> None:
    client, _service, _user = mcp_route_client

    response = client.post(
        "/api/mcp-connections",
        json={"client_type": "CODEX", "display_name": "My Codex"},
    )

    assert response.status_code == 403


def test_create_connection_discloses_token_once_and_safe_snippets(
    mcp_route_client: tuple[TestClient, FakeConnectionService, CurrentUser],
) -> None:
    client, _service, _user = mcp_route_client
    response = client.post(
        "/api/mcp-connections",
        headers=csrf_headers(client),
        json={"client_type": "CODEX", "display_name": "  My Codex  "},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["token"].startswith("bty_mcp_")
    assert "token_digest" not in payload
    assert payload["token"] not in payload["codex_config"]
    assert payload["token"] not in payload["claude_config"]
    assert "BITENARY_MCP_TOKEN" in payload["codex_config"]
    assert "BITENARY_MCP_TOKEN" in payload["claude_config"]
    assert payload["mcp_url"] == "http://localhost:8000/mcp"


def test_list_connection_never_returns_plaintext_or_digest(
    mcp_route_client: tuple[TestClient, FakeConnectionService, CurrentUser],
) -> None:
    client, _service, _user = mcp_route_client

    response = client.get("/api/mcp-connections")

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["state"] == "ACTIVE"
    assert "token" not in payload
    assert "token_digest" not in payload


def test_revoke_is_owner_scoped_and_requires_csrf(
    mcp_route_client: tuple[TestClient, FakeConnectionService, CurrentUser],
) -> None:
    client, service, _user = mcp_route_client
    service.fail_revoke = True

    response = client.delete(
        f"/api/mcp-connections/{service.connection.client_id}",
        headers=csrf_headers(client),
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer malformed-token"],
)
def test_mcp_endpoint_uses_same_generic_401(
    authorization: str | None,
) -> None:
    app = create_app()
    headers = {"Authorization": authorization} if authorization else {}
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "invalid_token",
        "error_description": "Authentication required",
    }
