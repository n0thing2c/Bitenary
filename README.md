# Bitenary

Bitenary is an authenticated nutrition and meal-planning platform with a React
web application, a FastAPI backend, and a Streamable HTTP MCP server for Codex
and Claude.

> **Project status:** active MVP development. Web authentication and personal
> MCP bearer-token authentication are implemented. The standalone MCP
> connections panel is built but is not mounted in the main application yet.

## Features

- Authentik OIDC login and signup using Authorization Code with PKCE.
- Secure web cookies with CSRF protection and automatic access-token refresh.
- Personal MCP connections for Codex and Claude.
- One-time MCP token disclosure with HMAC-SHA-256 storage.
- Streamable HTTP MCP transport at `/mcp`.
- Read-only `get_server_status` MCP tool with usage auditing.
- Independent React MCP connections panel ready for future navigation wiring.

## Architecture

```mermaid
flowchart LR
    User[Web user] --> Frontend[React frontend]
    Frontend -->|Cookie + CSRF| Backend[FastAPI backend]
    Backend <-->|OIDC / JWKS| Authentik[Authentik]
    Backend --> Database[(PostgreSQL)]
    Clients[Codex / Claude] -->|Bearer token /mcp| Backend
```

| Component | Technology | Local address |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite | `http://localhost:5173` |
| Backend | FastAPI, SQLAlchemy, Alembic | `http://localhost:8000` |
| Identity provider | Authentik | `http://localhost:9000` |
| Application database | PostgreSQL 16 | `localhost:5433` |
| MCP transport | FastMCP Streamable HTTP | `http://localhost:8000/mcp` |

## Repository layout

```text
Bitenary/
├── infrastructure/
│   ├── authentik/       # Local identity-provider stack
│   └── bitenary-db/     # Application PostgreSQL stack
├── readme/              # Detailed development and authentication guides
├── src/
│   ├── backend/         # FastAPI, web auth, MCP and migrations
│   └── frontend/        # React application and feature modules
└── README.md
```

## Prerequisites

- Git
- Docker Desktop or Docker Engine with Docker Compose
- Python 3.13, or another compatible Python 3 version
- Node.js and npm

Verify the local toolchain:

```powershell
git --version
docker version
docker compose version
python --version
node --version
npm --version
```

On Windows, use `npm.cmd` if PowerShell blocks the `npm.ps1` script.

## Quick start

### 1. Clone and configure

```powershell
git clone https://github.com/n0thing2c/Bitenary.git
cd Bitenary

Copy-Item infrastructure/authentik/.env.example infrastructure/authentik/.env
Copy-Item src/backend/.env.example src/backend/.env
Copy-Item src/frontend/.env.example src/frontend/.env
```

Set strong values for `PG_PASS` and `AUTHENTIK_SECRET_KEY` in
`infrastructure/authentik/.env`.

Generate secrets when needed:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use separate generated values for `OIDC_STATE_SECRET`, `CSRF_SECRET`, and
`MCP_TOKEN_PEPPER` in `src/backend/.env`.

### 2. Start infrastructure

```powershell
docker compose -f infrastructure/authentik/docker-compose.yml up -d
docker compose -f infrastructure/bitenary-db/docker-compose.yml up -d
```

Complete the Authentik initial setup at:

```text
http://localhost:9000/if/flow/initial-setup/
```

Then configure the Bitenary OIDC application and copy its client credentials
into `src/backend/.env`. Follow the
[web authentication guide](readme/web-authentication.md) for the exact
provider settings and redirect URI.

### 3. Start the backend

```powershell
cd src/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### 4. Start the frontend

Open another terminal from the repository root:

```powershell
cd src/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Verify the installation

| Check | Address or command | Expected result |
| --- | --- | --- |
| Backend health | `http://localhost:8000/api/health` | JSON with `status: "ok"` |
| Authentik | `http://localhost:9000` | Authentik login page |
| Frontend | `http://localhost:5173` | Bitenary authentication page |
| MCP without token | Request `POST /mcp` | `401 Unauthorized` |

For an authenticated MCP smoke test, follow the
[MCP authentication guide](readme/mcp-authentication.md).

## Development commands

Run backend tests from `src/backend`:

```powershell
.\venv\Scripts\python.exe -m pytest tests
```

Run frontend tests and create a production build from `src/frontend`:

```powershell
npm run test
npm run build
```

More backend commands and troubleshooting are documented in the
[backend development guide](readme/backend-development.md).

## Documentation

| Guide | Purpose |
| --- | --- |
| [Documentation index](readme/README.md) | Entry point for all detailed project guides |
| [Backend development](readme/backend-development.md) | Environment, migrations, server, tests and troubleshooting |
| [Backend Virtual Fridge](readme/backend-virtual-fridge.md) | Inventory CRUD, expiry notifications, migrations and testing |
| [Web authentication](readme/web-authentication.md) | Authentik OIDC setup, auth flow, cookies and endpoint verification |
| [MCP authentication](readme/mcp-authentication.md) | Personal tokens, client configuration, status-tool smoke test and auditing |

## Security notes

- Never commit `.env` files, OIDC client secrets, refresh tokens, or MCP bearer
  tokens.
- Use `COOKIE_SECURE=false` only for local HTTP development.
- Production deployments require HTTPS, `COOKIE_SECURE=true`, strong secrets,
  and a stable `MCP_TOKEN_PEPPER`.
- Changing `MCP_TOKEN_PEPPER` invalidates every existing MCP token.
- Plaintext MCP tokens are returned once and must not be written to logs or
  application storage.
