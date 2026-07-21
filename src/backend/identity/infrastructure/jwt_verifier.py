from typing import Any
import json

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from core.config import Settings
from identity.domain.errors import AuthenticationError


class JwtVerifier:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._jwks: dict[str, Any] | None = None

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid access token") from exc

        if header.get("alg") != "RS256":
            raise AuthenticationError("Unsupported JWT algorithm")

        key = await self._get_signing_key(header.get("kid"))
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self._settings.authentik_client_id,
                issuer=self._settings.authentik_issuer,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid access token") from exc

        return claims

    # Find key in jwks that match kid in jwt header
    async def _get_signing_key(self, kid: str | None) -> Any:
        jwks = await self._load_jwks()
        keys = jwks.get("keys", [])
        key_data = None

        if kid:
            key_data = next((key for key in keys if key.get("kid") == kid), None)
        elif len(keys) == 1:
            key_data = keys[0]

        # Reload jwks because Authentik may rotate key
        if key_data is None:
            self._jwks = None
            jwks = await self._load_jwks()
            keys = jwks.get("keys", [])
            if kid:
                key_data = next((key for key in keys if key.get("kid") == kid), None)
            elif len(keys) == 1:
                key_data = keys[0]

        if key_data is None:
            raise AuthenticationError("JWT signing key not found")

        return RSAAlgorithm.from_jwk(json.dumps(key_data))

    async def _load_jwks(self) -> dict[str, Any]:
        if self._jwks is not None:
            return self._jwks

        if self._http_client is None:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self._settings.authentik_jwks_url)
        else:
            response = await self._http_client.get(self._settings.authentik_jwks_url)

        if response.status_code >= 400:
            raise AuthenticationError("Could not load JWKS")

        self._jwks = response.json()
        return self._jwks
