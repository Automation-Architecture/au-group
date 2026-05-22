# CI/CD environments and secrets

GitHub **Environments** gate deployments and hold secrets. Configure in repo **Settings → Environments**.

## Environments

| Environment | Purpose | Protection | Deploy workflows |
|-------------|---------|------------|------------------|
| **pr** | Pull request CI only | None | `ci.yml`, path-filtered jobs |
| **staging** | Pre-production parser + **PR integration tests (strict)** | Optional reviewers | `deploy-parser-railway.yml` (dispatch `staging`), `integration-tests.yml`, `ci.yml` integration job |
| **production** | Live parser, n8n, Supabase | **Required reviewers** (manual approval) | `deploy-parser-railway.yml`, `deploy-n8n.yml`, `deploy-supabase.yml`, `smoke-e2e.yml` (cron) |

## Branch → environment

| Branch | CI | CD |
|--------|----|----|
| PR → `main` / `develop` | All path-filtered jobs | None |
| `main` push | Same | Parser Railway (production env), n8n + Supabase when paths change |
| `workflow_dispatch` | — | Staging or production per workflow inputs |

## Secrets (repository or environment)

| Secret | Used by | Description |
|--------|---------|-------------|
| `RAILWAY_TOKEN` | `deploy-parser-railway.yml` | Railway project deploy token |
| `PARSER_STAGING_URL` | Staging smoke | e.g. `https://au-group-staging.up.railway.app` |
| `PARSER_PRODUCTION_URL` | Prod smoke / cron | Matches `project.config.yaml` `api_base_url` when live |
| `DOCUMENT_PARSER_API_KEY` | Smoke, integration | Same as parser `API_KEY` in Railway |
| `N8N_BASE_URL` | n8n deploy, smoke, local export | `https://automationarchitecture.app.n8n.cloud` |
| `N8N_API_KEY` | n8n deploy, smoke, local export | n8n API key (not required for n8n CI — CI tests committed JSON only) |
| `SUPABASE_ACCESS_TOKEN` | Supabase deploy | Supabase CLI personal access token |
| `SUPABASE_PROJECT_REF` | Supabase deploy | Project ref (subdomain) |
| `SUPABASE_DB_PASSWORD` | Supabase deploy | Database password for `supabase link` |
| `SUPABASE_URL` | Integration tests | Project URL — **staging** environment |
| `SUPABASE_SERVICE_ROLE_KEY` | Integration tests | Service role (CI only) — **staging** |
| `S3_BUCKET`, `AWS_*` | Integration tests | S3 smoke fixtures |
| `EC2_HOST`, `EC2_SSH_KEY` | `deploy-parser-ec2.yml` | Phase 4 EC2 path |
| `JIRA_*` | AAA dashboard repo | Not stored here; see export package |

## Variables (non-secret)

| Variable | Example |
|----------|---------|
| `SMOKE_BANKRUPTCY_ID` | UUID for optional parse smoke |
| `SMOKE_S3_KEY` | `raw-documents/...pdf` |
| `INTEGRATION_CI_STRICT` | `false` | Set to `true` to **fail PRs** when staging integration secrets are missing (after secrets are configured) |

## Repository secrets / variables (auto-fix)

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `CURSOR_API_KEY` | Secret | — | Cursor Agent (only if `AUTOFIX_CURSOR_ENABLED=true`) |
| `AUTOFIX_CURSOR_ENABLED` | Variable | `false` | Opt-in Cursor step in `pr-autofix.yml` |
| `AUTOFIX_ALLOWED_ACTORS` | Variable | — | Comma-separated logins allowed for label/manual autofix |

## Playwright (local / CI)

| Variable | Default | Purpose |
|----------|---------|---------|
| `PARSER_BASE_URL` | `http://127.0.0.1:8001` | Target for [`e2e/`](../../e2e/) tests |

CI starts the parser via [`scripts/ci/start-parser-for-e2e.sh`](../../scripts/ci/start-parser-for-e2e.sh) with `EXPOSE_OPENAPI=true`.

## AAA client dashboard (separate repo)

This repo **validates** [`export/aaa-client-dashboard/au-group/`](../../export/aaa-client-dashboard/au-group/). The dashboard app repo should:

1. Merge `patches/clients.au-group.ts.snippet` into `clients.ts`
2. Copy `data/*.json` to `app/src/app/client/data/au-group/`
3. Append [`patches/sync-jira-workflow-step.yml`](../../export/aaa-client-dashboard/au-group/patches/sync-jira-workflow-step.yml) to its Jira sync workflow

## Branch protection (configure in GitHub UI)

Recommended required checks on `main`:

- `CI / all-green` (or individual: `CI / parser`, `CI / supabase`, `CI / n8n`, `CI / export` when using required checks per job)
- 1 approving review

See [`.github/BRANCH_PROTECTION.md`](../../.github/BRANCH_PROTECTION.md) for a copy-paste checklist.

## Promotion flow

```mermaid
flowchart LR
  PR[Pull request] --> CI[ci.yml path jobs]
  CI --> Merge[Merge to main]
  Merge --> CD[Deploy workflows]
  CD --> Smoke[smoke-e2e.yml]
```
