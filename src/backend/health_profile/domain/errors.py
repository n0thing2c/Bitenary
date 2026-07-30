class HealthProfileError(Exception):
    """Base error for health-profile use cases."""


class InvalidHealthProfileError(HealthProfileError):
    """Raised when health-profile values violate domain rules."""


class HealthProfileOwnerNotFoundError(HealthProfileError):
    """Raised when the local user owning a profile cannot be found."""
