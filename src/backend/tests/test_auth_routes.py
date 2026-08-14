from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import csrf_headers
from app.main import create_app
from core.csrf import CSRF_COOKIE_NAME, csrf_token_is_valid
from core.config import get_settings
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
    assert csrf_token_is_valid(
        response.cookies.get(CSRF_COOKIE_NAME),
        get_settings().csrf_secret,
    )


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
    assert csrf_token_is_valid(
        response.json()["csrf_token"],
        get_settings().csrf_secret,
    )
    assert "bitenary_csrf=" in response.headers["set-cookie"]


def test_csrf_replaces_legacy_unsigned_cookie(client: TestClient) -> None:
    client.cookies.set(CSRF_COOKIE_NAME, "legacy-unsigned-token")

    response = client.get("/api/auth/csrf")

    token = response.json()["csrf_token"]
    assert response.status_code == 200
    assert token != "legacy-unsigned-token"
    assert csrf_token_is_valid(token, get_settings().csrf_secret)


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
    client.cookies.set(REFRESH_COOKIE_NAME, "old-refresh-token")

    headers = csrf_headers(client)
    csrf_token = headers["X-CSRF-Token"]
    response = client.post(
        "/api/auth/refresh",
        headers=headers,
    )

    assert response.status_code == 204
    set_cookie = response.headers.get_list("set-cookie")
    assert any(f"{ACCESS_COOKIE_NAME}=new-access-token" in cookie for cookie in set_cookie)
    assert any(f"{REFRESH_COOKIE_NAME}=new-refresh-token" in cookie for cookie in set_cookie)
    assert client.cookies.get(CSRF_COOKIE_NAME) == csrf_token


def test_refresh_rejects_missing_csrf(client: TestClient) -> None:
    client.cookies.set(REFRESH_COOKIE_NAME, "refresh-token")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 403


def test_refresh_without_refresh_cookie_clears_auth_cookies(
    client: TestClient,
) -> None:
    client.cookies.set(ACCESS_COOKIE_NAME, "stale-access-token")

    response = client.post(
        "/api/auth/refresh",
        headers=csrf_headers(client),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert_cookies_cleared(response)


def test_refresh_failure_clears_auth_cookies(client: TestClient) -> None:
    fake_auth = FakeAuthService(token_set=None)
    client.app.dependency_overrides[get_auth_service] = lambda: fake_auth
    client.cookies.set(ACCESS_COOKIE_NAME, "stale-access-token")
    client.cookies.set(REFRESH_COOKIE_NAME, "invalid-refresh-token")

    response = client.post(
        "/api/auth/refresh",
        headers=csrf_headers(client),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert_cookies_cleared(response)


def test_logout_revokes_refresh_and_clears_cookies(client: TestClient) -> None:
    fake_auth = FakeAuthService(token_set=None)
    client.app.dependency_overrides[get_auth_service] = lambda: fake_auth
    client.cookies.set(REFRESH_COOKIE_NAME, "refresh-token")

    response = client.post(
        "/api/auth/logout",
        headers=csrf_headers(client),
    )

    assert response.status_code == 204
    assert fake_auth.revoked_token == "refresh-token"
    set_cookie = response.headers.get_list("set-cookie")
    assert any(f"{ACCESS_COOKIE_NAME}=" in cookie and "Max-Age=0" in cookie for cookie in set_cookie)
    assert any(f"{REFRESH_COOKIE_NAME}=" in cookie and "Max-Age=0" in cookie for cookie in set_cookie)


def assert_cookies_cleared(response) -> None:
    set_cookie = response.headers.get_list("set-cookie")
    for cookie_name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        assert any(
            f"{cookie_name}=" in cookie and "Max-Age=0" in cookie
            for cookie in set_cookie
        )
