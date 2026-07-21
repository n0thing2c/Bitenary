from datetime import UTC, datetime, timedelta
import json

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
import pytest

from core.config import get_settings
from identity.domain.errors import AuthenticationError
from identity.infrastructure.jwt_verifier import JwtVerifier


def make_key_pair() -> tuple[object, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "test-key"
    return private_key, public_jwk


def make_access_token(
    private_key: object,
    *,
    issuer: str = "http://localhost:9000/application/o/bitenary/",
    audience: str = "test-client-id",
    algorithm: str = "RS256",
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "authentik-user-1",
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    key = private_key if algorithm == "RS256" else "shared-secret"
    return jwt.encode(
        payload,
        key,
        algorithm=algorithm,
        headers={"kid": "test-key"},
    )


def make_jwks_client(jwk: dict[str, object]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_jwt_verifier_accepts_valid_authentik_access_token() -> None:
    private_key, jwk = make_key_pair()
    token = make_access_token(private_key)
    async with make_jwks_client(jwk) as http_client:
        verifier = JwtVerifier(get_settings(), http_client=http_client)

        claims = await verifier.verify_access_token(token)

    assert claims["sub"] == "authentik-user-1"


@pytest.mark.anyio
async def test_jwt_verifier_rejects_wrong_issuer() -> None:
    private_key, jwk = make_key_pair()
    token = make_access_token(private_key, issuer="http://issuer.example.com/")
    async with make_jwks_client(jwk) as http_client:
        verifier = JwtVerifier(get_settings(), http_client=http_client)

        with pytest.raises(AuthenticationError):
            await verifier.verify_access_token(token)


@pytest.mark.anyio
async def test_jwt_verifier_rejects_wrong_audience() -> None:
    private_key, jwk = make_key_pair()
    token = make_access_token(private_key, audience="other-client-id")
    async with make_jwks_client(jwk) as http_client:
        verifier = JwtVerifier(get_settings(), http_client=http_client)

        with pytest.raises(AuthenticationError):
            await verifier.verify_access_token(token)


@pytest.mark.anyio
async def test_jwt_verifier_rejects_non_rs256_algorithm() -> None:
    _private_key, jwk = make_key_pair()
    token = make_access_token("shared-secret", algorithm="HS256")
    async with make_jwks_client(jwk) as http_client:
        verifier = JwtVerifier(get_settings(), http_client=http_client)

        with pytest.raises(AuthenticationError):
            await verifier.verify_access_token(token)
