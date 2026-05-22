# AU Group — Bankruptcy Creditor Intelligence

AI-powered bankruptcy intake: monitor filings, parse court documents, enrich creditors, and push leads to Salesforce. Orchestrated by **n8n**; document parsing runs in a dedicated **FastAPI** service (SYS-02A).

| Area | Path |
|------|------|
| Document parser API (SYS-02A) | [`services/document-parser/`](./services/document-parser/) |
| n8n workflows | [`workflows/`](./workflows/) |
| Supabase schema | [`supabase/migrations/`](./supabase/migrations/) |
| Architecture | [`docs/architecture/`](./docs/architecture/) |
| Project config | [`project.config.yaml`](./project.config.yaml) |

## Running the API locally

The document parser is a Python FastAPI app. It listens on **port 8001** by default and is called by n8n over HTTP.

### Prerequisites

**macOS**

```bash
brew install python@3.11 tesseract poppler
```

**Ubuntu 22.04**

```bash
sudo apt-get update
sudo apt-get install -y python3.11-venv tesseract-ocr poppler-utils libgl1
```

### Start the server

```bash
cd services/document-parser
cp .env.example .env   # fill in Supabase, S3, API_KEY (see below)
chmod +x scripts/dev.sh
./scripts/dev.sh
```

`dev.sh` creates a venv, installs dependencies, loads `.env`, enables OpenAPI at `/docs`, and runs uvicorn with `--reload`.

### Verify

| Check | URL / command |
|-------|----------------|
| Health | `curl http://localhost:8001/health` |
| Readiness (Supabase + S3) | `curl http://localhost:8001/health/ready` |
| OpenAPI UI | `http://localhost:8001/docs` (set `EXPOSE_OPENAPI=true` in `.env`; default in dev) |

### Required `.env` values (minimum)

Copy from [`.env.example`](./services/document-parser/.env.example) and set at least:

| Variable | Purpose |
|----------|---------|
| `API_KEY` | Long random secret — n8n sends this as `X-API-Key` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server-side only) |
| `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Read/write court PDFs in storage |

Optional for Swagger/manual testing: `JWT_SECRET` (≥32 chars), `AUTH_USERNAME`, `AUTH_PASSWORD` — then use `POST /api/v1/auth/login` and `Authorization: Bearer <token>`.

### Call the API

**n8n / automation** — static API key:

```http
POST http://localhost:8001/api/v1/parse/document
X-API-Key: <API_KEY>
Content-Type: application/json

{"bankruptcy_id": "<uuid>", "s3_key": "raw-documents/<case>/<file>.pdf"}
```

With `ASYNC_PARSE_ENABLED=true`, the parse endpoint returns **202**; poll `GET /api/v1/jobs/{document_id}` until `completed` or `failed`.

**Swagger / curl** — login first (when JWT vars are set), then use `Authorization: Bearer <access_token>` on protected routes.

### Supabase migrations

Apply schema before parsing against a real project:

```bash
supabase db push
```

Or apply migrations from [`supabase/migrations/`](./supabase/migrations/) in the Supabase dashboard.

### Tests

```bash
cd services/document-parser
source .venv/bin/activate
pytest tests/ --ignore=tests/integration -q
```

Full service docs (production systemd/Railway, endpoint table, troubleshooting): **[`services/document-parser/README.md`](./services/document-parser/README.md)**.

## n8n workflows

Instance: [`automationarchitecture.app.n8n.cloud`](https://automationarchitecture.app.n8n.cloud). Workflow JSON lives under [`workflows/`](./workflows/). CI validates **manifest CD workflows** plus **every file in `workflows/pulled/`** (no cloud call in GitHub Actions).

### Pull all workflows from the AU Group project folder

After you change workflows in the n8n UI, pull them into the repo before opening a PR. The script uses the **same API credentials as Cursor `n8n-mcp`** (`N8N_API_URL` + `N8N_API_KEY`).

**1. Credentials** (pick one — script checks in this order):

| Source | Notes |
|--------|--------|
| `.env.local` at repo root | Gitignored; good for explicit keys |
| Shell `export` | `N8N_API_URL` + `N8N_API_KEY` |
| `.cursor/mcp.json` | **Auto-used** if Cursor `n8n-mcp` is already configured (no export needed) |

```bash
# Only if you do NOT use .cursor/mcp.json:
cat >> .env.local <<'EOF'
N8N_API_URL=https://automationarchitecture.app.n8n.cloud
N8N_API_KEY=your-n8n-api-key
EOF
```

Create an API key in n8n: **Settings → API**. Deploy/smoke use `N8N_BASE_URL` instead of `N8N_API_URL`; the pull script accepts either name.

**2. Pull** (scope: [AU Group folder](https://automationarchitecture.app.n8n.cloud/projects/JNBCQ8yj8IGyBMFc/folders/AGAjejcdoBye7tlv/workflows) — see [`workflows/n8n-pull.config.yaml`](./workflows/n8n-pull.config.yaml)):

```bash
chmod +x scripts/n8n/pull-folder-workflows.sh

# Preview which workflows will be exported (no files written)
./scripts/n8n/pull-folder-workflows.sh --dry-run

# Write JSON under workflows/pulled/ + index.yaml (archived workflows skipped)
./scripts/n8n/pull-folder-workflows.sh
```

**3. Commit** (if the pull should land in git):

```bash
git add workflows/pulled/
git commit -m "chore(n8n): pull AU Group workflows from cloud"
```

To refresh only the **three CD workflows** (`SYS-01`, `SYS-02`, `SYS-03`) into `workflows/` root (not `pulled/`):

```bash
export N8N_BASE_URL=https://automationarchitecture.app.n8n.cloud
export N8N_API_KEY=your-n8n-api-key
./scripts/n8n/export-workflows.sh
```

More detail: [`workflows/README.md`](./workflows/README.md).

### n8n-MCP in Cursor

For AI-assisted edits in the IDE (not bulk export):

- [`n8n-mcp-setup.md`](./n8n-mcp-setup.md) — setup
- [`n8n-mcp-quick-ref.md`](./n8n-mcp-quick-ref.md) — commands
- [`docs/n8n-mcp-integration.md`](./docs/n8n-mcp-integration.md) — overview
- [`.cursor/rules/n8n-mcp-integration.mdc`](./.cursor/rules/n8n-mcp-integration.mdc) — Cursor rule (always active)
- [n8n-skills](https://github.com/czlonkowski/n8n-skills) — `/plugin install czlonkowski/n8n-skills`; CI runs deterministic rules in [`docs/ci/n8n-skills.md`](docs/ci/n8n-skills.md)
- [n8n-skills](https://github.com/czlonkowski/n8n-skills) — `/plugin install czlonkowski/n8n-skills` (CI runs deterministic rules in [`docs/ci/n8n-skills.md`](docs/ci/n8n-skills.md))

## Repo layout (high level)

| Path | What it is |
|------|------------|
| `services/document-parser/` | FastAPI OCR + extraction API |
| `workflows/` | n8n workflow JSON; `pulled/` = full folder export via pull script |
| `supabase/` | Postgres migrations and types |
| `docs/` | Architecture, workflows, project specs |
| `types/database.types.ts` | Generated Supabase types |
| `export/aaa-client-dashboard/au-group/` | AAA client dashboard transfer package |

## CI/CD

| Topic | Doc |
|-------|-----|
| Requirements → gates | [`docs/ci/requirements-traceability.md`](docs/ci/requirements-traceability.md) |
| Environments & secrets | [`docs/ci/environments.md`](docs/ci/environments.md) |
| Rollback | [`docs/ci/rollback.md`](docs/ci/rollback.md) |
| n8n workflow-as-code | [`workflows/README.md`](workflows/README.md), [`tests/n8n/`](tests/n8n/), [`docs/ci/n8n-skills.md`](docs/ci/n8n-skills.md) |
| vbsec security (CI) | [`docs/ci/vbsec.md`](docs/ci/vbsec.md) — all 21 [vbsec](https://github.com/tanviet12/vbsec) rules (gitleaks, bandit, pip-audit, npm audit, patterns) |
| Branch protection setup | [`.github/BRANCH_PROTECTION.md`](.github/BRANCH_PROTECTION.md) |

PRs run [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (parser, **Playwright E2E**, Supabase migrations, n8n JSON, dashboard export, **vbsec security**). Merges to `main` can deploy the document-parser to **Railway**, push **Supabase** migrations, and promote **n8n** workflows when those paths change.

Playwright tests live in [`e2e/`](e2e/) (health, OpenAPI `/docs`). Local: start parser with `EXPOSE_OPENAPI=true`, then `cd e2e && npm test`.

## Jira

Board: [KD — AU Group](https://automationarchitecture.atlassian.net/jira/software/projects/KD/boards/451) (`jira_project_key: KD` in `project.config.yaml`).
