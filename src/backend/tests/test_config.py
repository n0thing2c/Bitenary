import pytest

from core.config import get_settings, parse_frontend_origins


def test_parse_frontend_origins_from_csv() -> None:
    assert parse_frontend_origins(
        "http://localhost:5173, https://app.example.com "
    ) == ["http://localhost:5173", "https://app.example.com"]


def test_parse_frontend_origins_from_json() -> None:
    assert parse_frontend_origins(
        '["http://localhost:5173", "https://app.example.com"]'
    ) == ["http://localhost:5173", "https://app.example.com"]


def test_parse_frontend_origins_rejects_non_list_json() -> None:
    with pytest.raises(ValueError):
        parse_frontend_origins('{"origin": "http://localhost:5173"}')


def test_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,https://app.example.com",
    )
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.environment == "test"
    assert settings.frontend_origin_list == [
        "http://localhost:5173",
        "https://app.example.com",
    ]

    get_settings.cache_clear()


def test_production_rejects_weak_mcp_token_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CSRF_SECRET", "c" * 32)
    monkeypatch.setenv("MCP_TOKEN_PEPPER", "replace-me")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="MCP_TOKEN_PEPPER"):
        get_settings()

    get_settings.cache_clear()


def test_production_rejects_weak_csrf_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CSRF_SECRET", "replace-me")
    monkeypatch.setenv("MCP_TOKEN_PEPPER", "m" * 32)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="CSRF_SECRET"):
        get_settings()

    get_settings.cache_clear()
