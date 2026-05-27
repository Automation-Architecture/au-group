# Implementation notes — GitHub Actions platform features

**Date:** 2026-05-21  
**Scope:** Integrate CI platform improvements from architecture review, **excluding n8n CI and AWS OIDC**.

## Delivered

| Feature | Location |
|---------|----------|
| Composite: parser setup | `.github/actions/setup-parser-ci/` |
| Composite: vbsec + SARIF | `.github/actions/run-vbsec/` |
| Scanner install script | `scripts/ci/install-security-scanners.sh` |
| SARIF generation | `scripts/ci/generate-security-sarif.sh` |
| Export validation CI | `.github/workflows/ci-export.yml` + path filter in `ci.yml` |
| Deploy concurrency locks | `deploy-supabase.yml`, `deploy-parser-railway.yml`, `deploy-parser-ec2.yml` |
| SARIF permissions | `security-events: write` on `ci.yml`, `ci-security.yml`, deploy workflows |

## Refactored workflows

- `ci-parser.yml`, `ci-playwright.yml`, `integration-tests.yml` → `setup-parser-ci`
- `ci-security.yml` → `run-vbsec` (shorter; logic centralized)

## Explicitly out of scope (per request)

- n8n workflow pytest job (`tests/n8n/`)
- AWS OIDC / IAM federation for integration secrets

## Copilot / missing `ci-export.yml` (2026-05-21)

- **Root cause:** `.gitignore` had bare `workflows`, which also ignored `.github/workflows/ci-export.yml`. File existed locally but was never committed; reusable workflow call failed on GitHub.
- **Fix:** Ignore only repo-root n8n exports: `/workflows/` and `/workflows/pulled`. Staged `ci-export.yml` for commit.

## PR trigger (2026-05-21)

- `ci.yml` `pull_request` has no `branches:` filter — runs on every PR once workflow files exist on the **base** branch.
- See `docs/ci/pull-request-ci.md` for the “first PR / only Copilot” limitation.

## Manual follow-up (GitHub UI)

- **Environments:** Ensure `staging` / `production` have required reviewers on production (see `.github/BRANCH_PROTECTION.md`).
- **Branch protection:** Optional required check `validate` / `CI — AAA dashboard export` after first green run on `main`.
- **Code scanning:** SARIF upload uses `github/codeql-action/upload-sarif`; enable **Code security** / Dependabot alerts if the Security tab stays empty.

## Supabase CI port 54322 (2026-05-21)

- **Symptom A:** `supabase db start` fails on GHA with `failed to bind host port ... 54322: address already in use` after a new `ghcr.io/supabase/postgres` image pull.
- **Cause A:** Intermittent Docker port-release race on hosted runners ([supabase/setup-cli#265](https://github.com/supabase/setup-cli/issues/265)).
- **Symptom B:** `supabase db reset` fails with `supabase start is not running` on every retry.
- **Cause B:** Regression from calling `supabase stop` before `db reset`; reset requires Postgres already up (`db start` first).
- **Fix:** `ci-supabase.yml` — per attempt: `supabase db start` then `db reset --local --yes`; only `stop`/`docker rm` between failed attempts; `if: always()` stop at end.

## Supabase CI RLS verify (2026-05-22)

- **Symptom:** `verify-supabase-rls.sh` failed with `Could not resolve local DB_URL` even when migrate-reset succeeded.
- **Cause:** `Stop Supabase local` (`if: always()`) ran immediately after migrations, before `db lint` and RLS verify — `supabase status` had no running DB.
- **Fix:** Move stop step to the last job step; `verify-supabase-rls.sh` also falls back to `supabase status -o env` when JSON lacks `DB_URL`.

## PR review follow-ups (2026-05-21)

- **vbsec SSRF:** Patterns in `vbsec_rules.py` now match request-derived URL args only; allowlist extended for Supabase/readiness clients in `vbsec_ci_scan.py`.
- **E2E:** `e2e/tests/parser-parse-flow.spec.ts` — auth gate, validation, correlation header, OpenAPI parse paths.
- **Observability:** `request_context.py` + middleware; `log_event` injects `correlation_id`; background parse binds parent request id.

## Assumptions

- `continue-on-error: true` on SARIF upload avoids failing CI when GitHub Advanced Security is not licensed; vbsec JSON + scan step still gate merges.
- Deploy concurrency uses `cancel-in-progress: false` so in-flight production deploys are not killed by a newer push.

## CodeQL + Trivy security layers (2026-05-27)

- **Added:** `.github/workflows/ci-codeql.yml`, `ci-trivy.yml`, `.github/codeql/codeql-config.yml`, `scripts/ci/install-trivy.sh`
- **Gate:** `ci.yml` `all-green` requires `codeql` + `trivy` on every PR/push (same as vbsec)
- **Trivy:** filesystem scan only (no Docker / no `trivy-action`); pins CLI v0.69.3
- **Deploy:** `deploy-parser-railway.yml` and `deploy-parser-ec2.yml` run both before deploy
- **Docs:** `docs/ci/security-layers.md`
- **Deferred:** OWASP ZAP (needs stable staging + `PARSER_STAGING_URL`); Semgrep (overlaps vbsec/Bandit)

## Gitleaks CI credentials (2026-05-22)

- **Symptom:** GitHub Advanced Security flagged `generic-api-key` in `.github/workflows/ci-parser.yml` for hardcoded `API_KEY` / `JWT_SECRET` test literals.
- **Fix:** `scripts/ci/generate-parser-test-env.sh` emits ephemeral `openssl rand -hex 32` values; CI workflows source it; pytest uses `secrets.token_hex` in `conftest.py`; E2E writes `e2e/.parser-e2e.env` (gitignored) for Playwright.

## OpenAPI route descriptions (2026-05-22)

- Short usage-focused `summary` and `description` on each route (what the route is for, not status codes or env vars).
- Tag blurbs in `openapi_tags` on `app/main.py`. Visible at `/docs` when `EXPOSE_OPENAPI=true`.

## Parse document — unknown bankruptcy_id (2026-05-22)

- **Symptom:** Swagger default UUID (`3fa85f64-...`) caused FK 409 on `documents` insert, surfaced as **503**.
- **Fix:** `DocumentPipeline._require_bankruptcy()` checks `get_bankruptcy` before PDF work; `BankruptcyNotFoundError` → **422** with clear detail. Skipped when Supabase persistence is disabled (`_enabled` false).

## Parse 200 but empty `creditors` / `bankruptcy_creditors` (2026-05-22)

- **Symptom:** `POST /parse/document` returns 200; user sees no rows in “main” creditor tables. `documents` + `creditor_matrix_*` may still have rows.
- **Cause:** `au_group_merge_creditor_matrix` RPC fails on remote DB with `42P10` (missing `idx_creditors_normalized_name_address`). First parse can leave matrix rows; merge never runs; repeat requests hit content-hash cache and skip merge.
- **Fix:** Migration `20260522100000_ensure_creditors_merge_unique_index.sql`; `_backfill_creditor_merge` on cache hit; RPC errors raise `SupabaseUnavailableError`.
- **Ops:** Apply migration to hosted Supabase (`supabase db push` or SQL editor), then re-POST with `"force": true` or call the same parse again (backfill runs on cache).

## Supabase CLI migration history drift (2026-05-22)

- **Symptom:** `supabase db push` → “Remote migration versions not found in local migrations directory” (remote IDs like `20260515073354` vs local `20260215180000_*`).
- **Cause:** Cloud history was applied via dashboard/MCP with different version stamps than repo filenames; schema already matches.
- **Fix:** Reset `supabase_migrations.schema_migrations` on cloud to the 19 local migration versions (bookkeeping only, no SQL re-run). Helper: `scripts/supabase/repair-migration-history.sh` for future drift via CLI.

## Supabase migration history repair (2026-05-26)

- **Symptom:** `db push` blocked on 35 MCP-only versions (`20260523035053` … `20260526050127`).
- **Fix (MCP `execute_sql` on `umivttszdnsrosbqryia`):** Deleted ghost rows; inserted 24 repo version stamps (schema already applied via MCP). Renamed duplicate `20260529160000_*orphans*` → `20260529161000_*`.
- **Result:** Remote `schema_migrations` = 43 rows, matches `supabase/migrations/*.sql`. `au_group_daily_creditor_report_rows` callable. CLI `db push` still prompts for DB password but should be a no-op.

## CI dummy PDF smoke tests (2026-05-22)

- **Gap:** Unit tests mocked `DocumentPipeline`; integration tests need live `.env` and are skipped in `ci-parser`.
- **Added:** `tests/test_api_dummy_pdf_smoke.py` — real PyMuPDF dummy PDFs (`pdf_fixtures.py`), fake S3 download + in-memory Supabase (`fake_supabase.py`). Covers health, auth, parse/*, extract/*, review-queue, jobs.
- **CI:** `ci-parser.yml` runs `pytest -m smoke` after main suite.

## SYS-01B no-Code workflow JSON (2026-05-24)

- **Artifact:** `workflows/pulled/au-group-sys-01b-pacer-nightly-poll-no-code.json` — same lanes as Code version but uses Schedule/HTTP/Supabase/Set/IF/Merge/SplitInBatches/Execute Workflow/Slack/Wait only.
- **RPC via HTTP Request** (not Code): `au_group_acquire_processing_job`, `au_group_upsert_docket_entries`; requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in n8n env.
- **SYS-00** sub-flow `hgXbSiTY7o7q5yPW` may still contain Code for PACER pagination — refactor SYS-00 separately for full no-Code stack.
- **Spec:** `docs/workflows/sys-01b-pacer-nightly-poll.md`
- **Canvas layout (2026-05-24):** `scripts/n8n/beautify-sys01b-layout.mjs` pushed SYS-06-style lane stickies + left→right flow to cloud `3qtDRBJtKrFUXqhH`; renamed **AU Group - SYS-01B - PACER Nightly Poll**.
- **Load Poll Candidates fix (2026-05-24):** Empty `[]` was RLS — HTTP credential used publishable key without `Authorization: Bearer` service_role. Fixed via `scripts/n8n/fix-sys01b-load-poll-candidates.mjs` (full URL + both headers; Config supabase reads `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`).
- **SYS-00 no-Code (2026-05-24):** Replaced `Normalize Input` + `Fetch PACER Docket` Code nodes with Set/IF/HTTP Request (pagination)/Aggregate on cloud `hgXbSiTY7o7q5yPW`. Artifact `workflows/pulled/au-group-sys-00-get-docket-no-code.json`; push `scripts/n8n/push-sys00-get-docket-no-code.mjs`; spec `docs/workflows/sys-00-get-docket.md`.

## SYS-04 full redesign JSON (2026-05-25)

- **Artifact:** `docs/workflows/au-group-sys-04-salesforce-push-redesign.json` (53 nodes, **0 Code nodes**)
- **Generate:** `node scripts/n8n/transform-sys04-no-code.mjs`
- **Push:** `node scripts/n8n/push-sys04-redesign.mjs`
- **Spec:** `docs/workflows/sys-04-salesforce-push.md`
- **Migrations:** `20260525160000_au_group_upsert_salesforce_account_rpc.sql`, `20260525170000_au_group_list_company_creditors_rpc.sql`
- **Node types:** Set, IF, HTTP Request, Supabase, Merge, Execute Workflow — Salesforce via **6 HTTP nodes** + `salesforceOAuth2Api` credential
- **Post-push:** attach OAuth2 on all `SF *` HTTP nodes; env `SUPABASE_*`, `SF_INSTANCE_URL`, `SYS04_DRY_RUN`

## SYS-04 Upsert RLS 42501 fix (2026-05-25)

- **Symptom:** `Upsert Salesforce Account` HTTP POST → `42501` RLS on `salesforce_accounts`.
- **Cause:** `httpHeaderAuth` credential `[ AU Group ] - supabase API Key - use for testing` sends **publishable/anon** JWT; table has RLS enabled (no public write policies).
- **Fix:** `scripts/n8n/fix-sys04-upsert-service-role.mjs --push` — Upsert uses `apikey` + `Authorization: Bearer` with `$env.SUPABASE_SERVICE_ROLE_KEY`; URL from `$env.SUPABASE_URL`. Same for `Acquire Processing Job` (uses `$json.service_role` from `Config supabase`). Config node assignments now read env vars, not hardcoded keys.
- **Required n8n env:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (already used by `Update Case Status`).

## SYS-04 Salesforce Push — no-Code chain (2026-05-25)

- **Scope:** Replace Code nodes `Account Match Or Create` → `Territory Owner` → `Log Bankruptcy Event` → `Check Gates` on workflow `YWmFi1GkJqJMB8bJ`.
- **Approach:** **Set** nodes (v3.4) with expression assignments; creditor context from `$('Loop Creditors').item.json` (fixes prior bug where `$input` after `Get Zoom Contacts` was only a contact row).
- **Artifact:** `workflows/pulled/au-group-sys-04-salesforce-push-no-code.json`; deploy `node scripts/n8n/patch-sys04-no-code.mjs --push`.
- **Still Code in SYS-04:** handoff/expand/aggregate/flag nodes — out of scope for this pass.

## SYS-03 Creditor Enrichment redesign (2026-05-23)

- **Scope:** PRD FR-4 (AU_GROUP-4) on workflow `j26cimQ4S7kN67IP`.
- **Deployed:** `scripts/n8n/patch-sys03-workflow.mjs --push` — single Code node `ZoomInfo Enrich Company` (company search → tier from firmographics → contact search with tier 1→2→3 fallback).
- **Wiring fixes:** `Loop Creditors` done → `Aggregate Enrichment`; all per-creditor branches loop back; `Prepare SYS-04 Input` → `Execute SYS-04`; removed broken `Edit Fields` nodes; Complete/Pipeline nodes use `$json.*` not `Skip No Creditors` refs.
- **Summary metrics:** per-creditor dedupe in aggregate; added `zoominfo_company_matched`, `no_contact_found`, `errors`.
- **Not in this pass:** ZoomInfo Redis cache (NFR-8.2), YAML/DB-configurable tier rules, 429 batching, production credential validation on contact search endpoint shape.
- **Aggregate fix (2026-05-23):** `$('Skip Individual').all()` throws when that branch never ran (all companies). **Final fix:** loop-end nodes push to `$getWorkflowStaticData('global').enrichResults`; Aggregate reads static data only (no cross-node `.all()`). Reset array in `Attach Job Context`. Prune duplicate canvas copies (`*1` node names). Fix wrong refs like `Merge Bankruptcy Context1`.

## SYS-04 Salesforce — no `$env` secrets (2026-05-23)

- **Security:** Removed `$env.SALESFORCE_ACCESS_TOKEN` / `$env.SALESFORCE_INSTANCE_URL` from `Account Match Or Create` Set expressions. Salesforce auth must use **n8n credentials** (or AWS Secrets via a dedicated node), never workflow env vars that leak in execution logs.
- **Dry run:** Only `dry_run` on the loop item (from handoff / Expand). When true → `DRY_{creditor_id}` stub + `sf_action: dry_run`. When false and no existing account → `salesforce_account_id: null`, `sf_action: pending_salesforce` until KD-53 wires the SF node.
- **Deployed:** `scripts/n8n/patch-sys04-no-code.mjs --push` on `YWmFi1GkJqJMB8bJ`.
- **MATCH node (2026-05-23):** Zoom fields use `$input` (not `$('Get Zoom Contacts')`); removed `?.` optional chaining; `Get Zoom Contacts` has `alwaysOutputData` so MATCH runs with zero contacts; `dry_run` typed boolean.

## SYS-04 handoff + credentials (2026-05-23)

- **No `$env`:** Supabase RPC/REST uses hardcoded project REST base + **AU Group Supabase Service Role** `httpHeaderAuth` credential (not workflow env). Salesforce HTTP uses **salesforceOAuth2Api** + `$credentials.salesforceOAuth2Api.instanceUrl` (no `SF_INSTANCE_URL` env).
- **SYS-03 handoff shape:** `enrichment_summary`, `schedule_f_queue_id`, `parent_processing_job_id`, `case_number`, `debtor_name`, `pipeline_execution_id` (upstream trace only). Normalize unwraps `[{...}]` arrays. `dry_run` only when `dry_run === true` on input.
- **Pipeline id:** Loop/complete use `$('Pipeline Started').first().json.id` (new SYS-04 row), not upstream `pipeline_execution_id` from handoff.
- **Artifact:** `docs/workflows/au-group-sys-04-salesforce-push-redesign.json`, `scripts/n8n/patch-sys04-handoff-no-env.mjs`. `transform-sys04-no-code.mjs` blocked unless `--force-legacy-regen` (old template still had `$env`).
- **pinData:** Sample handoff for case `26-15850` / `Anissa Hayes-Bryant` on `SYS-04 Trigger`.

## SYS-04 PGRST202 `au_group_count_company_creditors` (2026-05-23)

- **Cause:** RPC not deployed on `umivttszdnsrosbqryia`; first apply failed because migration used `bc.claim_amount` but `claim_amount` lives on `creditors` (`c.claim_amount`).
- **Fix:** Corrected `20260525170000_au_group_list_company_creditors_rpc.sql`; applied to remote via Supabase MCP. Both `au_group_count_company_creditors` and `au_group_list_company_creditors` now in schema.
- **n8n:** Cloud node still references `Merge Bankruptcy Context1` — rename to `Merge Bankruptcy Context` or re-import redesign JSON.

## SYS-04 loop read-before-write (2026-05-23)

- **Design:** `Load SF Map` = READ `salesforce_accounts` at loop start (dedup). `Upsert SF Map` = WRITE only after real Salesforce Id (not dry_run, not `DRY_*`).
- **Cloud bug:** `Get a row` replaced `Load SF Map` but `Merge Loop + SF Map` still calls `$('Load SF Map')` → cache always empty.
- **Junk creditors:** RPC filter tightened (`mailing address|email address` substring, exclude `contact`); applied remote `au_group_company_creditors_junk_filter`.
- **Doc:** `docs/workflows/sys-04-loop-and-supabase-map.md`

## SYS-04 full redesign push (2026-05-25)

- **Artifacts:** `scripts/n8n/build-sys04-workflow.mjs`, `scripts/n8n/push-sys04-workflow.mjs`, `docs/workflows/au-group-sys-04-salesforce-push.json`
- **Deployed:** `node scripts/n8n/push-sys04-workflow.mjs` → https://automationarchitecture.app.n8n.cloud/workflow/YWmFi1GkJqJMB8bJ
- **Fixes:** 49 nodes, 0 Code, **0 Merge nodes** (IF branches multi-wire instead of append merge — fixes hang); `Load SF Map`; `Upsert SF Map` after SF push; no `$env`
- **Merge fix (2026-05-25):** Removed `Merge Dry / SF`, `Merge SF Account Branches`, `Merge Loop End` — append mode waited for branches that never run.
- **Canvas layout (2026-05-25):** `LAYOUT` map in `build-sys04-workflow.mjs` — 4 color sticky zones (Handoff / Job / Loop / Finalize); main flow L→R; SF ladder below loop; skip branch above `Has Creditors?`.

## SYS-04 `bankruptcy_case_status` RLS 42501 (2026-05-25)

- **Symptom:** `Update Case Status` RPC → `42501` new row violates row-level security policy for table `bankruptcy_case_status`.
- **Cause:** `au_group_upsert_case_status` was `security invoker`; n8n `httpHeaderAuth` credential often uses publishable/anon key → insert runs as anon → RLS deny.
- **Fix:** `20260525180000_au_group_upsert_case_status_security_definer.sql` — `security definer` + `p_bankruptcy_id` guard; applied remote `umivttszdnsrosbqryia`.
- **Still required:** HTTP credential must send **service_role** as Bearer (same as other Supabase RPC nodes). Prefer credential **AU Group Supabase Service Role**, not publishable-only test key.
- **Ops:** Re-attach **Salesforce OAuth2** on SF HTTP nodes if missing after push; restore error workflow in UI if needed (API strips `errorWorkflow` on PUT)

## SYS-00 Get Docket redesign + cloud push (2026-05-25)

- **Target:** `5WG5YykOvLYxCOFN` — https://automationarchitecture.app.n8n.cloud/workflow/5WG5YykOvLYxCOFN
- **Change:** Removed embedded SYS-01B nightly poll (22 → 7 nodes). Sub-flow only: trigger → normalize → fetch PACER.
- **Artifact:** `workflows/pulled/au-group-sys-00-get-docket.json`, `scripts/n8n/push-sys00-get-docket.mjs`, `docs/workflows/sys-00-get-docket.md`, `workflows/lib/pacer-fetch-docket.js`
- **Callers updated:** SYS-01B `3qtDRBJtKrFUXqhH`, SYS-06 `gGRp6dF85A015TMH` → Execute `5WG5YykOvLYxCOFN`. Workflow **activated** on cloud (required for sub-workflow references).
- **Ops:** Re-attach **HTTP Basic Auth** on **Fetch PACER Docket Pages** in n8n UI if missing after push.
- **SYS-00 no-Code (2026-05-23):** Replaced Code nodes with Set / IF / HTTP Request (pagination). Push: `node scripts/n8n/push-sys00-get-docket.mjs`. Spec: `docs/workflows/sys-00-get-docket.md`.
- **Legacy:** `hgXbSiTY7o7q5yPW` old duplicate — archive in n8n UI when convenient.

## SYS-01B PACER Nightly Poll workflow JSON (2026-05-24)

- **Deliverables:** `workflows/pulled/au-group-sys-01b-pacer-nightly-poll.json` (orchestrator), cleaned `au-group-sys-00-get-docket.json` (sub-flow only), `docs/workflows/sys-01b-pacer-nightly-poll.md`.
- **Design:** 02:00 ET cron → cap cases → `pacer_poll` acquire → Execute `5WG5YykOvLYxCOFN` (SYS-00) → `au_group_upsert_docket_entries` → `last_docket_check_at` → job complete/fail. No SYS-02/03/04.
- **Migration:** `20260524120000_au_group_upsert_docket_entries_rpc.sql` — `au_group_upsert_docket_entries(p_bankruptcy_id, p_entries)` applied to Supabase `umivttszdnsrosbqryia` (2026-05-25). PGRST202 before apply = RPC missing on remote, not n8n body shape.

## SYS-06 ↔ SYS-07 linkage fix (2026-05-23)

- **Problem:** SYS-06 triggered `Sm45TsSpCR0LDo3l` but Execute Workflow Trigger fed **List Favorites** (dropped handoff payload). Active duplicate `4gJCImKNTC6WJ3aj` polled `status=detected` while SYS-06 sets `pending_approval`. Sm45 used stub `Load Pending` (`approved: true` always).
- **Fix:** Merged hourly logic from `4gJC` into `Sm45TsSpCR0LDo3l`; deactivated `4gJCImKNTC6WJ3aj`. Handoff branch: **Normalize SYS-06 Handoff** → **Log SYS-06 Handoff** (no PACER overwrite). Hourly: favorites → load `pending_approval` → **Get Bankruptcy** → **Merge Queue Context** → Diff → approve/reject → S3 → **Prepare Parse Payload** → **Run Document Parser** (`qwVPSlI3L1RMsw9V`). Diff: empty favorites list → **not** auto-approve.
- **SYS-06:** Explicit `workflowInputs` (6 fields); `continueOnFail: false`; removed **Merge Scan Branches** (append hang risk) — branches wire directly to **Log Pipeline Execution**.
- **Push:** `node scripts/n8n/push-sys06-sys07-linkage.mjs` (unarchives Sm45 if needed). Artifacts: `workflows/pulled/au-group-sys-06-schedule-f-detect.json`, `au-group-sys-07-schedule-f-processor.json`.
- **Still TODO (FR-2.4):** Real PACER favorites add/list API; do not activate SYS-06/07 in prod until PACER stubs replaced.
- **Two SYS-07 in n8n UI:** Only **`Sm45TsSpCR0LDo3l`** is canonical. Duplicate **`4gJCImKNTC6WJ3aj`** was deactivated; archive it so the folder shows one workflow: `node scripts/n8n/archive-sys07-duplicate.mjs`.

## Architect audit follow-ups (2026-05-22)

- **`SUPABASE_HTTP_TIMEOUT_SEC`** in `Settings` (default 60s); `SupabaseClient` uses it for REST/RPC/count.
- **`_backfill_creditor_merge`:** success logs `creditor_count` + `confidence_score`; failures log `exc_info` and creditor count.
- **Tests:** unit tests in `test_pipeline_robustness.py`; smoke `test_parse_document_creditor_matrix_cache_triggers_merge_backfill` (second parse without `force` asserts merge on cache hit).
- **`FakeSupabaseClient`:** hash-keyed `upsert_document` + `merge_creditors_call_count` for smoke assertions.

## MVP missing-systems deploy (2026-05-25)

**Scope:** Plan waves 0–5 — PACER, favorites, territory, SF/outreach, Schedule F, historical, daily summary.

### Delivered

| Wave | Artifacts |
|------|-----------|
| 0 | `scripts/n8n/deploy-mvp.mjs`; SYS-00 PACER cred on cloud; legacy `hgXbSiTY7o7q5yPW` deactivated |
| 1 | SYS-06 **Add PACER Favorite Report**; SYS-07 **List PACER Favorites Reports**; `docs/workflows/sys-07-pacer-favorites.md` |
| 2A | `docs/salesforce-mvp-setup.md` (Keith SF admin checklist) |
| 2B | Migration `20260526110000_au_group_territory_assignments.sql`; SYS-00 Territory → RPC; `docs/salesforce-territories.md` |
| 2C–D | SYS-04 → SYS-05 handoff fields; SYS-05 real **Check Gates** (not always dry_run) |
| 3 | SYS-07 parse target `7IjPc44k9YaCrmXM` |
| 4 | Migrations exposure/historical; **SYS-08** `14CyXpHYXAadAfuQ`; `docs/data/historical-import-mapping.md` |
| 5 | **SYS-09** `UVv5VGxOHq8p5S27`; `au_group_daily_pipeline_summary` RPC; `au_group_daily_creditor_report_rows` RPC + sheet wiring (`docs/workflows/sys-09-daily-creditor-sheet.md`); **SYS-99** activated + errorWorkflow on pipeline WFs |
| Repo | 14 workflow JSON in `workflows/pulled/`; `scripts/n8n/pull-folder-workflows.sh` |

### Deploy commands

```bash
node scripts/n8n/deploy-mvp.mjs --wave=all --push
node scripts/n8n/push-aux-workflows.mjs --push
supabase db push   # local; remote applied via MCP 2026-05-25
```

### Ops follow-ups (not automated)

- Replace `005PLACEHOLDER*` Salesforce User IDs in `au_group_territory_assignments`
- Keith: SF custom objects per `docs/salesforce-mvp-setup.md`
- Set n8n env `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` on SYS-08/09 HTTP nodes (service role credential)
- Manual AC-2.4 favorites test with real PACER account
- Confirm `SYS04_DRY_RUN` unset/false for live Salesforce push

## KD-14 + KD-11 config (2026-05-28)

**KD-14 target states**

- Migrations: `20260528100000_au_group_target_states.sql` — table + `au_group_list_target_states`, `au_group_is_target_state`, `au_group_list_pacer_poll_candidates`, `au_group_config_audit`.
- Seed: NY, NJ, PA, FL, MI. Applied to remote `umivttszdnsrosbqryia`.
- **SYS-01B:** `Load Poll Candidates` RPC + `Expand Poll Candidates`; `Config supabase` uses `$env.SUPABASE_URL` only; poll limit from env or `au_group_runtime_config` (no `|| 20` in workflow).
- **SYS-01 RSS:** Set/IF/HTTP/Merge chain (`Set Normalize Court Id` → court RPC → target-state RPC → `Merge Court Context`) → `Target State Active?`; no Code node for court routing.
- **SYS-01B:** `Load Poll Candidates` → `Has Poll Cases` directly (`alwaysOutputData`); removed Expand Code node.
- **SYS-04:** Territory via Set/IF/HTTP/Merge (same pattern as SYS-00); removed Resolve Territory Rep Code node.
- **SYS-09:** `Set Slack Message` + Split Out/Set for sheet rows; `Config supabase` uses `$env.SUPABASE_URL` only.
- **Canvas layout:** `scripts/n8n/beautify-workflows.py` — aligned KD-14/11/SYS-09 nodes + sticky notes (repo only, not pushed to n8n cloud).
- **Connection audit (2026-05-29):** Removed dual-wire Merge pattern (Set→IF+Merge input 0; 3× input 1). Replaced with single **Combine * Output** Set (`raw` JSON + `Object.assign` from anchor node) on SYS-00, SYS-01 court gate, SYS-04 territory. SYS-09 `Has Creditor Rows?` uses `row_count` only.
- **20260528130000:** `au_group_court_mappings`, `au_group_runtime_config`, `au_group_get_runtime_config`; SYS-02/04 HTTP URLs use `$env.SUPABASE_URL` only; territory nodes return `null` on failure (no `rep_default` in JS).

**KD-11 territory**

- `20260528110000_au_group_territory_seed_expand.sql` — 50-state seed + PA/MI.
- `20260528120000_au_group_list_company_creditors_creditor_state.sql` — `creditor_state` (address parse, fallback `bankruptcies.state`) per FR-5.3.
- **SYS-04:** inline **Resolve Territory Rep** Code node (RPC) after `Merge Loop + SF Map`; dry-run `territory_rep` from RPC (not hardcoded Keith).
- Docs: `docs/salesforce-territories.md`, `docs/salesforce-mvp-setup.md`, `docs/data/territory-seed-template.csv`.

**Deploy**

- Push pulled JSON to n8n cloud: SYS-01B `3qtDRBJtKrFUXqhH`, SYS-01, SYS-04 `YWmFi1GkJqJMB8bJ`.
- n8n env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `SYS01B_MAX_CASES_PER_RUN`.

## Creditor name junk filter (2026-05-27)

- **Symptom:** `creditors.name` contained Form 204 labels (`email address of creditor`), line numbers (`19`), `contact` — parser treated table column 0 / form fields as names.
- **Fix:** `is_junk_creditor_name()` in `app/validation/creditor_name_quality.py` (shared by parser + validation); filter at extract + smarter table column pick; `validate_creditor_matrix` flags empty/invalid sets; migrations `20260527120000_*` + `20260527130000_*_sync` skip junk at `au_group_merge_creditor_matrix`.
- **Review follow-up (2026-05-27):** Removed `holdings` from junk substring list (false-positive on "ABC Holdings LLC"); extracted shared module so validation does not import `fitz` via extractors.
- **Review follow-up (2026-05-29):** `au_group_is_junk_creditor_name()` — single SQL function for merge + SYS-04 read RPCs; thresholds from `au_group_runtime_config` keys `creditor_name_min_length` / `creditor_line_number_max_digits` (seeded in `291200`, `au_group_config_int` in `291600`); parser mirrors via Settings env vars (same key names, default 3).
- **Deploy:** Push document-parser to Railway; `supabase db push` or apply migration on `umivttszdnsrosbqryia`; re-parse affected cases or run cleanup migration.

## SYS-09 daily sheet — audit archive (2026-05-29)

**Waves 0–5 delivered:** `20260529150000_*` (jsonb wrapper + primary bankruptcy lateral), `20260529160000_*` (runtime config, pending status, zoominfo id RPC, orphan junk cleanup). Docs: `docs/workflows/sys-09-daily-creditor-sheet.md`, `docs/workflows/sys-03-zoominfo-company-id-rpc.md`. Test: `scripts/supabase/test-daily-creditor-report.sql`.

**Applied remote:** 291500 + 291600 on `umivttszdnsrosbqryia`. RPC returns `{since, row_count, rows}` — verified 2 rows in 7-day window.

**Enum fix:** `processing_jobs.status` on remote is `processing_job_status` (`queued`/`running`/`retrying`, not `pending`). `au_group_creditor_pipeline_status` uses `::text` casts.

**Still manual:** Pull SYS-03 → wire `au_group_set_creditor_zoominfo_company_id`; run SYS-09 manually; re-parse junk-linked bankruptcies via SYS-02.

**PR review (2026-05-29):** In `20260529160000_au_group_daily_report_runtime_config_and_fixes.sql` — `REVOKE EXECUTE … FROM public` after `GRANT` on new SECURITY DEFINER RPCs (`au_group_config_*`, `au_group_set_creditor_zoominfo_company_id`, `au_group_daily_creditor_report_rows`); restored orphan-inclusive `report_rows` (`left join lateral` per `291500`, not `inner join primary_bankruptcy`). Dropped duplicate-timestamp `20260529160000_au_group_daily_creditor_report_orphans.sql` (logic folded into `291600`). `au_group_creditor_pipeline_status` pending/failed checks now match jobs via `bankruptcy_creditors` **or** `creditors.source_bankruptcy_id` (same UNION as `report_rows`).

## Fix F0 — repo restore + cloud sync (2026-05-25)

- **Problem:** `scripts/n8n/lib/*.mjs`, SYS-08/09 pulled JSON, and workflow docs were **0 bytes** — deploy loop broken.
- **Fix:** Restored deploy scripts from agent transcript; `node scripts/n8n/deploy-mvp.mjs --pull`; pulled SYS-00/08/09 from cloud by ID.
- **Cloud:** Deactivated duplicate SYS-08 `6B5QzfEHCIwCHJ5U` (canonical `14CyXpHYXAadAfuQ`).
- **Repo:** Moved `au-group-sys-04-salesforce-push-redesign.json` → `workflows/archive/` (not on cloud).
- **SYS-07:** Hourly Poll now wires `List PACER Favorites Reports` (cloud); orphan `List Favorites Stub` connection entry remains — cleanup in F3.
- **Next:** Fix F1 — `creditor_outreach_disposition` migration + SYS-04/05 gate/disposition wiring.

## KD-40 — FR-3.5 Creditor fuzzy deduplication (2026-05-30)

- **Parser:** `app/dedup/creditors.py` — RapidFuzz `token_set_ratio` on normalized name+address; Union-Find clustering; default threshold **85** (`CREDITOR_DEDUP_THRESHOLD`, `creditor_dedup_enabled`).
- **Pipeline:** `DocumentPipeline._dedup_creditors_if_enabled` runs after extract / manual-review apply / merge backfill, **before** `validate_creditor_matrix` and `merge_creditors`.
- **Audit:** `CreditorRow.source_line_numbers`, `dedup_audit` json; `documents.raw_extraction.dedup_stats`; staging column `creditor_matrix_rows.source_line_numbers`; canonical `creditors.dedup_audit`.
- **Migration:** `20260530120000_kd40_creditor_dedup_audit.sql` — merge RPC sums `claim_amount` on conflict and merges dedup audit.
- **Tests:** `tests/test_deduplicate_creditors.py` (AC-3.5).
- **Audit fixes (2026-05-27):** Removed extractor name-only pre-filter (`creditor_matrix.py`); cache hit returns `_with_deduped_creditors` after backfill; `creditor_dedup_threshold` validated 50–100; `dedup_audit` only when `len(group) > 1`.
- **Audit follow-up (2026-05-27):** Intentional deviation from PRD “name-only” wording — match key is **name+address** (documented in PRD § FR-3.5 + AC-3.5). Cache hit upserts `raw_extraction.creditors` + `dedup_stats` via `_sync_cached_matrix_raw_extraction`. Job status uses `_raw_with_deduped_creditors`. Smoke/API tests assert deduped creditors, `dedup_stats`, and `last_merge_creditors` carries `dedup_audit` / `source_line_numbers`.
- **Code review fix (2026-05-27):** `raw_extraction.creditors_merged` set after successful `merge_creditors`; `_backfill_creditor_merge` skips when flag is true (prevents cache-hit claim_amount double-sum). RPC `dedup_audit` merge includes `duplicate_count`. Remote DBs that already applied `20260530120000` need `CREATE OR REPLACE` on `au_group_merge_creditor_matrix` if `duplicate_count` merge fix is required (re-run migration body or MCP patch).
- **Copilot PR fixes (2026-05-27):** `_dedup_creditors_if_enabled(..., log=True)` only on write paths (parse/apply/cache sync); read paths (`_with_deduped_creditors`, `_raw_with_deduped_creditors`) stay silent. Migration: `source_line_numbers` merge filters `^\d+$` before cast; `duplicate_count` = `jsonb_array_length(merged_names)`. Removed committed `coverage.json`; added to `.gitignore`.
- **n8n:** No workflow change — SYS-02 still calls parser; dedup is server-side.
- **Deploy:** Apply Supabase migration on remote; redeploy Railway document-parser; KD-36 Schedule E/F extractor can add line numbers using same `source_line_numbers` pattern later.
- **Remote migration history (2026-05-27):** Schema already live (`source_line_numbers`, `dedup_audit`, merge RPC). MCP applied as `20260527082541_kd40_creditor_dedup_audit`; repo file is `20260530120000_kd40_creditor_dedup_audit.sql`. Repaired remote `schema_migrations` with version `20260530120000` so `supabase db push` does not re-apply DDL. Prefer **Supabase MCP `apply_migration`** when CLI `db push` hangs (no `.supabase` link / interactive password).
- **Phase 0 ship checklist (architect plan, 2026-05-27):**
  1. Commit: `app/dedup/`, migration `20260530120000_kd40_creditor_dedup_audit.sql`, dedup tests (exclude `.coverage`).
  2. Remote: confirm columns + `au_group_merge_creditor_matrix`; patch RPC if `duplicate_count` merge missing.
  3. Railway: redeploy document-parser.
  4. Smoke: matrix PDF + `force=true` → `dedup_stats`, merged ABC row, `creditors_merged` in raw.
  5. Jira: mark AU_GROUP-3.4 Done (CloudWatch metric stays deferred).
- **Phase 3 prep (2026-05-27):** `app/pipeline/filing_types.py` — `is_creditor_list_filing()` for CREDITOR_MATRIX + SCHEDULE; router dedup/cache paths use it. Extraction still matrix-only until AU_GROUP-3.1 `parse_schedule_ef`.
- **Phase 2 (2026-05-27):** `parse_schedule_ef` in `schedules.py` (table headers + text/numbered fallbacks); `router.py` SCHEDULE branch + dedup; manual review apply uses `is_creditor_list_filing`. FR-3.1 extra fields (claim date, nature, flags) still deferred — CreditorRow has name/address/amount only.

## KD-38 — OCR manual review (Sheet + n8n + API) (2026-05-26)

- **Parser API:** `validate_creditor_matrix(..., ocr_used, ocr_confidence)` gates low OCR confidence; `review_reason` prefixed with `low_priority` when page OCR below threshold. `POST /api/v1/review/{review_id}/apply` supports **creditor matrix** or **Form 201** (`ApplyReviewRequest` exactly one of `creditors` / `form201`).
- **Tests:** `tests/test_validation.py`, `tests/test_api_review.py` (matrix + form201 apply).
- **n8n:** `workflows/pulled/au-group-sys-02-parse-doc.json` — child parse + job poll. Parent SYS-02 **Manual Review?** stops before SYS-03.
- **n8n KD-38 (audit fixes):** `au-group-sys-38-ocr-manual-review.json` — **no Code nodes** (Split Out, Merge, Filter, Set, HTTP, IF). Sync-out: parallel read Sheet + GET queue → merge by `review_id` → filter Pending/new → GET job → upsert. Sync-in: filter Approved/Rejected → apply/resolve branches → SYS-03. Manual Run = sync-out only.
- **Sheet spec:** `docs/workflows/kd-38-manual-review-sheet.md` — columns `ocr_text_preview`, `corrected_form201_json`.
- **Deploy (manual):** Railway parser deploy; import SYS-38 + parse-doc to n8n; env `MANUAL_REVIEW_SHEET_DOCUMENT_ID`, `PARSER_URL`, `DOCUMENT_PARSER_API_KEY`; E2E one bankruptcy row before Jira Done.

## SYS-01 RSS — canvas sticky notes (2026-05-26)

- **File:** `workflows/pulled/au-group-sys-01-rss-intelligence.json`
- **Lanes documented:** RSS ingest, parse/qualify, KD-14 target-state gate, dedup/insert, SYS-02 queue.
- **Wiring aligned with cloud paste:** `court_id_norm` on **Edit Fields**; removed **Set Normalize Court Id** from path; **Config supabase** (`$env.SUPABASE_URL` + `/rest/v1/`) before court/target RPCs; **Combine Court Gate** merges from **Edit Fields**.
- **Not copied:** large `pinData` test fixture from n8n UI (keeps repo diff small); re-pin in editor if needed.
