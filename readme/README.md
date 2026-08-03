# Bitenary Documentation

Detailed setup, architecture, authentication, and testing guides for Bitenary.
Start with the [project README](../README.md) for the product overview and
quick start.

## Guides

| Guide | Audience | Covers |
| --- | --- | --- |
| [Backend development](backend-development.md) | Backend developers | Environment setup, local services, migrations, tests and troubleshooting |
| [Backend Health Profile](backend-health-profile.md) | Backend developers | File responsibilities, architecture, data flow, API and persistence of Health Profile |
| [Backend Virtual Fridge](backend-virtual-fridge.md) | Backend developers | CRUD, expiry status, notifications, migrations and test instructions |
| [Web authentication](web-authentication.md) | Backend and identity developers | Authentik OIDC setup, cookies, CSRF and manual verification |
| [MCP authentication](mcp-authentication.md) | MCP and integration developers | Personal tokens, client configuration, status-tool testing and audit logs |

## Suggested reading order

1. [Project overview and quick start](../README.md)
2. [Backend development](backend-development.md)
3. [Backend Health Profile](backend-health-profile.md)
4. [Backend Virtual Fridge](backend-virtual-fridge.md)
5. [Web authentication](web-authentication.md)
6. [MCP authentication](mcp-authentication.md)

## Documentation conventions

- Commands target Windows PowerShell unless a block states otherwise.
- Paths are relative to the repository root.
- Placeholder secrets use angle brackets and must never be committed.
- Local HTTP settings are for development only; production requires HTTPS and
  secure cookies.

