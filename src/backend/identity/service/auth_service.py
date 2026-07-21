from typing import Any

from identity.domain.entities import User
from identity.domain.errors import AuthenticationError
from identity.infrastructure.authentik_client import AuthentikClient, TokenSet
from identity.infrastructure.jwt_verifier import JwtVerifier
from identity.repository.users import UserRepository
from identity.service.oidc_transaction import OidcTransaction


class AuthService:
    def __init__(
        self,
        *,
        authentik_client: AuthentikClient,
        jwt_verifier: JwtVerifier,
        user_repository: UserRepository,
    ) -> None:
        self._authentik_client = authentik_client
        self._jwt_verifier = jwt_verifier
        self._user_repository = user_repository

    async def complete_callback(
        self,
        *,
        code: str,
        transaction: OidcTransaction,
    ) -> tuple[TokenSet, User]:
        token_set = await self._authentik_client.exchange_code(
            code=code,
            code_verifier=transaction.code_verifier,
        )
        claims = await self._jwt_verifier.verify_access_token(token_set.access_token)
        if claims.get("nonce") and claims.get("nonce") != transaction.nonce:
            raise AuthenticationError("Invalid OIDC nonce")

        profile = await self._profile_from_claims_or_userinfo(
            claims,
            token_set.access_token,
        )
        user = await self._user_repository.upsert_from_authentik_claims(**profile)
        return token_set, user

    async def refresh(self, refresh_token: str) -> TokenSet:
        return await self._authentik_client.refresh(refresh_token)

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        await self._authentik_client.revoke(refresh_token)

    async def _profile_from_claims_or_userinfo(
        self,
        claims: dict[str, Any],
        access_token: str,
    ) -> dict[str, str | None]:
        profile = extract_profile(claims)
        if profile["username"] and profile["authentik_sub"] and profile["email"]:
            return profile

        userinfo = await self._authentik_client.userinfo(access_token)
        merged = {**claims, **userinfo}
        return extract_profile(merged)


def extract_profile(claims: dict[str, Any]) -> dict[str, str | None]:
    authentik_sub = claims.get("sub")
    if not authentik_sub:
        raise AuthenticationError("Access token is missing subject")

    email = claims.get("email")
    username = (
        claims.get("preferred_username")
        or claims.get("name")
        or claims.get("nickname")
        or (str(email).split("@", maxsplit=1)[0] if email else None)
        or authentik_sub
    )

    return {
        "authentik_sub": str(authentik_sub),
        "username": str(username),
        "email": str(email) if email else None,
    }
