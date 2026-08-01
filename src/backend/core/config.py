from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def parse_frontend_origins(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []

    # Accept JSON arrays for deploy configs and CSV for simple local .env files.
    if cleaned.startswith("[") or cleaned.startswith("{"):
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            raise ValueError("FRONTEND_ORIGINS JSON value must be a list")
        return [str(origin).strip() for origin in parsed if str(origin).strip()]

    return [origin.strip() for origin in cleaned.split(",") if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str
    service_name: str
    environment: str
    # Avoid the common DEBUG env var because some shells/tools use it for log levels.
    app_debug: bool
    log_level: str

    database_url: str
    sql_echo: bool

    frontend_origins: str
    backend_public_url: str

    cookie_secure: bool
    cookie_samesite: Literal["lax", "strict", "none"]

    authentik_client_id: str
    authentik_client_secret: str
    authentik_issuer: str
    authentik_authorize_url: str
    authentik_enrollment_url: str
    authentik_token_url: str
    authentik_userinfo_url: str
    authentik_revoke_url: str
    authentik_jwks_url: str
    authentik_end_session_url: str

    oidc_redirect_uri: str
    oidc_scope: str
    oidc_state_secret: str
    csrf_secret: str
    mcp_token_pepper: str
    mcp_token_ttl_days: int = Field(default=90, ge=1, le=3650)

    spoonacular_api_key: str
    google_api_key: str
    redis_url: str = Field(default="redis://localhost:6379")

    @property
    def frontend_origin_list(self) -> list[str]:
        return parse_frontend_origins(self.frontend_origins)

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment.lower() == "production" and (
            self.mcp_token_pepper == "replace-me"
            or len(self.mcp_token_pepper) < 32
        ):
            raise ValueError(
                "MCP_TOKEN_PEPPER must contain at least 32 characters in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
