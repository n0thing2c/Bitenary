from identity.domain.entities import CurrentUser, UserStatus
from identity.domain.errors import AuthenticationError, DisabledUserError
from identity.infrastructure.jwt_verifier import JwtVerifier
from identity.repository.users import UserRepository


class CurrentUserService:
    def __init__(
        self,
        *,
        jwt_verifier: JwtVerifier,
        user_repository: UserRepository,
    ) -> None:
        self._jwt_verifier = jwt_verifier
        self._user_repository = user_repository

    async def from_access_token(self, access_token: str) -> CurrentUser:
        claims = await self._jwt_verifier.verify_access_token(access_token)
        authentik_sub = claims.get("sub")
        if not authentik_sub:
            raise AuthenticationError("Access token is missing subject")

        user = await self._user_repository.get_by_authentik_sub(str(authentik_sub))
        if user is None:
            raise AuthenticationError("Local user was not found")
        if user.status == UserStatus.DISABLED:
            raise DisabledUserError("Local user is disabled")

        return CurrentUser(
            user_id=user.user_id,
            authentik_sub=user.authentik_sub,
            username=user.username,
            email=user.email,
            status=user.status,
        )
