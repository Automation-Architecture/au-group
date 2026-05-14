# AAA client dashboard — repository status

**Checked:** 2026-05-14 (via `gh api orgs/Automation-Architecture/repos`)

## Finding

The Next.js application that serves [dashboard.automationarchitecture.ai](https://dashboard.automationarchitecture.ai) is **not** present as a repository named `aaa-client-dashboard` (or similar) under the `Automation-Architecture` GitHub organization in the accessible org listing.

Repositories in that org at check time included: `au-group`, `aaa-discovery-template`, `aa-project-pipeline`, `aa-jira-fulfillment`, `aa-knowledge-base`, and others — none hosting the live client dashboard source.

## Implication

Steps that require editing `app/src/app/config/clients.ts`, `app/src/app/client/data/bci/`, or `.github/workflows/sync-jira-data.yml` **must run in whichever repo actually builds and deploys** the Vercel project behind `dashboard.automationarchitecture.ai`. That may be:

- A private repo under another org or account, or
- A name other than `aaa-client-dashboard`.

## What we shipped in `au-group` instead

Until that repo is identified, the **transfer package** at [export/aaa-client-dashboard/bci/README.md](../export/aaa-client-dashboard/bci/README.md) mirrors what `aaa-client-init` would add: client config snippet, five JSON data files (seeded from [client-dashboard.md](../client-dashboard.md)), Jira sync workflow step for project **KD**, and a placeholder Railway SQL file.

## Next action for operators

1. Locate the real dashboard repo (Vercel project settings → Git connection, or ask Brad / infra).
2. Copy the files from `export/aaa-client-dashboard/bci/` into the paths described in that README.
3. Merge, deploy, run Jira sync workflow, run Railway seed SQL (or rely on lazy-insert per step-13).

## Verification (automated check)

As of implementation, `GET https://dashboard.automationarchitecture.ai/client/bci` returned **404** (slug not registered in the deployed app yet). Reference client `GET .../client/kidneyhood` returned **200**. Re-run the same curl after merging the transfer package into the live dashboard repo.
