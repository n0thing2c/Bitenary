from pathlib import Path
import os
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Enable asyncio mode for all async test functions globally.
# This removes the need to mark every async test with @pytest.mark.asyncio.
import pytest
from fastapi.testclient import TestClient

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


TEST_ENV = {
    "APP_NAME": "Bitenary API",
    "SERVICE_NAME": "bitenary-api",
    "ENVIRONMENT": "test",
    "APP_DEBUG": "false",
    "LOG_LEVEL": "INFO",
    "DATABASE_URL": "postgresql+asyncpg://bitenary:bitenary@localhost:5433/bitenary",
    "SQL_ECHO": "false",
    "FRONTEND_ORIGINS": "http://localhost:5173",
    "BACKEND_PUBLIC_URL": "http://localhost:8000",
    "COOKIE_SECURE": "false",
    "COOKIE_SAMESITE": "lax",
    "AUTHENTIK_CLIENT_ID": "test-client-id",
    "AUTHENTIK_CLIENT_SECRET": "test-client-secret",
    "AUTHENTIK_ISSUER": "http://localhost:9000/application/o/bitenary/",
    "AUTHENTIK_AUTHORIZE_URL": "http://localhost:9000/application/o/authorize/",
    "AUTHENTIK_ENROLLMENT_URL": "http://localhost:9000/if/flow/default-enrollment-flow/",
    "AUTHENTIK_TOKEN_URL": "http://localhost:9000/application/o/token/",
    "AUTHENTIK_USERINFO_URL": "http://localhost:9000/application/o/userinfo/",
    "AUTHENTIK_REVOKE_URL": "http://localhost:9000/application/o/revoke/",
    "AUTHENTIK_JWKS_URL": "http://localhost:9000/application/o/bitenary/jwks/",
    "AUTHENTIK_END_SESSION_URL": (
        "http://localhost:9000/application/o/bitenary/end-session/"
    ),
    "AUTHENTIK_USER_SETTINGS_URL": "http://localhost:9000/if/user/#/settings",
    "OIDC_REDIRECT_URI": "http://localhost:8000/api/auth/callback",
    "OIDC_SCOPE": "openid profile email offline_access",
    "OIDC_STATE_SECRET": "test-oidc-state-secret",
    "CSRF_SECRET": "test-csrf-secret",
    "MCP_TOKEN_PEPPER": "test-mcp-token-pepper",
    "SPOONACULAR_API_KEY": "test-spoonacular-key",
    "GOOGLE_API_KEY": "test-google-key",
    "REDIS_URL": "redis://localhost:6379",
}


for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)


def csrf_headers(client: TestClient) -> dict[str, str]:
    """Issue a signed token through the same endpoint used by the frontend."""
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    return {"X-CSRF-Token": token}
