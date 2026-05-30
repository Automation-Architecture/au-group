# CLAUDE.md — AU Group

Agent-facing notes for working in this repo. The README is the human entry point — start there for system overview.

## What this is

AI-powered lead-gen from federal bankruptcy filings. PACER → Schedule F parse → ZoomInfo enrichment → Salesforce. Deployed stack: **Supabase Postgres + Railway (FastAPI document-parser) + n8n**. See `README.md` for the full topology.

## Current direction (as of 2026-05-30) — READ FIRST

- **MVP was simplified (May 2026, PRD v3.0 / Brief v2.0).** Pipeline = PACER → ZoomInfo **company** match + tier-as-attribute → Salesforce (account + bankruptcy logging + email vars + recency flag) → **daily Slack creditor report** (grouped by debtor: Creditor·City·State·Claim·Tier·Status·ZoomInfo URL). Decision-maker **contacts are manual**; Schedule F / automated outreach / historical DB are **Phase 2+ deferred** (the MVP-scope banner in `docs/project/prd.md` governs).
- **The pipeline is being re-platformed OFF n8n → code-native.** Don't build new n8n workflows; the 26 AU-Group n8n workflows are slated for decommission after a parallel-run. Build per **`docs/architecture/n8n-to-code-native-migration.md`** (FastAPI on Railway + the Supabase `processing_jobs` queue; enqueue/claim RPCs). Tracked in Jira **KD epics E9/E10/E11 (KD-54…KD-70)**. **Unblocked build path:** KD-57 (queue RPCs) → KD-60 (grouped report RPC + `report.py` + cron) → KD-61 (parse). **WP-04 column migration must precede WP-03 grouped RPC** (it selects `creditors.company_tier`).
- **Salesforce stage is access-blocked** (not creds — see `docs/project/salesforce-audit.md`): creds exist but a VPN/login-IP lockout blocks the live org. The two new SF fields the re-scope needs (`Company_Tier__c`, `ZoomInfo_URL__c`) are on KD-10.
- **Gotchas:** the Jira REST/Agile API token (1Password "Atlassian", Engineering vault) is **stale/401** — sprint creation is blocked on a fresh token. The Atlassian **MCP is authed as the former engineer (Yanji)** — revoke + re-auth as the operator.

## Commands (document-parser)

The one runnable service lives in `services/document-parser/`. Run from that directory:

```bash
./scripts/dev.sh                                         # local dev: venv + deps + uvicorn --reload on PORT (default 8001)
pip install -r requirements.txt -r requirements-dev.txt  # one-off setup if running pytest/ruff outside dev.sh
pytest tests/ --ignore=tests/integration -q              # unit tests
pytest tests/integration/ -m integration -v              # live tests (needs .env, S3, Supabase)
ruff check .                                             # lint
```

**Deploy:** Railway builds with **Nixpacks** (`nixpacks.toml` installs Tesseract + Poppler for OCR and sets `PORT` automatically); production start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (`$PORT` only works where it's set — locally use `./scripts/dev.sh`). A `Dockerfile` also exists for the alternate EC2 path (`scripts/deploy.sh`, `deploy-parser-ec2.yml`).

## Repo conventions

- **Client meeting transcripts** — raw Fireflies transcripts do **NOT** live in this repo. They live in `~/Documents/aaa/Client Docs/AU Group/Meeting Transcripts/`. Only summary + Fireflies ID + decisions land in `client-comms/transcripts/`. Source of truth: global `references/step-01-read-transcripts.md`. (Violated on PR #7 — Copilot caught it.)
- **DOCX/PDF deliverables** — write directly to `~/Documents/aaa/Client Docs/AU Group/<project>/`, never to the repo.
- **Supabase migrations** are timestamp-prefixed (`YYYYMMDDhhmmss_*.sql`). Three identifier prefixes are in use, each with a distinct meaning — don't rename between them: `au_group_*` = lead-gen pipeline tables, `sys02a_*` = document-intelligence schema (SYS-02A), `sys02_*` = SYS-02 v2 per-document parse results (e.g. `..._sys02_document_parse_results.sql`). `sys02_` is **not** a typo for `sys02a_`.
- **`project.config.yaml`** — `client` is the **business name** ("AU Group"), not the contact's name ("Keith"); `stage` tracks reality (`build`, with `discovery` closed). The `export/aaa-client-dashboard/` tree is a **historical transfer package** — still in-repo and CI-validated, but no longer the source of truth for the live dashboard (that's `clients.ts` + the data repo). Don't copy it to (re)provision; don't assume it's dead/deletable either.

## Runtime gotchas

- **Railway `startCommand` is NOT bash-parsed.** Use `$PORT`, never `${PORT:-8001}` — the literal string is passed to uvicorn and the service crashes on startup. (Fixed in PR #16.)
- **Copilot review is required before merge, wired via `.github/workflows/copilot-review.yml`** (requests `Copilot` as a reviewer on each PR; restored in `b0802e7` to fix a hanging status check). If it's ever absent the copilot check hangs and PRs sit BLOCKED — see the stale-review note below.

## Client dashboard

Provisioned at **`https://dashboard.automationarchitecture.ai/client/au-group`**. Its config lives in the `aaa-client-dashboard` repo (`clients.ts`, `slugs.yaml`) + `aaa-client-dashboard-data` (`sync` branch) — **not here**; don't look for it in this repo. Stage tracker (Postgres) + GitHub-activity sync drive it.

- **Jira sprint sync is OFF for au-group** (`sync.jira: false` in `slugs.yaml`). **KD is a team-managed Kanban board with no sprints** — `sync_jira.py` *can* sync Kanban (backlog/`/board/{id}/issue` fallback), but enabling it would dump the full ungroomed ~53-issue board, including `[Deferred MVP]` epics (KD-5/6/7) and `ISSUES/BLOCKED`-column cards, onto the client view. Flip on only once the board is groomed for client display.
- Refresh dashboard content via `/aaa-dashboard-update`; never put finance/credentials/internal IDs in dashboard data — the **dashboard app's** Document Library route (`/client/au-group/docs`) is unauthenticated/public. (Not to be confused with the document-parser's own `/docs` OpenAPI route, which is gated by `EXPOSE_OPENAPI`.)

## PR workflow notes (this repo)

- **Stale review pinned to old commit.** When the `copilot-pull-request-reviewer` review stays pinned to a previous commit (so the PR sits BLOCKED forever), the bot has hung. For doc-only PRs where CI is green and all prior findings are addressed, just `aaa-merge <PR#>` — admin bypass is the right call.
- **Dependabot + new lint rules.** Major-version linter bumps (e.g., ruff 0.9 → 0.15) introduce rules that the codebase doesn't satisfy. Dependabot's PR can never pass CI alone because Dependabot can't touch source code. Pattern: open a combined PR (the bump + the source fix in the same commit), close Dependabot's PR as superseded. (See PR #19, which combined the ruff bump with a `class X(str, Enum)` → `StrEnum` migration to satisfy UP042.)
- **`main` can move under you.** While a PR is open, another PR can land that touches the same file and obsolete the premise of your change. Always `git fetch origin main && git log origin/main..HEAD` before pushing a fix — if the file you're touching changed substantively on main, reassess before continuing. (Hit on PR #6, which replaced the stale README the same week PR #4's CI/CD work replaced it independently.)

## Where things live

| Domain | Path |
|---|---|
| FastAPI document parser (SYS-02A) | `services/document-parser/` |
| Supabase schema | `supabase/migrations/` |
| Architecture decisions | `docs/architecture/` (final tech stack, ADR-001 RSS vs PACER) |
| n8n workflow specs | `docs/workflows/`, `docs/n8n/` |
| Project metadata | `project.config.yaml` |
| TypeScript DB types | `types/database.types.ts` |
| Discovery artifacts (historical) | `references/step-NN-*.md`, `docs/throughput-log.md` |
