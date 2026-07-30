class MCPError(Exception):
    """Base error for the Bitenary MCP feature."""


class MCPConnectionNotFoundError(MCPError):
    """Raised when an owned MCP connection cannot be found."""


class DuplicateTokenPrefixError(MCPError):
    """Raised when generated token lookup material collides."""


class MCPAuditUnavailableError(MCPError):
    """Raised when an invocation cannot be recorded before execution."""


class ExternalServiceError(MCPError):
    """Raised when a third-party service (e.g. Spoonacular) returns an
    error or an unrecognised response during a tool invocation."""
