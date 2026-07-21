from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

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
from identity.service.oidc_transaction import OidcTransaction, OidcTransactionService
from identity.wiring import get_auth_service, get_current_user, get_oidc_transaction_service


router = APIRouter(prefix="/auth", tags=["auth"])


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
    transactions: OidcTransactionService = Depends(get_oidc_transaction_service),
) -> RedirectResponse:
    transaction = transactions.create(return_to)
    return RedirectResponse(
        build_authorization_url(settings, transaction),
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        token_set = await auth_service.refresh(refresh_token)
    except AuthenticationError as exc:
        clear_auth_cookies(response, settings=settings)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        ) from exc

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


def frontend_redirect_url(settings: Settings, return_to: str) -> str:
    frontend_origin = settings.frontend_origin_list[0].rstrip("/")
    return f"{frontend_origin}{return_to}"
