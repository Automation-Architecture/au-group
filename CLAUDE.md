# CLAUDE.md — AU Group

Agent-facing notes for working in this repo. The README is the human entry point — start there for system overview.

## What this is

AI-powered lead-gen from federal bankruptcy filings. PACER → Schedule F parse → ZoomInfo enrichment → Salesforce. Deployed stack: **Supabase Postgres + Railway (FastAPI document-parser) + n8n**. See `README.md` for the full topology.

## Repo conventions

- **Client meeting transcripts** — raw Fireflies transcripts do **NOT** live in this repo. They live in `~/Documents/aaa/Client Docs/AU Group/Meeting Transcripts/`. Only summary + Fireflies ID + decisions land in `client-comms/transcripts/`. Source of truth: global `references/step-01-read-transcripts.md`. (Violated on PR #7 — Copilot caught it.)
- **DOCX/PDF deliverables** — write directly to `~/Documents/aaa/Client Docs/AU Group/<project>/`, never to the repo.
- **Supabase migrations** are timestamp-prefixed (`YYYYMMDDhhmmss_*.sql`). The `au_group_*` identifier covers the lead-gen pipeline tables; `sys02a_*` covers document intelligence. Don't shorten to `sys02_`.

## Runtime gotchas

- **Railway `startCommand` is NOT bash-parsed.** Use `$PORT`, never `${PORT:-8001}` — the literal string is passed to uvicorn and the service crashes on startup. (Fixed in PR #16.)
- **`copilot-review.yml`** is present in `.github/workflows/` and triggers the required `copilot-pull-request-reviewer` status check. The workflow itself almost always passes; the *blocker* is when Copilot doesn't emit a fresh review against the new HEAD even though the workflow ran.

## PR workflow notes (this repo)

- **Stale review pinned to old commit.** When `copilot-review.yml` runs successfully but the `copilot-pull-request-reviewer` review stays pinned to a previous commit (so the PR sits BLOCKED forever), the bot has hung. For doc-only PRs where CI is green and all prior findings are addressed, just `aaa-merge <PR#>` — admin bypass is the right call.
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