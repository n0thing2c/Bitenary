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
        if not token_set.id_token:
            raise AuthenticationError("Token response is missing ID token")

        id_token_claims = await self._jwt_verifier.verify_id_token(
            token_set.id_token,
            expected_nonce=transaction.nonce,
        )
        id_token_subject = _required_subject(id_token_claims, "ID token")

        access_token_claims = await self._jwt_verifier.verify_access_token(
            token_set.access_token
        )
        access_token_subject = _required_subject(access_token_claims, "Access token")
        if access_token_subject != id_token_subject:
            raise AuthenticationError("OIDC token subjects do not match")

        profile = await self._profile_from_claims_or_userinfo(
            {**access_token_claims, **id_token_claims},
            token_set.access_token,
            expected_subject=id_token_subject,
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
        *,
        expected_subject: str,
    ) -> dict[str, str | None]:
        profile = extract_profile(claims)
        if profile["username"] and profile["authentik_sub"] and profile["email"]:
            return profile

        userinfo = await self._authentik_client.userinfo(access_token)
        if not isinstance(userinfo, dict):
            raise AuthenticationError("Invalid UserInfo response")
        if userinfo.get("sub") != expected_subject:
            raise AuthenticationError("UserInfo subject does not match ID token")

        merged = {**claims, **userinfo, "sub": expected_subject}
        return extract_profile(merged)


def _required_subject(claims: dict[str, Any], token_name: str) -> str:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthenticationError(f"{token_name} is missing subject")
    return subject


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
