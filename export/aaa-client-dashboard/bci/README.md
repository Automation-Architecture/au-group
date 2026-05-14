# BCI client — AAA dashboard transfer package

Apply these files into the **AAA client dashboard** mono-repo (the app deployed to `dashboard.automationarchitecture.ai`). Paths follow [references/step-13-client-dashboard.md](../../references/step-13-client-dashboard.md).

## Source of truth in `au-group`

| Input | Path |
|--------|------|
| Operator config | [project.config.yaml](../../project.config.yaml) (`slug: bci`, `jira_project_key: KD`) |
| Content spec | [client-dashboard.md](../../client-dashboard.md) |
| Jira board | [KD board](https://automationarchitecture.atlassian.net/jira/software/projects/KD/boards/451) |

## Copy map

| This package | Target in dashboard repo |
|--------------|---------------------------|
| [patches/clients.bci.ts.snippet](patches/clients.bci.ts.snippet) | Merge into `app/src/app/config/clients.ts` (append `bci` entry; align field names to existing `Client` / config type) |
| [data/*.json](data/) | `app/src/app/client/data/bci/` (same five filenames as step-13) |
| [patches/sync-jira-workflow-step.yml](patches/sync-jira-workflow-step.yml) | Append the step to `.github/workflows/sync-jira-data.yml` (or equivalent) |
| [seed/railway-stages.placeholder.sql](seed/railway-stages.placeholder.sql) | Run in Railway Postgres after reconciling table/column names with your real schema (replace placeholders) |

## Jira sync command

```bash
python scripts/sync_jira.py --slug bci --project-key KD
```

Secrets (repo): `JIRA_BASE_URL` (typically `https://automationarchitecture.atlassian.net`), `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`.

## GitHub activity

This package sets **`Automation-Architecture/au-group`** as the docs / discovery repo for activity until a dedicated application repo exists. Update `github_activity.json` and the client config if you switch to another repo.

## Verify

After deploy: `https://dashboard.automationarchitecture.ai/client/bci` should return **200** (not 404).
