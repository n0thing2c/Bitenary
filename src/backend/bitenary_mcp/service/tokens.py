import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from uuid import UUID

from core.security import constant_time_equal


TOKEN_PREFIX_MARKER = "bty_mcp_"
TOKEN_LOOKUP_HEX_LENGTH = 8
TOKEN_PATTERN = re.compile(
    rf"^(?P<prefix>{TOKEN_PREFIX_MARKER}[0-9a-f]{{{TOKEN_LOOKUP_HEX_LENGTH}}})"
    r"\.(?P<secret>[A-Za-z0-9_-]{43,})$"
)

# Internal token prefix used by the Orchestrator when it calls its own MCP server.
# These tokens are verified purely via HMAC and never touch the database.
_INTERNAL_PREFIX = "internal_"


class MCPTokenCodec:
    def __init__(
        self,
        pepper: str,
        *,
        lookup_factory: Callable[[], str] | None = None,
        secret_factory: Callable[[], str] | None = None,
    ) -> None:
        if not pepper:
            raise ValueError("MCP token pepper must not be empty")
        self._pepper = pepper.encode("utf-8")
        self._lookup_factory = lookup_factory or (lambda: secrets.token_hex(4))
        self._secret_factory = secret_factory or (lambda: secrets.token_urlsafe(32))

    def generate(self) -> tuple[str, str, str]:
        lookup = self._lookup_factory()
        if not re.fullmatch(r"[0-9a-f]{8}", lookup):
            raise ValueError("MCP token lookup prefix must be eight lowercase hex characters")
        secret = self._secret_factory()
        if len(secret) < 43:
            raise ValueError("MCP token secret must contain at least 32 random bytes")

        token_prefix = f"{TOKEN_PREFIX_MARKER}{lookup}"
        plaintext = f"{token_prefix}.{secret}"
        return plaintext, token_prefix, self.digest(plaintext)

    def parse_prefix(self, token: str) -> str | None:
        match = TOKEN_PATTERN.fullmatch(token)
        if match is None:
            return None
        return match.group("prefix")

    def digest(self, token: str) -> str:
        return hmac.new(
            self._pepper,
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def matches(self, token: str, expected_digest: str) -> bool:
        return constant_time_equal(self.digest(token), expected_digest)

    # ------------------------------------------------------------------
    # Internal token — used by the Orchestrator to authenticate itself
    # to the MCP server without touching the database.
    #
    # Format:  internal_<user_id>.<hmac-sha256-hex>
    # The HMAC is keyed with the same pepper as regular tokens.
    # ------------------------------------------------------------------

    def generate_internal_token(self, user_id: UUID) -> str:
        """Create a short-lived internal Bearer token for the Orchestrator.

        The token is signed with the server's ``mcp_token_pepper`` so it
        cannot be forged by anyone who does not know the secret.  It is
        intended only for in-process / loopback use between the Orchestrator
        and the MCP server mounted on the same FastAPI instance.
        """
        payload = f"{_INTERNAL_PREFIX}{user_id}"
        signature = hmac.new(
            self._pepper,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{signature}"

    def verify_internal_token(self, token: str) -> UUID | None:
        """Return the ``user_id`` embedded in an internal token if valid.

        Returns ``None`` if the token is malformed, has been tampered with,
        or does not carry the ``internal_`` prefix.
        """
        if not token.startswith(_INTERNAL_PREFIX):
            return None
        # Expected structure: internal_<uuid>.<64-char hex>
        try:
            prefix_and_id, signature = token.rsplit(".", 1)
        except ValueError:
            return None
        if len(signature) != 64:  # sha256 hex = 64 chars
            return None
        expected_sig = hmac.new(
            self._pepper,
            prefix_and_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not constant_time_equal(signature, expected_sig):
            return None
        user_id_str = prefix_and_id.removeprefix(_INTERNAL_PREFIX)
        try:
            return UUID(user_id_str)
        except ValueError:
            return None
