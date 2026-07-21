class IdentityError(Exception):
    """Base error for identity use cases."""


class AuthenticationError(IdentityError):
    """Raised when credentials or OIDC state are invalid."""


class DisabledUserError(IdentityError):
    """Raised when a valid Authentik identity maps to a disabled local user."""
