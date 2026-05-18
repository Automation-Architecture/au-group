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
- OpenAPI: `http://localhost:8001/docs`
- All parse routes require header `X-API-Key`

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
| `SUPABASE_URL` | yes | `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | service role key |
| `S3_BUCKET` | yes | `bankruptcy-creditor-docs` |
| `AWS_REGION` | yes | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | yes | IAM user with S3 read/write on bucket |
| `AWS_SECRET_ACCESS_KEY` | yes | — |
| `PARSER_VERSION` | no | `0.1.0` |
| `LOG_LEVEL` | no | `INFO` |

Railway sets `PORT` automatically — do not override it.

### 4. Build and start

Railway reads [`railway.toml`](railway.toml):

- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `GET /health`

After deploy, open the generated URL:

- `https://<your-service>.up.railway.app/health`
- `https://<your-service>.up.railway.app/docs`

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
| S3 errors | Verify IAM keys and bucket name; bucket must be reachable from Railway (public internet). |
| Timeouts on large PDFs | Increase n8n HTTP timeout or use `GET /api/v1/jobs/{document_id}` poll pattern. |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/parse/document` | Full pipeline (route → classify → extract → validate) |
| POST | `/api/v1/parse/ocr` | OCR only |
| POST | `/api/v1/parse/structured` | Structured PDF text only |
| POST | `/api/v1/extract/form201` | Form 201 extraction |
| POST | `/api/v1/extract/creditor-matrix` | Creditor matrix extraction |
| GET | `/api/v1/review-queue` | Manual review queue |
| GET | `/api/v1/jobs/{document_id}` | Job status poll (n8n timeouts) |

## Tests

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q
```

## Deferred (Phase 2)

Schedule parsers (`SCHEDULE_A_B`, `SCHEDULE_D`, `SCHEDULE_E_F`, `SOFA`) live in `app/extractors/schedules.py` as stubs until Phase 1 accuracy gates pass.
