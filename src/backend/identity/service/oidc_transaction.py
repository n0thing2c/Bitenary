from dataclasses import dataclass
from urllib.parse import urlsplit

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.security import create_pkce_challenge, generate_pkce_verifier
from identity.domain.errors import AuthenticationError


OIDC_TRANSACTION_MAX_AGE_SECONDS = 300

# object contain data of a login session
@dataclass(frozen=True)
class OidcTransaction:
    state: str
    nonce: str # number used once
    code_verifier: str
    code_challenge: str
    return_to: str


class OidcTransactionService:
    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="bitenary-oidc-state",
        )

    # Create a signed OIDC transaction before redirect to Authentik
    def create(self, return_to: str | None) -> OidcTransaction:
        safe_return_to = validate_return_to(return_to)
        nonce = generate_pkce_verifier()
        code_verifier = generate_pkce_verifier()
        state = self._serializer.dumps(
            {
                "nonce": nonce,
                "code_verifier": code_verifier,
                "return_to": safe_return_to,
            }
        )
        return OidcTransaction(
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            code_challenge=create_pkce_challenge(code_verifier),
            return_to=safe_return_to,
        )

    # Restore and validate the OIDC transaction from the callback state
    def load(self, state: str) -> OidcTransaction:
        try:
            payload = self._serializer.loads(
                state,
                max_age=OIDC_TRANSACTION_MAX_AGE_SECONDS,
            )
        except (BadSignature, SignatureExpired) as exc:
            raise AuthenticationError("Invalid OIDC state") from exc

        try:
            nonce = str(payload["nonce"])
            code_verifier = str(payload["code_verifier"])
            return_to = validate_return_to(str(payload["return_to"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Invalid OIDC state payload") from exc

        return OidcTransaction(
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            code_challenge=create_pkce_challenge(code_verifier),
            return_to=return_to,
        )


# Only allow relative paths to prevent open redirect attacks.
def validate_return_to(return_to: str | None) -> str:
    if not return_to:
        return "/"

    parsed = urlsplit(return_to)
    if parsed.scheme or parsed.netloc or not return_to.startswith("/"):
        return "/"
    if return_to.startswith("//") or "\\" in return_to:
        return "/"
    return return_to
