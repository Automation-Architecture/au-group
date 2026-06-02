# Rollback procedures (AU_GROUP-8.2.2)

Target: restore last known-good state in **under 5 minutes** for parser; n8n/Supabase may take longer.

## Document parser (Railway) — primary

1. Open [Railway dashboard](https://railway.app) → project **au-group** → service **document-parser**.
2. **Deployments** → select previous successful deployment → **Rollback**.
3. Verify:
   ```bash
   curl -fsS "${PARSER_PRODUCTION_URL}/health"
   curl -fsS "${PARSER_PRODUCTION_URL}/health/ready"
   ```
4. If n8n still errors, confirm `API_KEY` in Railway matches n8n credential (no rollback needed for key drift).

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
2. Confirm workflow `qwVPSlI3L1RMsw9V` (SYS-02) is active in the n8n UI.

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
