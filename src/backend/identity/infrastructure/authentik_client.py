from dataclasses import dataclass
from typing import Any

import httpx

from core.config import Settings
from identity.domain.errors import AuthenticationError


# object contain response token from Authentik
@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    id_token: str | None
    expires_in: int | None


class AuthentikClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> "AuthentikClient":
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()

    # Exchange the authorization code returned by Authentik for OIDC tokens
    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenSet:
        return await self._request_token(
            {
                "grant_type": "authorization_code",
                "code": code, # authorization code from Authentik
                "redirect_uri": self._settings.oidc_redirect_uri,
                "code_verifier": code_verifier,
            }
        )

    # Obtain a new token set using a previously issued refresh token
    async def refresh(self, refresh_token: str) -> TokenSet:
        return await self._request_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )

    # Revoke a token at Authentik to invalidate the user's session access
    async def revoke(self, token: str) -> None:
        client = self._client()
        response = await client.post(
            self._settings.authentik_revoke_url,
            data={
                "client_id": self._settings.authentik_client_id,
                "client_secret": self._settings.authentik_client_secret,
                "token": token,
            },
        )
        if response.status_code >= 400:
            raise AuthenticationError("Could not revoke refresh token")

    # Retrieve user claims from Authentik using an access token
    async def userinfo(self, access_token: str) -> dict[str, Any]:
        client = self._client()
        response = await client.get(
            self._settings.authentik_userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise AuthenticationError("Could not load userinfo")
        return response.json()

    # Send a token request to Authentik and return a TokenSet
    async def _request_token(self, data: dict[str, str]) -> TokenSet:
        client = self._client()
        response = await client.post(
            self._settings.authentik_token_url,
            data={
                "client_id": self._settings.authentik_client_id,
                "client_secret": self._settings.authentik_client_secret,
                **data,
            },
        )
        if response.status_code >= 400:
            raise AuthenticationError("Could not exchange token")
        payload = response.json()
        try:
            access_token = str(payload["access_token"])
        except KeyError as exc:
            raise AuthenticationError("Token response is missing access_token") from exc

        refresh_token = payload.get("refresh_token")
        id_token = payload.get("id_token")
        expires_in = payload.get("expires_in")
        return TokenSet(
            access_token=access_token,
            refresh_token=str(refresh_token) if refresh_token else None,
            id_token=str(id_token) if id_token else None,
            expires_in=int(expires_in) if expires_in is not None else None,
        )

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            raise RuntimeError("AuthentikClient must be used as an async context manager")
        return self._http_client
