from collections.abc import AsyncIterator
import logging

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from core.database import get_db_session
from identity.delivery.cookies import ACCESS_COOKIE_NAME
from identity.domain.entities import CurrentUser
from identity.domain.errors import AuthenticationError, DisabledUserError
from identity.infrastructure.authentik_client import AuthentikClient
from identity.infrastructure.jwt_verifier import JwtVerifier
from identity.infrastructure.sqlalchemy_users import SqlAlchemyUserRepository
from identity.repository.users import UserRepository
from identity.service.auth_service import AuthService
from identity.service.current_user import CurrentUserService
from identity.service.oidc_transaction import OidcTransactionService


logger = logging.getLogger(__name__)


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_oidc_transaction_service(
    settings: Settings = Depends(get_settings),
) -> OidcTransactionService:
    return OidcTransactionService(settings.oidc_state_secret)


def get_jwt_verifier(settings: Settings = Depends(get_settings)) -> JwtVerifier:
    return JwtVerifier(settings)


async def get_authentik_client(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[AuthentikClient]:
    async with AuthentikClient(settings) as client:
        yield client


def get_auth_service(
    authentik_client: AuthentikClient = Depends(get_authentik_client),
    jwt_verifier: JwtVerifier = Depends(get_jwt_verifier),
    user_repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(
        authentik_client=authentik_client,
        jwt_verifier=jwt_verifier,
        user_repository=user_repository,
    )


def get_current_user_service(
    jwt_verifier: JwtVerifier = Depends(get_jwt_verifier),
    user_repository: UserRepository = Depends(get_user_repository),
) -> CurrentUserService:
    return CurrentUserService(
        jwt_verifier=jwt_verifier,
        user_repository=user_repository,
    )


async def get_current_user(
    request: Request,
    service: CurrentUserService = Depends(get_current_user_service),
) -> CurrentUser:
    access_token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not access_token:
        logger.info(
            "Authentication rejected: access cookie missing path=%s",
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        return await service.from_access_token(access_token)
    except DisabledUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        ) from exc
    except AuthenticationError as exc:
        logger.info(
            "Authentication rejected: access token or local user invalid path=%s",
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        ) from exc
