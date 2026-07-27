# Bitenary Documentation

Detailed setup, architecture, authentication, and testing guides for Bitenary.
Start with the [project README](../README.md) for the product overview and
quick start.

## Guides

| Guide | Audience | Covers |
| --- | --- | --- |
| [Backend development](backend-development.md) | Backend developers | Environment setup, local services, migrations, tests and troubleshooting |
| [Web authentication](web-authentication.md) | Backend and identity developers | Authentik OIDC setup, cookies, CSRF and manual verification |
| [MCP authentication](mcp-authentication.md) | MCP and integration developers | Personal tokens, client configuration, status-tool testing and audit logs |

## Suggested reading order

1. [Project overview and quick start](../README.md)
2. [Backend development](backend-development.md)
3. [Web authentication](web-authentication.md)
4. [MCP authentication](mcp-authentication.md)

## Documentation conventions

- Commands target Windows PowerShell unless a block states otherwise.
- Paths are relative to the repository root.
- Placeholder secrets use angle brackets and must never be committed.
- Local HTTP settings are for development only; production requires HTTPS and
  secure cookies.

