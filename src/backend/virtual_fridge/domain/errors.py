class VirtualFridgeError(Exception):
    """Base error for Virtual Fridge use cases."""


class IngredientNotFoundError(VirtualFridgeError):
    """Raised when an ingredient master record does not exist."""


class FridgeItemNotFoundError(VirtualFridgeError):
    """Raised when an item does not exist or belongs to another user."""


class InvalidFridgeItemError(VirtualFridgeError):
    """Raised when item values violate domain rules."""


class NotificationNotFoundError(VirtualFridgeError):
    """Raised when a notification does not exist or belongs to another user."""


class InvalidNotificationSettingsError(VirtualFridgeError):
    """Raised when expiry notification settings are invalid."""
