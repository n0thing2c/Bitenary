import base64
import hashlib
import hmac
import secrets


def generate_urlsafe_token(byte_length: int = 32) -> str:
    if byte_length < 32:
        raise ValueError("byte_length must be at least 32")
    return secrets.token_urlsafe(byte_length)


def generate_pkce_verifier() -> str:
    return generate_urlsafe_token(64)


def create_pkce_challenge(verifier: str) -> str:
    # Authentik supports S256, which is the PKCE method used by the OIDC flow.
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
