# AU Group Document Parser (SYS-02A)

FastAPI service for bankruptcy document OCR, classification, and structured extraction. No Docker.

Called over HTTP by the **code-native pipeline** (`pipeline/worker.py`, running as the
`pipeline-worker` Railway cron service). The n8n orchestration this service was originally
built for is in a parallel run pending decommission — see "6. Wire n8n" for that legacy path.

## System dependencies

**Ubuntu 22.04 (production)**

```bash
sudo apt-get update
sudo apt-get install -y python3.11-venv tesseract-ocr poppler-utils libgl1
```

**macOS (development)**

```bash
brew install python@3.11 tesseract poppler
```

## Local development

```bash
cd services/document-parser
cp .env.example .env   # edit Supabase, S3, API_KEY
chmod +x scripts/dev.sh
./scripts/dev.sh
```

- Health: `GET http://localhost:8001/health`
- OpenAPI (local only): set `EXPOSE_OPENAPI=true` then open `http://localhost:8001/docs`
- Parse routes accept **`X-API-Key`**, or **`Authorization: Bearer`** if JWT login is configured (it is **not** configured in production — see below)

### Authentication

**`X-API-Key` is the only working authentication path in production.**

```http
X-API-Key: <API_KEY>
```

**JWT login — not configured in production.** `JWT_SECRET`, `AUTH_USERNAME` and
`AUTH_PASSWORD` have been removed from the `au-group` Railway service, so
`POST /api/v1/auth/login` returns **503 "JWT authentication is not configured"**
(verified live 2026-08-13). This is a deployment/config decision, not a code
removal — the code still supports JWT wherever those variables are set.

Consequences:

- You cannot obtain a Bearer token from the deployed service.
- Swagger UI's login cannot be used to explore the production API; authorise
  with the `X-API-Key` header instead.

To enable login **locally**, set `JWT_SECRET` (≥32 chars), `AUTH_USERNAME`, and
`AUTH_PASSWORD` in `.env`, then:

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "<AUTH_USERNAME>", "password": "<AUTH_PASSWORD>"}
```

Response: `{ "access_token": "...", "token_type": "bearer", "expires_in": 3600 }`

Then call APIs with:

```http
Authorization: Bearer <access_token>
```

## Production (systemd)

1. Clone repo to `/opt/au-group`
2. Create venv and install requirements
3. Copy `.env` with production secrets
4. Install unit file:

```bash
sudo cp deploy/document-parser.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable document-parser
sudo systemctl start document-parser
```

Deploy updates: `./scripts/deploy.sh`

## `REQUIRE_BANKRUPTCY_ID`

When `REQUIRE_BANKRUPTCY_ID=true` (default), `POST /api/v1/parse/document` returns **400** without `bankruptcy_id`. n8n SYS-01 must pass the bankruptcy UUID into SYS-02.

Orphan rows (documents parsed before this fix): `scripts/backfill_orphan_documents.py` (requires `SUPABASE_*`, `API_KEY`).

## Supabase migrations

After pulling, apply migrations (includes manual review resolve RPC):

```bash
supabase db push
# or apply supabase/migrations/20260519120000_manual_review_resolve.sql in the dashboard
```

## Deploy on Railway

Railway builds from **`Dockerfile`**, not Nixpacks (verified 2026-08-13 from Railway
build logs; deployment manifests report `builder=DOCKERFILE`, which overrides
`railway.toml`'s `builder = "nixpacks"`). **`nixpacks.toml` is dead config.** OCR's
system packages — Tesseract, Poppler, libgl1 — come from the Dockerfile's `apt-get`
layer.

> ⚠️ All four services build from this one Dockerfile, so **anything the cron services
> import must be `COPY`'d into the image**. Copying only `app` shipped an image with no
> `pipeline` package, and every scheduled cron run died on
> `ModuleNotFoundError: No module named 'pipeline'` (PR #123).

### 1. Create the service

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → select `au-group`.
2. **Settings → Root Directory:** `services/document-parser`
3. **Settings → Watch Paths:** `services/document-parser/**` (optional, for monorepo)

### 2. Resources

- **Memory:** at least **2 GB** (OCR on multi-page PDFs is RAM-heavy).
- **CPU:** 2 vCPU recommended for parallel page OCR.

### 3. Environment variables

Set in **Variables** (or sync from a shared Railway environment):

| Variable | Required | Example |
|----------|----------|---------|
| `API_KEY` | yes | long random secret (n8n sends as `X-API-Key`) |
| `JWT_SECRET` | no | ≥32 chars; enables `/auth/login`. **Not set in production** — login returns 503 |
| `AUTH_USERNAME` | no | Login username (with `JWT_SECRET`). **Not set in production** |
| `AUTH_PASSWORD` | no | Login password (with `JWT_SECRET`). **Not set in production** |
| `SUPABASE_URL` | yes | `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | service role key |
| `S3_BUCKET` | yes | `bankruptcy-creditor-docs` |
| `AWS_REGION` | yes | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | yes | IAM user with S3 read/write on bucket |
| `AWS_SECRET_ACCESS_KEY` | yes | — |
| `PARSER_VERSION` | no | `0.1.0` |
| `LOG_LEVEL` | no | `INFO` |
| `APP_ENV` | yes (prod) | `production` |
| `EXPOSE_OPENAPI` | yes (prod) | `false` — do not expose `/docs` publicly |
| `ALLOW_DOCUMENT_URL` | no | `true` only if n8n pastes external PDF URLs |
| `ALLOWED_DOWNLOAD_HOST_SUFFIXES` | if URLs enabled | `uscourts.gov,pacer.uscourts.gov` (comma-separated) |
| `RATE_LIMIT_ENABLED` | no | `true` on public Railway |
| `ALLOW_LOCAL_FILE_URLS` | yes (prod) | `false` |
| `REQUIRE_BANKRUPTCY_ID` | yes | `true` — blocks parse without `bankruptcy_id` |
| `ASYNC_PARSE_ENABLED` | no | `true` — use with n8n poll loop on `GET /jobs/{id}` |

Railway sets `PORT` automatically — do not override it.

### Security checklist (production)

1. **`API_KEY`** — `openssl rand -hex 32`; rotate if leaked (last rotated **2026-08-13**).
   The canonical copy lives in **1Password**, vault **"AU Group"**, item
   **"AU Group — Document Parser / Pipeline"** — update it there on every rotation.
   No n8n workflow uses this key (verified across all 149 workflows on the
   instance), so n8n credentials are not a place it needs to be kept.
   On Railway, `pipeline-worker` holds `DOCUMENT_PARSER_API_KEY` as a
   `${{au-group.API_KEY}}` reference so it tracks rotations automatically —
   keep it a reference; a copy-pasted literal previously drifted and broke the
   worker→parser call.
2. **S3 IAM** — `GetObject` on `raw-documents/*` only; `PutObject` on `ocr-outputs/*` and `parsed-outputs/*`.
3. **n8n uploads** — Supabase Storage keys must match `raw-documents/{case_number}/{id}.pdf`.
4. **Pasted URLs** — set `ALLOW_DOCUMENT_URL=true` and `ALLOWED_DOWNLOAD_HOST_SUFFIXES` to court/PACER domains only.
5. **No public OpenAPI** — `EXPOSE_OPENAPI=false` on Railway.
   > ⚠️ **Production is currently non-compliant with this item.** The live
   > service has `EXPOSE_OPENAPI=true`, so `/docs` is publicly reachable
   > (verified 2026-08-13). The guidance above is still the target state; this
   > needs resolving.
6. **Apply migrations** — including [`20260518130000_document_parser_rls_policies.sql`](../../supabase/migrations/20260518130000_document_parser_rls_policies.sql).
7. **Edge (recommended)** — Cloudflare or similar in front of Railway for WAF / optional IP allowlist on n8n egress.

### 4. Build and start

[`railway.toml`](railway.toml) declares `builder = "nixpacks"`, but that is **overridden**
— the services build from [`Dockerfile`](Dockerfile). Deploy
settings are configured **per service in Railway**, not in this file — four
services share this directory as their root, and a `[deploy]` block here is
forced onto all of them (see the comment in `railway.toml` for the incident).

Configure the web service in Railway → **Settings**:

- **Start:** `/bin/sh -c "exec uvicorn app.main:app --host 0.0.0.0 --port $PORT"`
- **Health check:** `/health`, timeout `120`
- **Restart policy:** `ON_FAILURE`

Keep the `/bin/sh -c` wrapper — Railway does not bash-parse the start command,
so a bare `$PORT` reaches uvicorn literally and the service dies on startup.

The three cron services (`pipeline-worker`, `daily-report`, `intake-cron`) set
their own start commands (`python -m pipeline.<module>`) and need no health
check — they serve no HTTP.

After deploy, verify:

- `https://<your-service>.up.railway.app/health`
- `/docs` should **not** be reachable when `EXPOSE_OPENAPI=false`

### 5. Apply Supabase migration first

Run [`supabase/migrations/20260518120000_sys02a_document_intelligence.sql`](../../supabase/migrations/20260518120000_sys02a_document_intelligence.sql) on the same Supabase project before parsing in production.

### 6. Wire n8n

> **Legacy — n8n is in a parallel run pending decommission.** The pipeline is
> now code-native (`services/document-parser/pipeline/`); new work should go
> there, not into n8n. This section is kept for the workflows still running.
> Note that several existing n8n workflows point at the dead placeholder host
> `https://au-group.railway.app`; the live host is
> `https://au-group-production.up.railway.app`.

In n8n HTTP Request nodes:

- **URL:** `https://<your-service>.up.railway.app/api/v1/parse/document`
- **Header:** `X-API-Key: <API_KEY>`
- **Body:** `{ "bankruptcy_id": "...", "s3_key": "raw-documents/..." }`

See [`docs/workflows/document-parse.md`](../../docs/workflows/document-parse.md).

### 7. Custom domain (optional)

Railway → **Settings → Networking → Generate Domain** or attach a custom domain. Use that URL in n8n instead of the default `*.up.railway.app` host.

### Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on `opencv` / `pdf2image` | Check the `apt-get` layer in [`Dockerfile`](Dockerfile) — **not** `nixpacks.toml`, which is unused. |
| `tesseract not found` | Same — the Dockerfile's apt layer must install `tesseract-ocr` / `poppler-utils`. |
| Cron service dies on `ModuleNotFoundError` | The module isn't `COPY`'d into the image. Add it to [`Dockerfile`](Dockerfile). |
| 403 on API | Check `X-API-Key` matches `API_KEY` in Railway. |
| 400 on pasted URL | Set `ALLOW_DOCUMENT_URL=true` and add host to `ALLOWED_DOWNLOAD_HOST_SUFFIXES`. |
| 400 on `s3_key` | Key must be `raw-documents/{case_number}/{file}.pdf`. |
| S3 errors | Verify IAM keys and bucket name; bucket must be reachable from Railway (public internet). |
| Timeouts on large PDFs | Use `"async_mode": true` on parse/document, then poll `GET /api/v1/jobs/{document_id}`. |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Issue JWT access token (username/password). **503 in production** — JWT is not configured there |
| POST | `/api/v1/parse/document` | Full pipeline; `async_mode: true` → **202** + poll jobs |
| POST | `/api/v1/parse/ocr` | OCR only |
| POST | `/api/v1/parse/structured` | Structured PDF text only |
| POST | `/api/v1/extract/form201` | Form 201 extraction (full parse; **409** if document still processing) |
| POST | `/api/v1/extract/creditor-matrix` | Creditor matrix extraction (**409** if document still processing) |
| GET | `/api/v1/review-queue` | Manual review queue |
| POST | `/api/v1/review/{review_id}/apply` | Apply corrected creditor matrix or Form 201 from Sheet review, then resolve |
| POST | `/api/v1/review/{review_id}/resolve` | Mark review done; clear bankruptcy flag if no pending items |
| GET | `/api/v1/jobs/{document_id}` | Job status poll (`processing` / `completed` / `failed`) |
| GET | `/health/ready` | Readiness probe (Supabase + S3; 503 if deps down) |

## Tests

```bash
source .venv/bin/activate
pip install -r requirements.txt

# Unit tests (mocked pipeline — runs in CI)
pytest tests/ --ignore=tests/integration -q

# Live integration tests (requires .env with Supabase, S3, API_KEY)
pytest tests/integration/ -m integration -v
```

For integration tests, copy `.env.example` to `.env` and optionally set `INTEGRATION_BANKRUPTCY_ID` to an existing test bankruptcy UUID. Do not point integration tests at production case numbers.

## Deferred (Phase 2)

Schedule parsers (`SCHEDULE_A_B`, `SCHEDULE_D`, `SCHEDULE_E_F`, `SOFA`) live in `app/extractors/schedules.py` as stubs until Phase 1 accuracy gates pass.
