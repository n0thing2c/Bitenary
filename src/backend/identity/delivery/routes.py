import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from core.config import Settings, get_settings
from core.csrf import CSRF_COOKIE_NAME, verify_csrf_token
from identity.delivery.cookies import (
    REFRESH_COOKIE_NAME,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from identity.delivery.dto import CsrfResponse, CurrentUserResponse
from identity.domain.entities import CurrentUser
from identity.domain.errors import AuthenticationError
from identity.service.auth_service import AuthService
from identity.service.oidc_transaction import (
    OidcTransaction,
    OidcTransactionService,
    validate_return_to,
)
from identity.wiring import get_auth_service, get_current_user, get_oidc_transaction_service


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.get("/login")
def login(
    return_to: str | None = None,
    settings: Settings = Depends(get_settings),
    transactions: OidcTransactionService = Depends(get_oidc_transaction_service),
) -> RedirectResponse:
    transaction = transactions.create(return_to)
    return RedirectResponse(
        build_authorization_url(settings, transaction),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/signup")
def signup(
    return_to: str | None = None,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    return RedirectResponse(
        build_signup_url(settings, return_to),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    settings: Settings = Depends(get_settings),
    transactions: OidcTransactionService = Depends(get_oidc_transaction_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC callback",
        )

    try:
        transaction = transactions.load(state)
        token_set, _user = await auth_service.complete_callback(
            code=code,
            transaction=transaction,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC callback",
        ) from exc

    response = RedirectResponse(
        frontend_redirect_url(settings, transaction.return_to),
        status_code=status.HTTP_302_FOUND,
    )
    set_auth_cookies(response, token_set=token_set, settings=settings)
    set_csrf_cookie(response, settings=settings, token=None)
    return response


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    response.status_code = status.HTTP_204_NO_CONTENT
    verify_csrf_token(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        logger.info("Session refresh rejected: refresh cookie missing")
        return cleared_unauthorized_response(settings)

    try:
        token_set = await auth_service.refresh(refresh_token)
    except AuthenticationError:
        logger.info("Session refresh rejected: refresh token invalid")
        return cleared_unauthorized_response(settings)

    set_auth_cookies(
        response,
        token_set=token_set,
        settings=settings,
        fallback_refresh_token=refresh_token,
    )
    set_csrf_cookie(
        response,
        settings=settings,
        token=request.cookies.get(CSRF_COOKIE_NAME),
    )
    return response


def cleared_unauthorized_response(settings: Settings) -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Not authenticated"},
    )
    clear_auth_cookies(response, settings=settings)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    response.status_code = status.HTTP_204_NO_CONTENT
    verify_csrf_token(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    try:
        await auth_service.logout(refresh_token)
    except AuthenticationError:
        pass
    clear_auth_cookies(response, settings=settings)
    return response


@router.get("/csrf", response_model=CsrfResponse)
def csrf(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> CsrfResponse:
    csrf_token = set_csrf_cookie(
        response,
        settings=settings,
        token=request.cookies.get(CSRF_COOKIE_NAME),
    )
    return CsrfResponse(csrf_token=csrf_token)


def build_authorization_url(settings: Settings, transaction: OidcTransaction) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.authentik_client_id,
            "redirect_uri": settings.oidc_redirect_uri,
            "scope": settings.oidc_scope,
            "state": transaction.state,
            "nonce": transaction.nonce,
            "code_challenge": transaction.code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{settings.authentik_authorize_url}?{query}"


def build_signup_url(settings: Settings, return_to: str | None) -> str:
    safe_return_to = validate_return_to(return_to)
    next_url = append_query_params(
        f"{settings.backend_public_url.rstrip('/')}/api/auth/login",
        {"return_to": safe_return_to},
    )
    return append_query_params(settings.authentik_enrollment_url, {"next": next_url})


def append_query_params(url: str, params: dict[str, str]) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(params.items())
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def frontend_redirect_url(settings: Settings, return_to: str) -> str:
    frontend_origin = settings.frontend_origin_list[0].rstrip("/")
    return f"{frontend_origin}{return_to}"
