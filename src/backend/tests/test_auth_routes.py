from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from identity.delivery.cookies import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from identity.domain.entities import CurrentUser, User, UserStatus
from identity.domain.errors import AuthenticationError
from identity.infrastructure.authentik_client import TokenSet
from identity.service.oidc_transaction import OidcTransactionService
from identity.wiring import get_auth_service, get_current_user, get_oidc_transaction_service


@dataclass
class FakeAuthService:
    token_set: TokenSet | None = None
    fail_callback: bool = False
    revoked_token: str | None = None

    async def complete_callback(self, *, code: str, transaction: object) -> tuple[TokenSet, User]:
        if self.fail_callback or self.token_set is None:
            raise AuthenticationError("callback failed")
        now = datetime.now(UTC)
        user = User(
            user_id=uuid4(),
            authentik_sub="authentik-user-1",
            username="Ada",
            email="ada@example.com",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        return self.token_set, user

    async def refresh(self, refresh_token: str) -> TokenSet:
        if self.token_set is None:
            raise AuthenticationError("refresh failed")
        return self.token_set

    async def logout(self, refresh_token: str | None) -> None:
        self.revoked_token = refresh_token


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_login_redirects_to_authentik_with_pkce(client: TestClient) -> None:
    response = client.get("/api/auth/login?return_to=/dashboard", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:9000/application/o/authorize/")
    assert "response_type=code" in location
    assert "client_id=test-client-id" in location
    assert "code_challenge_method=S256" in location
    assert "state=" in location
    assert "nonce=" in location


def test_signup_redirects_to_authentik_enrollment_flow(client: TestClient) -> None:
    response = client.get(
        "/api/auth/signup?return_to=/dashboard",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:9000/if/flow/default-enrollment-flow/"
    )
    assert (
        "next=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fauth%2Flogin"
        in response.headers["location"]
    )
    assert "return_to%3D%252Fdashboard" in response.headers["location"]


def test_callback_sets_auth_and_csrf_cookies(client: TestClient) -> None:
    transaction_service = OidcTransactionService("test-oidc-state-secret")
    transaction = transaction_service.create("/dashboard")
    fake_auth = FakeAuthService(
        token_set=TokenSet(
            access_token="access-token",
            refresh_token="refresh-token",
            id_token=None,
            expires_in=900,
        )
    )
    client.app.dependency_overrides[get_auth_service] = lambda: fake_auth

    response = client.get(
        f"/api/auth/callback?code=auth-code&state={transaction.state}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/dashboard"
    set_cookie = response.headers.get_list("set-cookie")
    assert any(f"{ACCESS_COOKIE_NAME}=access-token" in cookie for cookie in set_cookie)
    assert any(f"{REFRESH_COOKIE_NAME}=refresh-token" in cookie for cookie in set_cookie)
    assert any("bitenary_csrf=" in cookie for cookie in set_cookie)


def test_callback_rejects_invalid_state(client: TestClient) -> None:
    response = client.get(
        "/api/auth/callback?code=auth-code&state=bad-state",
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    current_user = CurrentUser(
        user_id=uuid4(),
        authentik_sub="authentik-user-1",
        username="Ada",
        email="ada@example.com",
        status=UserStatus.ACTIVE,
    )

    async def override_current_user() -> CurrentUser:
        return current_user

    client.app.dependency_overrides[get_current_user] = override_current_user

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authentik_sub"] == "authentik-user-1"
    assert payload["username"] == "Ada"
    assert payload["email"] == "ada@example.com"
    assert payload["status"] == "ACTIVE"


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_csrf_issues_cookie_and_response_token(client: TestClient) -> None:
    response = client.get("/api/auth/csrf")

    assert response.status_code == 200
    assert response.json()["csrf_token"]
    assert "bitenary_csrf=" in response.headers["set-cookie"]


def test_refresh_rotates_access_cookie(client: TestClient) -> None:
    fake_auth = FakeAuthService(
        token_set=TokenSet(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            id_token=None,
            expires_in=900,
        )
    )
    client.app.dependency_overrides[get_auth_service] = lambda: fake_auth
    client.cookies.set("bitenary_csrf", "csrf-token")
    client.cookies.set(REFRESH_COOKIE_NAME, "old-refresh-token")

    response = client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-Token": "csrf-token"},
    )

    assert response.status_code == 204
    set_cookie = response.headers.get_list("set-cookie")
    assert any(f"{ACCESS_COOKIE_NAME}=new-access-token" in cookie for cookie in set_cookie)
    assert any(f"{REFRESH_COOKIE_NAME}=new-refresh-token" in cookie for cookie in set_cookie)


def test_refresh_rejects_missing_csrf(client: TestClient) -> None:
    client.cookies.set(REFRESH_COOKIE_NAME, "refresh-token")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 403


def test_logout_revokes_refresh_and_clears_cookies(client: TestClient) -> None:
    fake_auth = FakeAuthService(token_set=None)
    client.app.dependency_overrides[get_auth_service] = lambda: fake_auth
    client.cookies.set("bitenary_csrf", "csrf-token")
    client.cookies.set(REFRESH_COOKIE_NAME, "refresh-token")

    response = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": "csrf-token"},
    )

    assert response.status_code == 204
    assert fake_auth.revoked_token == "refresh-token"
    set_cookie = response.headers.get_list("set-cookie")
    assert any(f"{ACCESS_COOKIE_NAME}=" in cookie and "Max-Age=0" in cookie for cookie in set_cookie)
    assert any(f"{REFRESH_COOKIE_NAME}=" in cookie and "Max-Age=0" in cookie for cookie in set_cookie)
