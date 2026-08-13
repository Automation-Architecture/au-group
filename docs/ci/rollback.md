# Rollback procedures (AU_GROUP-8.2.2)

Target: restore last known-good state in **under 5 minutes** for parser; n8n/Supabase may take longer.

## Document parser (Railway) — primary

1. Open [Railway dashboard](https://railway.app) → project **au-group-be** → service **au-group** (root `services/document-parser`).
2. **Deployments** → select previous successful deployment → **Rollback**.
3. Verify (`PARSER_PRODUCTION_URL` = `https://au-group-production.up.railway.app`):
   ```bash
   curl -fsS "${PARSER_PRODUCTION_URL}/health"
   curl -fsS "${PARSER_PRODUCTION_URL}/health/ready"
   ```
4. If n8n still errors, confirm `API_KEY` in Railway matches n8n credential (no rollback needed for key drift). The parser `API_KEY` was rotated on 2026-08-13.

> **Do not roll back past `a362fe3` (PR #121, 2026-08-13) without care.** Commits before that one carry a
> `[deploy]` block in `services/document-parser/railway.toml`; because that directory is the Railway root
> for four services (`au-group`, `pipeline-worker`, `daily-report`, `intake-cron`), the block overrides the
> cron services' start commands and crash-loops them on `RuntimeError: API_KEY environment variable is
> required`. Deploy settings now live per service instance in the Railway dashboard — see
> [`environments.md`](./environments.md).

## Document parser (EC2) — Phase 4

On the instance:

```bash
cd /opt/au-group
git fetch origin
git checkout <previous-sha>
cd services/document-parser
./scripts/deploy.sh
sudo systemctl status document-parser
```

Or run from CI: re-dispatch **Deploy document-parser (EC2)** after checking out a known-good tag locally and pushing a revert PR (preferred).

## n8n workflows

> n8n is in **parallel-run pending decommission** (the build target is the code-native pipeline — see CLAUDE.md "Current direction"). There is **no repo-based n8n deploy** — no `deploy-n8n.yml` workflow and no deploy script; workflows are managed directly in **n8n Cloud** (via the UI / n8n-MCP).

1. Restore the known-good workflow directly in **n8n Cloud** — use the workflow's **version history** in the n8n UI (or re-import a known-good export) via the UI / n8n-MCP. The workflow definitions are not deployed from this repo.
2. ~~Confirm workflow `qwVPSlI3L1RMsw9V` (SYS-02) is active in the n8n UI.~~

> **Correction (2026-08-13):** workflow `qwVPSlI3L1RMsw9V` is **"AU Group - SYS-02 - Bankruptcy Intelligence", and it is inactive AND archived** (verified via the n8n API; last updated 2026-05-20). Do not expect it to be active — an n8n rollback that "restores" it to active would re-enable an archived workflow. Across the whole instance only one parser-referencing workflow is active, and it is a sub-workflow with no active callers. Several AU Group workflows also point at the dead placeholder host `https://au-group.railway.app`. Treat this whole section as legacy: the live path is the code-native pipeline.

## Supabase migrations

**Forward-only in production.** Rollback = a new migration that reverses the change.

**Apply mechanism: Supabase MCP `apply_migration`** (NOT `supabase db push`). The repo migrations dir has
drifted from live and the `deploy-supabase.yml` `db push` job is disabled (`if: false`) — running `db push`
would regress live. See KD-74 and [`../architecture/supabase-live-schema-state.md`](../architecture/supabase-live-schema-state.md).

To reverse a change: write the corrective migration file in `supabase/migrations/`, apply it to the live
project (`umivttszdnsrosbqryia`) via MCP `apply_migration`, then verify with `execute_sql`. Do **not**
delete migration files already applied to production. Once KD-74 reconciles repo↔live, the `db push`
workflow path can be re-evaluated.

## Smoke verification after rollback

Run **Smoke E2E** workflow (`workflow_dispatch`) or wait for `workflow_run` hook after deploy.

## Incident log

Record in Jira **KD** / AU_GROUP-8: time, SHA reverted, owner, root cause link.
