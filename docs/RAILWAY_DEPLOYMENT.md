# SellerOS Railway Preview Deployment

This package deploys the React frontend and FastAPI backend as one same-origin Railway service, with
Railway PostgreSQL as a separate service. It is a controlled founder preview, not a public
multi-tenant SaaS release.

## Repository source

- Repository: `DataScience-beginner/Amazon-seller-analytics-platform`
- Branch: `agent/selleros-phase-1-mvp`
- Service root directory: `/`
- Dockerfile path: `/Dockerfile`

Railway builds the multi-stage Dockerfile automatically. Do not set separate frontend build/start
commands and do not set `VITE_API_BASE_URL`; the browser calls `/api/v1` on the same domain.

## 1. Add PostgreSQL

In the SellerOS Railway project:

1. Select **Create** or **New**.
2. Select **Database → PostgreSQL**.
3. Wait until the database service is available.

Do not reuse the Power Trading database. SellerOS migrations own a separate schema.

## 2. Configure the SellerOS service

Open the SellerOS service **Variables** tab and add:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
ENVIRONMENT=production
PREVIEW_BASIC_AUTH_USERNAME=<your-private-preview-username>
PREVIEW_BASIC_AUTH_PASSWORD=<a-unique-random-password-of-at-least-16-characters>
```

Use Railway's variable-reference picker for `DATABASE_URL`; the PostgreSQL service may have a
different display name, in which case Railway updates the reference name.

The preview credentials are an interim whole-application access lock. Do not reuse a GitHub,
Amazon, email or banking password. The container fails closed in production if either credential is
missing or the password is shorter than 16 characters.

The image sets these safe runtime defaults:

```text
UPLOAD_DIRECTORY=/app/uploads
FRONTEND_DIST_DIRECTORY=/app/frontend-dist
ALLOW_UNAUTHENTICATED_WORKSPACE_BOOTSTRAP=true
```

Workspace bootstrap is reachable only after the preview login. Final tenant authentication must
replace this interim arrangement before customer or public SaaS use.

## 3. Deployment settings

Configure:

```text
Healthcheck path: /api/v1/health
Restart policy: On Failure
```

The container runs:

```text
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Alembic therefore upgrades the PostgreSQL schema before the application accepts traffic. A failed
migration prevents the new deployment from becoming healthy.

## 4. Optional upload volume

Import staging files normally exist only until confirmation or terminal failure. To retain a
retryable staged file across redeployments, attach a Railway volume to the SellerOS service:

```text
Mount path: /app/uploads
```

Imported market evidence lives in PostgreSQL; the volume is not the system of record.

## 5. Generate the domain

After the deployment is healthy:

1. Open **SellerOS service → Settings → Networking**.
2. Select **Generate Domain**.
3. Open the generated HTTPS URL.
4. Enter the preview username and password in the browser prompt.
5. Create the founder organisation and Amazon India marketplace.
6. Re-import the Keepa workbook through the application.

The local SQLite database and private workbooks are intentionally excluded from the Docker image and
are never pushed through Git.

## Verification

Check:

```text
https://<selleros-domain>/api/v1/health
https://<selleros-domain>/
```

The health endpoint should return application/database `ok`. The root page should require preview
authentication and then load SellerOS. Direct routes such as `/dashboard` must load the same React
application.

## Production boundary

The preview login protects one founder deployment but does not provide users, password recovery,
roles, tenant principals, rate limits or audited sessions. Do not invite customers or describe the
deployment as production SaaS until identity and server-enforced tenant authorisation are complete.
