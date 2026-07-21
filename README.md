# Bitenary Local Development

This guide explains how to run Bitenary locally with:

- Authentik on `http://localhost:9000`
- Backend API on `http://localhost:8000`
- Frontend app on `http://localhost:5173`
- Bitenary PostgreSQL on local port `5433`

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose
- Python 3.13 or compatible Python 3
- Node.js and npm

Verify:

```sh
docker version
docker compose version
python --version
node --version
npm --version
```

On Windows PowerShell, if `npm` is blocked by execution policy, use `npm.cmd`.

## 1. Start Authentik

From the repository root:

```sh
cd infrastructure/authentik
```

If `docker-compose.yml` is not already present, download the official Authentik Compose file:

```sh
curl -L https://docs.goauthentik.io/compose.yml -o docker-compose.yml
```

On Windows PowerShell:

```powershell
Invoke-WebRequest https://docs.goauthentik.io/compose.yml -OutFile docker-compose.yml
```

Create `infrastructure/authentik/.env`:

```env
PG_PASS=<random-database-password>
AUTHENTIK_SECRET_KEY=<random-secret-key>
AUTHENTIK_ERROR_REPORTING__ENABLED=false
```

Start Authentik:

```sh
docker compose pull
docker compose up -d
```

Open:

```text
http://localhost:9000/if/flow/initial-setup/
```

Create the initial password for `akadmin`, then log in at:

```text
http://localhost:9000
```

## 2. Configure Authentik OIDC

In Authentik Admin, create the Bitenary application/provider:

```text
Applications -> Applications -> New Application
```

Use:

```text
Application name: Bitenary
Application slug: bitenary
Provider type: OAuth2/OIDC
Client type: Confidential
Grant type: Authorization Code
Scopes: openid, profile, email, offline_access
Signing algorithm/key: RS256 / default asymmetric signing key
```

Add this redirect URI:

```text
Mode: Strict
Type: Authorization
URL: http://localhost:8000/api/auth/callback
```

For signup, attach an Authentik enrollment flow to the authentication identification stage. Then set the backend enrollment URL to the flow slug:

```env
AUTHENTIK_ENROLLMENT_URL=http://localhost:9000/if/flow/<enrollment-flow-slug>/
```

Verify discovery:

```text
http://localhost:9000/application/o/bitenary/.well-known/openid-configuration
```

## 3. Configure Backend

From the repository root:

```sh
cd src/backend
python -m pip install -r requirements.txt
```

Create `src/backend/.env` from `src/backend/.env.example`, then fill in the real Authentik values:

```env
AUTHENTIK_CLIENT_ID=<client-id-from-authentik>
AUTHENTIK_CLIENT_SECRET=<client-secret-from-authentik>
AUTHENTIK_ENROLLMENT_URL=http://localhost:9000/if/flow/<enrollment-flow-slug>/
OIDC_STATE_SECRET=<long-random-secret>
CSRF_SECRET=<long-random-secret>
MCP_TOKEN_PEPPER=<long-random-secret>
```

Generate local secrets with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run that command three times for the three Bitenary secrets.

## 4. Start Bitenary Database

From the repository root:

```sh
cd infrastructure/bitenary-db
docker compose up -d
```

The backend `.env.example` expects:

```env
DATABASE_URL=postgresql+asyncpg://bitenary:bitenary@localhost:5433/bitenary
```

## 5. Run Backend

From `src/backend`:

```sh
python -m alembic -c alembic.ini upgrade head
python -m uvicorn app.main:app --reload
```

Check:

```text
http://localhost:8000/api/health
http://localhost:8000/api/auth/login?return_to=/
http://localhost:8000/api/auth/signup?return_to=/
```

## 6. Run Frontend

From the repository root:

```sh
cd src/frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend uses `src/frontend/.env.example`:

```env
VITE_BACKEND_URL=http://localhost:8000
```

## 7. Test and Build

Backend tests:

```sh
python -m pytest src/backend/tests
```

Frontend production build:

```sh
cd src/frontend
npm run build
```

PowerShell alternative:

```powershell
cd src/frontend
npm.cmd run build
```

## Local Auth Flow

1. Open `http://localhost:5173`.
2. Click **Log in** or **Sign up**.
3. Authentik handles credentials or enrollment.
4. Authentik redirects to `http://localhost:8000/api/auth/callback`.
5. Backend sets auth cookies and redirects back to the frontend.
6. Frontend calls `/api/auth/me` with credentials and shows the signed-in state.

Use `COOKIE_SECURE=false` only for local HTTP development. Production must use HTTPS and `COOKIE_SECURE=true`.
