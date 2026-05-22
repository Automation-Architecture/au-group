# CI on every pull request

## Behaviour

Workflow [`ci.yml`](../../.github/workflows/ci.yml) runs on **every** pull request:

- Event types: `opened`, `synchronize`, `reopened`, `ready_for_review`
- No `branches:` filter on `pull_request` (PRs into `main`, `develop`, `feat/*`, etc.)
- On PRs, **all** jobs run (parser, integration, supabase, playwright, export, security) — path filters apply only to `push` events

Required gate: job **`CI / all-green`**.

## GitHub limitation (important)

`pull_request` workflows are loaded from the **base branch** of the PR (e.g. `main`), not from the PR head branch.

| Base branch has `ci.yml`? | What runs on the PR |
|---------------------------|---------------------|
| No (only `copilot-review.yml`) | Copilot review only |
| Yes (full `.github/workflows/`) | Copilot + full **CI** |

So the first PR that **introduces** `ci.yml` will not run CI until those workflow files are on the target branch. Fix:

1. Merge `.github/workflows/` (and `.github/actions/`) into `main` (can be a small PR that only adds CI), **or**
2. Push to `feat/**` and confirm runs under **Actions → CI** (push uses workflows on the pushed branch)

After `ci.yml` is on `main`, every new PR gets the full suite automatically.

## Checks vs Actions

- **Copilot Code Review** — [`copilot-review.yml`](../../.github/workflows/copilot-review.yml) on `main` (org policy)
- **CI** — `ci.yml` orchestrator + reusable workflows

Both can appear on the same PR once CI is on `main`.
