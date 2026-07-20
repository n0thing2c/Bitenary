from fastapi import HTTPException, Request, status

from core.security import constant_time_equal


CSRF_COOKIE_NAME = "bitenary_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def csrf_tokens_match(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    # Use constant-time comparison so token checks do not leak timing clues.
    return constant_time_equal(cookie_token, header_token)


def verify_csrf_token(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_tokens_match(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )
