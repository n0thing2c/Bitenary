# Bitenary Local Authentik Setup

This guide explains how to run a local Authentik instance with Docker Compose and configure it as the OIDC provider for Bitenary.

## Prerequisites

- Docker Desktop or Docker Engine is installed.
- Docker Compose is available.

Verify:

```sh
docker version
docker compose version
```

## 1. Prepare the Authentik Folder

From the repository root:

```sh
cd infrastructure/authentik
```

If `docker-compose.yml` is not already present, download the official Authentik Compose file:

```sh
curl -L https://docs.goauthentik.io/compose.yml -o docker-compose.yml
```

On Windows PowerShell, use:

```powershell
Invoke-WebRequest https://docs.goauthentik.io/compose.yml -OutFile docker-compose.yml
```

## 2. Create the Authentik `.env`

Create `infrastructure/authentik/.env` with:

```env
PG_PASS=<random-database-password>
AUTHENTIK_SECRET_KEY=<random-secret-key>
AUTHENTIK_ERROR_REPORTING__ENABLED=false
```

Example secret generation with OpenSSL:

```sh
openssl rand -base64 36
openssl rand -base64 60
```

Do not commit real secrets.

## 3. Start Authentik

From `infrastructure/authentik`:

```sh
docker compose pull
docker compose up -d
docker compose ps
```

The local instance should be available at:

```text
http://localhost:9000
```

If the server is still starting, check logs:

```sh
docker compose logs -f server
```

## 4. Complete Initial Admin Setup

Open:

```text
http://localhost:9000/if/flow/initial-setup/
```

Create the initial password for:

```text
Username: akadmin
```

Then log in at:

```text
http://localhost:9000
```

## 5. Create the Bitenary OIDC Application

In the Authentik Admin interface, go to:

```text
Applications -> Applications -> New Application
```

Create an application/provider pair:

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

The policy/user/group bindings step can be left empty for local development.

## 6. Verify OIDC Discovery

Open:

```text
http://localhost:9000/application/o/bitenary/.well-known/openid-configuration
```

It should return JSON containing:

```text
issuer
authorization_endpoint
token_endpoint
jwks_uri
revocation_endpoint
end_session_endpoint
```

## 7. Configure Bitenary Backend

Copy the Authentik provider's client ID and client secret into the backend `.env`:

```env
AUTHENTIK_CLIENT_ID=<client-id-from-authentik>
AUTHENTIK_CLIENT_SECRET=<client-secret-from-authentik>

AUTHENTIK_ISSUER=http://localhost:9000/application/o/bitenary/
AUTHENTIK_AUTHORIZE_URL=http://localhost:9000/application/o/authorize/
AUTHENTIK_TOKEN_URL=http://localhost:9000/application/o/token/
AUTHENTIK_USERINFO_URL=http://localhost:9000/application/o/userinfo/
AUTHENTIK_REVOKE_URL=http://localhost:9000/application/o/revoke/
AUTHENTIK_JWKS_URL=http://localhost:9000/application/o/bitenary/jwks/
AUTHENTIK_END_SESSION_URL=http://localhost:9000/application/o/bitenary/end-session/

OIDC_REDIRECT_URI=http://localhost:8000/api/auth/callback
FRONTEND_ORIGIN=http://localhost:5173
COOKIE_SECURE=false
```

Use `COOKIE_SECURE=false` only for local HTTP development. Production must use HTTPS and `COOKIE_SECURE=true`.
