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

1. Revert the workflow JSON commit in git (`workflows/*.json`).
2. Merge to `main` (triggers `deploy-n8n.yml`) **or** run locally:
   ```bash
   export N8N_BASE_URL=... N8N_API_KEY=...
   ./scripts/n8n/deploy-workflows.sh
   ```
3. Confirm workflow `qwVPSlI3L1RMsw9V` (SYS-02) is active in n8n UI.

## Supabase migrations

**Forward-only in production.** Rollback = new migration that reverses the change, then:

```bash
supabase link --project-ref "$SUPABASE_PROJECT_REF"
supabase db push --linked
```

Do **not** delete migration files already applied to production.

## Smoke verification after rollback

Run **Smoke E2E** workflow (`workflow_dispatch`) or wait for `workflow_run` hook after deploy.

## Incident log

Record in Jira **KD** / AU_GROUP-8: time, SHA reverted, owner, root cause link.
