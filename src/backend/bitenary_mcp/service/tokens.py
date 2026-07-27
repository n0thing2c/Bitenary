import hashlib
import hmac
import re
import secrets
from collections.abc import Callable

from core.security import constant_time_equal


TOKEN_PREFIX_MARKER = "bty_mcp_"
TOKEN_LOOKUP_HEX_LENGTH = 8
TOKEN_PATTERN = re.compile(
    rf"^(?P<prefix>{TOKEN_PREFIX_MARKER}[0-9a-f]{{{TOKEN_LOOKUP_HEX_LENGTH}}})"
    r"\.(?P<secret>[A-Za-z0-9_-]{43,})$"
)


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
