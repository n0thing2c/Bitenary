from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
import pytest

from core.csrf import CSRFMiddleware, create_csrf_token


CSRF_SECRET = "middleware-test-secret"


def create_probe_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, secret=CSRF_SECRET)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://frontend.example"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.api_route(
        "/api/probe",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "TRACE"],
    )
    async def api_probe(request: Request) -> dict[str, str]:
        return {"method": request.method}

    @app.post("/mcp")
    async def mcp_probe() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_unsafe_api_methods_require_csrf(method: str) -> None:
    with TestClient(create_probe_app()) as client:
        response = client.request(method, "/api/probe")

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid CSRF token"}


def test_signed_token_allows_unsafe_api_request() -> None:
    token = create_csrf_token(CSRF_SECRET)
    with TestClient(create_probe_app()) as client:
        client.cookies.set("bitenary_csrf", token)
        response = client.post(
            "/api/probe",
            headers={"X-CSRF-Token": token},
        )

    assert response.status_code == 200
    assert response.json() == {"method": "POST"}


@pytest.mark.parametrize("method", ["GET", "HEAD", "TRACE"])
def test_safe_api_methods_do_not_require_csrf(method: str) -> None:
    with TestClient(create_probe_app()) as client:
        response = client.request(method, "/api/probe")

    assert response.status_code == 200


def test_cors_preflight_is_not_blocked_and_keeps_cors_headers() -> None:
    with TestClient(create_probe_app()) as client:
        response = client.options(
            "/api/probe",
            headers={
                "Origin": "https://frontend.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-CSRF-Token",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://frontend.example"
    )


def test_mcp_post_is_outside_csrf_scope() -> None:
    with TestClient(create_probe_app()) as client:
        response = client.post("/mcp")

    assert response.status_code == 200
