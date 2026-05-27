# AU Group Document Parser (SYS-02A)

FastAPI service for bankruptcy document OCR, classification, and structured extraction. Orchestrated by **n8n** over HTTP. No Docker.

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
- Parse routes accept **`X-API-Key`** (n8n) or **`Authorization: Bearer`** (after login)

### Authentication

**n8n / automation** — static API key:

```http
X-API-Key: <API_KEY>
```

**Swagger / manual clients** — login for a short-lived JWT:

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

Set `JWT_SECRET` (≥32 chars), `AUTH_USERNAME`, and `AUTH_PASSWORD` in `.env` to enable login.

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

Railway runs the app with **Nixpacks** (no Dockerfile). OCR needs system packages — `nixpacks.toml` installs Tesseract and Poppler.

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
| `JWT_SECRET` | no | ≥32 chars; enables `/auth/login` |
| `AUTH_USERNAME` | no | Login username (with `JWT_SECRET`) |
| `AUTH_PASSWORD` | no | Login password (with `JWT_SECRET`) |
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

1. **`API_KEY`** — `openssl rand -hex 32`; store only in Railway + n8n credentials; rotate if leaked.
2. **S3 IAM** — `GetObject` on `raw-documents/*` only; `PutObject` on `ocr-outputs/*` and `parsed-outputs/*`.
3. **n8n uploads** — Supabase Storage keys must match `raw-documents/{case_number}/{id}.pdf`.
4. **Pasted URLs** — set `ALLOW_DOCUMENT_URL=true` and `ALLOWED_DOWNLOAD_HOST_SUFFIXES` to court/PACER domains only.
5. **No public OpenAPI** — `EXPOSE_OPENAPI=false` on Railway.
6. **Apply migrations** — including [`20260518130000_document_parser_rls_policies.sql`](../../supabase/migrations/20260518130000_document_parser_rls_policies.sql).
7. **Edge (recommended)** — Cloudflare or similar in front of Railway for WAF / optional IP allowlist on n8n egress.

### 4. Build and start

Railway reads [`railway.toml`](railway.toml):

- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `GET /health`

After deploy, verify:

- `https://<your-service>.up.railway.app/health`
- `/docs` should **not** be reachable when `EXPOSE_OPENAPI=false`

### 5. Apply Supabase migration first

Run [`supabase/migrations/20260518120000_sys02a_document_intelligence.sql`](../../supabase/migrations/20260518120000_sys02a_document_intelligence.sql) on the same Supabase project before parsing in production.

### 6. Wire n8n

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
| Build fails on `opencv` / `pdf2image` | Confirm `nixpacks.toml` is present; redeploy. |
| `tesseract not found` | Same — apt packages must install on build. |
| 403 on API | Check `X-API-Key` matches `API_KEY` in Railway. |
| 400 on pasted URL | Set `ALLOW_DOCUMENT_URL=true` and add host to `ALLOWED_DOWNLOAD_HOST_SUFFIXES`. |
| 400 on `s3_key` | Key must be `raw-documents/{case_number}/{file}.pdf`. |
| S3 errors | Verify IAM keys and bucket name; bucket must be reachable from Railway (public internet). |
| Timeouts on large PDFs | Use `"async_mode": true` on parse/document, then poll `GET /api/v1/jobs/{document_id}`. |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Issue JWT access token (username/password) |
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
