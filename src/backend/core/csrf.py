import base64
import hashlib
import hmac

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from core.security import constant_time_equal, generate_urlsafe_token


CSRF_COOKIE_NAME = "bitenary_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_VERSION = "v1"
SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_TOKEN_PART_LENGTH = 43


def create_csrf_token(secret: str) -> str:
    """Create an opaque, versioned CSRF token authenticated with HMAC-SHA256."""
    if not secret:
        raise ValueError("CSRF secret must not be empty")
    nonce = generate_urlsafe_token()
    unsigned_token = f"{CSRF_TOKEN_VERSION}.{nonce}"
    signature = _sign(unsigned_token, secret)
    return f"{unsigned_token}.{signature}"


def csrf_token_is_valid(token: str | None, secret: str) -> bool:
    if not token or not secret:
        return False

    parts = token.split(".")
    if len(parts) != 3:
        return False
    version, nonce, signature = parts
    if version != CSRF_TOKEN_VERSION:
        return False
    if not _is_urlsafe_token_part(nonce) or not _is_urlsafe_token_part(signature):
        return False

    expected_signature = _sign(f"{version}.{nonce}", secret)
    return constant_time_equal(signature, expected_signature)


def csrf_tokens_match(
    cookie_token: str | None,
    header_token: str | None,
    secret: str,
) -> bool:
    if not cookie_token or not header_token:
        return False
    if not constant_time_equal(cookie_token, header_token):
        return False
    return csrf_token_is_valid(cookie_token, secret)


class CSRFMiddleware:
    """Enforce CSRF validation centrally for unsafe REST API requests."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        secret: str,
        protected_prefix: str = "/api",
    ) -> None:
        self.app = app
        self.secret = secret
        self.protected_prefix = protected_prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._requires_csrf(scope):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if not csrf_tokens_match(
            request.cookies.get(CSRF_COOKIE_NAME),
            request.headers.get(CSRF_HEADER_NAME),
            self.secret,
        ):
            response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid CSRF token"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _requires_csrf(self, scope: Scope) -> bool:
        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        is_protected_path = path == self.protected_prefix or path.startswith(
            f"{self.protected_prefix}/"
        )
        return is_protected_path and method not in SAFE_HTTP_METHODS


def _sign(unsigned_token: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        unsigned_token.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _is_urlsafe_token_part(value: str) -> bool:
    return len(value) == _TOKEN_PART_LENGTH and all(
        character.isascii() and (character.isalnum() or character in "-_")
        for character in value
    )
