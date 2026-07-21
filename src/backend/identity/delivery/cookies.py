from fastapi import Response

from core.config import Settings
from core.csrf import CSRF_COOKIE_NAME
from core.security import generate_urlsafe_token
from identity.infrastructure.authentik_client import TokenSet


ACCESS_COOKIE_NAME = "bitenary_access"
REFRESH_COOKIE_NAME = "bitenary_refresh"
REFRESH_COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def set_auth_cookies(
    response: Response,
    *,
    token_set: TokenSet,
    settings: Settings,
    fallback_refresh_token: str | None = None,
) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token_set.access_token,
        max_age=token_set.expires_in,
        path="/api",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )

    refresh_token = token_set.refresh_token or fallback_refresh_token
    if refresh_token:
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            max_age=REFRESH_COOKIE_MAX_AGE_SECONDS,
            path="/api/auth",
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
        )


def set_csrf_cookie(response: Response, *, settings: Settings, token: str | None) -> str:
    csrf_token = token or generate_urlsafe_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return csrf_token


def clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        ACCESS_COOKIE_NAME,
        path="/api",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=True,
    )
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path="/api/auth",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=True,
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=False,
    )
