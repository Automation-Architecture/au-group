# CLAUDE.md — AU Group

Agent-facing notes for working in this repo. The README is the human entry point — start there for system overview.

## What this is

AI-powered lead-gen from federal bankruptcy filings. PACER → Schedule F parse → ZoomInfo enrichment → Salesforce. Deployed stack: **Supabase Postgres + Railway (FastAPI document-parser) + n8n**. See `README.md` for the full topology.

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

## Runtime gotchas

- **Railway `startCommand` is NOT bash-parsed.** Use `$PORT`, never `${PORT:-8001}` — the literal string is passed to uvicorn and the service crashes on startup. (Fixed in PR #16.)
- **Copilot review wiring — this repo has NO `copilot-review.yml`.** The org merge gate is the `request-copilot-review` CheckRun emitted by `.github/workflows/copilot-review.yml` (this is the check the org ruleset actually evaluates; the dynamic `copilot-pull-request-reviewer` check is invisible to the PR-level `statusCheckRollup`). That workflow is **missing here** — the only copilot-aware workflow is `pr-autofix.yml`, which *reacts to* CodeRabbit/Copilot review comments, it does not *request* a review. Net effect: the org-required `request-copilot-review` check can't be emitted, so copilot coverage falls to the dynamic reviewer that the rollup ignores. **Action:** if PRs sit BLOCKED on a copilot gate, copy `copilot-review.yml` from an existing AAA repo into `.github/workflows/`.

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
