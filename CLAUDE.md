# CLAUDE.md — AU Group

Agent-facing notes for working in this repo. The README is the human entry point — start there for system overview.

## What this is

AI-powered lead-gen from federal bankruptcy filings. MVP flow: PACER (Form 204 top-20 creditor list) → OCR/parse → ZoomInfo company match → Salesforce → daily Slack creditor report. Deployed stack: **Supabase Postgres + Railway (FastAPI document-parser + code-native pipeline cron services)**. n8n is in a **parallel-run pending decommission** (not the build target — see "Current direction"). See `README.md` for the full topology.

## Current direction (as of 2026-06-15) — READ FIRST

- **MVP was simplified (May 2026, PRD v3.0 / Brief v2.0).** Pipeline = PACER → ZoomInfo **company** match + tier-as-attribute → Salesforce (account + bankruptcy logging + email vars + recency flag) → **daily Slack creditor report** (grouped by debtor: Creditor·City·State·Claim·Tier·Status·ZoomInfo URL). Decision-maker **contacts are manual**; Schedule F / automated outreach / historical DB are **Phase 2+ deferred** (the MVP-scope banner in `docs/project/prd.md` governs).
- **The pipeline is being re-platformed OFF n8n → code-native.** Don't build new n8n workflows; the 26 AU-Group n8n workflows are slated for decommission after a parallel-run. Build per **`docs/architecture/n8n-to-code-native-migration.md`** (FastAPI on Railway + the Supabase `processing_jobs` queue; enqueue/claim RPCs). Tracked in Jira **KD epics E9/E10/E11 (KD-54…KD-70)**.
- **All four code-native pipeline stages are BUILT + merged to main** (`services/document-parser/pipeline/`): **intake** (`intake.py`) discovers via `discovery.py` (CourtListener Search API) and retrieves Form 204s via `retrieval.py` (free RECAP archive first → paid PACER CM/ECF fallback); **parse** (`parse.py`, KD-65); **enrich** (`enrich.py`, ZoomInfo GTM Data API, KD-67); **salesforce** (`salesforce.py`, KD-68). Plus `worker.py` (queue drain), `report.py` (daily Slack report), `alerts.py`, `settings.py`. Queue/report RPCs + the `company_tier`/`sf_recency_status` columns are merged. **Three Railway cron services live** in project `au-group-be`: `intake-cron` (`0 9 * * 1-5`), `pipeline-worker` (`*/30`, `SKIP_ENRICH=true`+`SKIP_SF=true` for the parallel-run), `daily-report` (`0 13 * * 1-5`). Whole pipeline is end-to-end runnable with **no client credential**, EXCEPT retrieval (see blocker below).
- **⚠️ CURRENT BLOCKER (2026-06-15): Form 204 retrieval is unproven and likely needs a standard PACER account.** A live kickoff run discovered 27 fresh Chapter 11 cases via CourtListener but retrieved **zero** Form 204 documents — and that result is **rate-limit-poisoned** (CourtListener's aggressive burst limit caused false misses), so it is NOT a clean coverage verdict. No successful RECAP Form 204 retrieval has been confirmed at all. Two stacked problems: CourtListener's burst rate limit makes batch retrieval infeasible without proactive pacing (deferred), and the RECAP archive almost certainly lacks Form 204s for brand-new filings. **CourtListener solved discovery, not retrieval** — the realistic fix is a free standard PACER "Case Search Only" account → the paid per-document CM/ECF fetch (set `PACER_USERNAME`/`PASSWORD` and `intake.py` auto-switches to PACER PCL discovery + the paid fallback). An operator decision on the retrieval path is **open**; full detail in the session-pickup memory.
- **OD-8 RESOLVED (2026-06-14): discovery via CourtListener.** `intake.py` discovers new Chapter 11 filings through the **CourtListener Search API** (`pipeline/discovery.py`, `q=chapter:11`, free FLP token, no standard PACER account) when `COURTLISTENER_API_TOKEN` is set, and auto-selects **PACER PCL** (`PacerClient.search_new_cases`) when `PACER_USERNAME`/`PASSWORD` are set (authoritative, deferred). PACER Monitor API is dead. Form 204 retrieval is RECAP-first (`pipeline/retrieval.py`) → paid PACER CM/ECF only with PACER creds. Caveat: CourtListener `q=chapter:11` misses ~13% of fresh chapter-blank filings (mitigation deferred). Verified live 2026-06-14 (60 Ch.11 cases njb+nysb/14d). Detail: `docs/architecture/n8n-to-code-native-migration.md` OD-8 + `pacer-data-source-discovery-2026-06-02.md` banner.
- **Access status (changed since 05-31):**
  - **Salesforce — RESTORED ✅.** A security token (in 1Password) cleared the login-IP block; the live org was introspected and the four required custom fields created. `salesforce.py` (KD-68, DEV DONE) and KD-10 build against the **confirmed live schema** in `docs/project/salesforce-audit.md` §1c — push into the EXISTING `Bankrupt_Companies__c` + `Bankruptcy__c` objects (NOT `Bankruptcy_Event__c`). Org is **Professional Edition, production**. Remaining = a few client confirmations (the `Engage_*` merge-field family, recency rules) + the live integration test once real creditor data flows.
  - **ZoomInfo — still BLOCKED.** Account not API-enabled. `enrich.py` (KD-67, DEV DONE) is built to the GTM contract but is a no-op behind `SKIP_ENRICH=true` until the key lands. First-live-call checklist is in the module docstring.
  - **Form 204 retrieval — see the blocker above.** The 1Password "Pacer" item is a **PACER *Monitor*** subscription (pacermonitor.com), which does **not** work for the official PACER/PCL APIs — a standard PACER account is the open need.
- **Gotchas:** the Jira REST/Agile API token may still be stale (rotate in 1Password if sprint/Agile-API calls 401 — note KD is a Kanban board with no sprints, so this rarely matters). The Atlassian **MCP is now re-authed as the operator** (Brad) — Jira reads/writes go under his account. (Operational specifics — names, exact secret locations — live in the session-pickup memory, not the repo.)

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
- **Supabase live schema has drifted from local migration files** — see `docs/architecture/supabase-live-schema-state.md` for the full divergence map before writing any migration. Key facts: (1) `processing_jobs.status` type is `processing_job_status` (not `au_group_job_status`); use `'queued'::processing_job_status` — the value `pending` does not exist. (2) `processing_jobs` has extra columns `worker_name` and `job_payload` not in any local file. (3) Five migration versions are registered in `schema_migrations` but have no local file counterpart. (4) Migration `20260530120000` is a phantom (version registered, SQL never ran) — start new migrations at `20260530120001` or later.

## Client dashboard

Provisioned at **`https://dashboard.automationarchitecture.ai/client/au-group`**. Its config lives in the `aaa-client-dashboard` repo (`clients.ts`, `slugs.yaml`) + `aaa-client-dashboard-data` (`sync` branch) — **not here**; don't look for it in this repo. Stage tracker (Postgres) + GitHub-activity sync drive it.

- **Jira sprint sync is OFF for au-group** (`sync.jira: false` in `slugs.yaml`). **KD is a team-managed Kanban board with no sprints** — `sync_jira.py` *can* sync Kanban (backlog/`/board/{id}/issue` fallback), but enabling it would dump the full ungroomed ~53-issue board, including `[Deferred MVP]` epics (KD-5/6/7) and `ISSUES/BLOCKED`-column cards, onto the client view. Flip on only once the board is groomed for client display.
- Refresh dashboard content via `/aaa-dashboard-update`; never put finance/credentials/internal IDs in dashboard data — the **dashboard app's** Document Library route (`/client/au-group/docs`) is unauthenticated/public. (Not to be confused with the document-parser's own `/docs` OpenAPI route, which is gated by `EXPOSE_OPENAPI`.)

## PR workflow notes (this repo)

- **`aaa-merge` bypasses red CI — check `parser / lint-test-audit` before admin-merging code PRs.** `aaa-merge` admin-bypasses branch protection, including a failing CI. During the 2026-05-31 stacked-PR cleanup, PRs #46–#50 were admin-merged while CI was red, landing two latent breakages on `main` that only surfaced on the *next* PR's run: a ruff `I001` import-sort error in `tests/test_pipeline_report.py`, and coverage dropping to 55.7% (below `--cov-fail-under=60`) because `--cov=pipeline` was added while `pipeline/intake.py` + `pipeline/worker.py` had zero tests. A green Copilot/CodeRabbit review is NOT green CI — run `gh run view <run> --json jobs` and confirm `parser / lint-test-audit` passed before `aaa-merge` on any code PR. Doc-only PRs are exempt (CI is path-filtered and skips).
- **Coverage gate (`--cov-fail-under=60`) counts every file under `--cov=app --cov=pipeline`.** New untested modules drag the *total* below the gate even when existing code is fine. `services/document-parser/.coveragerc` omits the two cron entrypoints (`pipeline/intake.py`, `pipeline/worker.py`) with leading-`*/` glob patterns — bare relative paths do NOT match coverage's absolute-path recording in CI. Remove those omits when KD-65 adds parse-worker unit tests. Verify locally before pushing: `pytest tests/ --ignore=tests/integration -m "not smoke" --cov=app --cov=pipeline --cov-fail-under=60`.
- **Stale review pinned to old commit.** When the `copilot-pull-request-reviewer` review stays pinned to a previous commit (so the PR sits BLOCKED forever), the bot has hung. For doc-only PRs where CI is green and all prior findings are addressed, just `aaa-merge <PR#>` — admin bypass is the right call.
- **Dependabot + new lint rules.** Major-version linter bumps (e.g., ruff 0.9 → 0.15) introduce rules that the codebase doesn't satisfy. Dependabot's PR can never pass CI alone because Dependabot can't touch source code. Pattern: open a combined PR (the bump + the source fix in the same commit), close Dependabot's PR as superseded. (See PR #19, which combined the ruff bump with a `class X(str, Enum)` → `StrEnum` migration to satisfy UP042.)
- **`main` can move under you.** While a PR is open, another PR can land that touches the same file and obsolete the premise of your change. Always `git fetch origin main && git log origin/main..HEAD` before pushing a fix — if the file you're touching changed substantively on main, reassess before continuing. (Hit on PR #6, which replaced the stale README the same week PR #4's CI/CD work replaced it independently.)

## Where things live

| Domain | Path |
|---|---|
| FastAPI document parser (SYS-02A) | `services/document-parser/` |
| Code-native pipeline modules + cron entrypoints | `services/document-parser/pipeline/` (`worker.py`, `intake.py`, `report.py`, `alerts.py`, `settings.py`) |
| Coverage config (omits untested cron entrypoints) | `services/document-parser/.coveragerc` |
| Supabase schema | `supabase/migrations/` |
| Architecture decisions | `docs/architecture/` — n8n→code-native migration, supabase-live-schema-state, pacer-pcl-api-reference, salesforce-audit, final-tech-stack, ADR-001 RSS vs PACER |
| n8n workflow specs (legacy, decommission-pending) | `docs/workflows/`, `docs/n8n/` |
| Project metadata | `project.config.yaml` |
| TypeScript DB types | `types/database.types.ts` |
| Discovery artifacts (historical) | `references/step-NN-*.md`, `docs/throughput-log.md` |

=== SYSTEM UNDERSTANDING ===

Trust Boundaries:
- Internet/client → FastAPI: X-API-Key OR Bearer JWT (no per-resource authZ)
- FastAPI → Supabase: service_role (RLS bypass; god-mode on tables + RPCs)
- FastAPI → S3: AWS creds; reads only raw-documents/* pattern
- FastAPI → HTTP(S) document_url: gated by flags + host suffix + SSRF checks
- FastAPI → file://: dev-only; blocked in production; chrooted to LOCAL_FILE_ROOT
- Supabase anon/authenticated: restrictive deny on SYS-02A tables; no au_group_* EXECUTE
- CI: verify-rpc-acl.sql + smoke_merge_creditor_matrix_dedup_audit.sql post-migrate

Data Flow:
1. Auth (verify_auth) → route handler → DocumentPipeline
2. _resolve_pdf: s3_key | https? URL | file:// (dev)
3. _parse_document_sync OR async background → same sync path
4. Classify → extract → in-process dedup → validate
5. Persist: documents + extractions (REST) + merge/upsert (RPC)
6. Review: queue REST read; apply/resolve → RPC + optional merge

State Machines:
- Job: raw_extraction processing → completed | failed
- Merge idempotency: RAW_CREDITORS_MERGED after au_group_merge_creditor_matrix
- Review: pending | in_review → resolved (apply may merge first)
- Cache: content_sha256 + parser_version; force/backfill rules in _lookup_cached_document

Invariants (global):
- API_KEY non-empty; ≥32 chars in production
- JWT: HS256, type=access, sub required; login rate-limited
- au_group_* RPC: service_role EXECUTE only (reapply migration last)
- s3_key read: ^raw-documents/[case]/[doc].pdf$
- document_url: disabled unless allow_document_url + non-empty suffix allowlist
- merge_creditors skipped when validation.manual_review_required
- file:// never unlinked by _should_unlink_temp (only s3 + http(s) temps deleted)

Attack Surface (entry points):
- Unauth: GET /health, GET /health/ready (dependency probe labels)
- Auth: POST /api/v1/auth/login
- Auth: all other /api/v1/* (parse, extract, review)
- Egress: document_url fetch; S3 read/write
- Secrets in env: API_KEY, JWT_SECRET, service_role, AWS keys

Assumptions Registry:
| ID | Assumption | Conf |
|----|------------|------|
| A1 | Only operators/n8n hold API_KEY | MED |
| A2 | service_role never in browser clients | MED |
| A3 | expose_openapi=false in prod | HIGH |
| A4 | JWT subject unused for authorization | HIGH |
| A5 | DNS at URL-check time ≈ DNS at connect time | LOW |
| A6 | au_group_merge_creditor_matrix enforces integrity in SQL | MED (not line-audited) |