# Backend Development Guide

This guide covers local backend setup, database migrations, development
commands, tests, and common troubleshooting.

## Contents

- [Prerequisites](#prerequisites)
- [Environment setup](#environment-setup)
- [Local services](#local-services)
- [Run the backend](#run-the-backend)
- [Test and validate](#test-and-validate)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.13, or another compatible Python 3 version
- Docker with Docker Compose
- Authentik on `http://localhost:9000`
- PostgreSQL on `localhost:5433`

All commands below assume the repository root unless stated otherwise.

## Environment setup

Create and populate the backend environment file:

```powershell
Copy-Item src/backend/.env.example src/backend/.env
```

Required local secrets:

```env
AUTHENTIK_CLIENT_ID=<authentik-client-id>
AUTHENTIK_CLIENT_SECRET=<authentik-client-secret>
OIDC_STATE_SECRET=<strong-random-secret>
CSRF_SECRET=<strong-random-secret>
MCP_TOKEN_PEPPER=<strong-random-secret>
```

Generate a secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Create a virtual environment and install dependencies:

```powershell
cd src/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

The checked-in local database URL is:

```env
DATABASE_URL=postgresql+asyncpg://bitenary:bitenary@localhost:5433/bitenary
```

## Local services

Start the application database from the repository root:

```powershell
docker compose -f infrastructure/bitenary-db/docker-compose.yml up -d
```

Start Authentik:

```powershell
docker compose -f infrastructure/authentik/docker-compose.yml up -d
```

Check service state:

```powershell
docker compose -f infrastructure/bitenary-db/docker-compose.yml ps
docker compose -f infrastructure/authentik/docker-compose.yml ps
Test-NetConnection localhost -Port 5433
Test-NetConnection localhost -Port 9000
```

See the [web authentication guide](web-authentication.md) before starting
the backend for the first time.

## Run the backend

Apply all migrations:

```powershell
cd src/backend
.\venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Check the current revision:

```powershell
.\venv\Scripts\python.exe -m alembic -c alembic.ini current
```

Start the development server:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Verify the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

Expected fields:

```json
{
  "status": "ok",
  "service": "bitenary-api",
  "environment": "development"
}
```

## Test and validate

Run the complete backend test suite:

```powershell
cd src/backend
.\venv\Scripts\python.exe -m pytest tests
```

Run one test module:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_mcp_tokens.py -q
```

Validate that migrations can generate offline SQL:

```powershell
.\venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql | Out-Null
```

Check Python syntax without starting services:

```powershell
.\venv\Scripts\python.exe -m compileall app api core identity bitenary_mcp
```

Frontend tests and builds are run separately:

```powershell
cd ../frontend
npm run test
npm run build
```

## Project structure

```text
src/backend/
├── alembic/          # Database migrations
├── api/              # Root API router
├── app/              # FastAPI application entry point
├── bitenary_mcp/     # MCP domain, services, adapters and tools
├── core/             # Configuration, database and security utilities
├── identity/         # Authentik OIDC and local user mapping
├── tests/            # Backend test suite
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Troubleshooting

### `Connection refused` on port 5433

Confirm the database container is healthy:

```powershell
docker compose -f infrastructure/bitenary-db/docker-compose.yml ps
```

Also confirm that `DATABASE_URL` uses port `5433`, not PostgreSQL's internal
container port `5432`.

### Alembic cannot find backend modules

Run Alembic from `src/backend` and use the virtual-environment interpreter:

```powershell
cd src/backend
.\venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

### `ModuleNotFoundError: mcp.server`

The virtual environment is stale or missing the official MCP SDK:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -c "from mcp.server.fastmcp import FastMCP; print('MCP SDK OK')"
```

### Auth callback returns `401`

Verify the Authentik client ID, client secret, issuer, JWKS URL, redirect URI,
and the backend clock. The configured redirect URI must exactly match:

```text
http://localhost:8000/api/auth/callback
```

### PowerShell blocks npm

Use the Windows command shim:

```powershell
npm.cmd run test
npm.cmd run build
```

## Related documentation

- [Documentation index](README.md)
- [Project overview](../README.md)
- [Web authentication](web-authentication.md)
- [MCP authentication](mcp-authentication.md)
