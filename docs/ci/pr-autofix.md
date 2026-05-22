# PR auto-fix (no auto-merge, hardened)

Automatically applies fixes when **CodeRabbit** or **Copilot** post new PR review comments. **Never merges.**

## Security controls

| Control | Behavior |
|---------|----------|
| Fork PRs | **Comments only** (`@coderabbitai fix`) — no checkout, push, or Cursor |
| Manual `/autofix` | **OWNER or MEMBER** only (not external COLLABORATOR) |
| Label `autofix` | Actor must have **write+** on repo (or listed in `AUTOFIX_ALLOWED_ACTORS`) |
| Git commit scope | **Only** `services/document-parser/` via [`autofix-safe-commit.sh`](../../scripts/ci/autofix-safe-commit.sh) |
| Blocked paths | `.github/`, `workflows/`, `supabase/`, `scripts/ci/`, `.env`, etc. |
| Cursor agent | **Off by default** — set repo variable `AUTOFIX_CURSOR_ENABLED=true` + secret `CURSOR_API_KEY` |
| Cursor SDK | Pinned `@cursor/sdk@1.0.0` (not `@latest`) |
| Bot allowlist | Exact logins only (workflow + cursor script) |

## Triggers (automatic)

| Event | When |
|-------|------|
| `pull_request_review_comment` created | Author ∈ review bot allowlist |
| `pull_request_review` submitted | Bot, state `commented` or `changes_requested` |

**Review bots:** `coderabbitai[bot]`, `coderabbit[bot]`, `copilot-pull-request-reviewer[bot]`, `github-copilot[bot]`

## Triggers (manual)

| Action | Who |
|--------|-----|
| Comment `/autofix` | OWNER or MEMBER |
| Label `autofix` | Write+ collaborator or `AUTOFIX_ALLOWED_ACTORS` |

## Repo variables (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTOFIX_CURSOR_ENABLED` | `false` | Enable Cursor agent step |
| `AUTOFIX_ALLOWED_ACTORS` | (empty) | Comma-separated GitHub logins allowed for label/manual |
| `INTEGRATION_CI_STRICT` | `false` | (separate) integration tests on PR |

## Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `GITHUB_TOKEN` | Built-in | Comments; push on same-repo PR only |
| `CURSOR_API_KEY` | Only if Cursor enabled | Agent autofix |

## What each run does

1. Gate + **security guard** (fork / actor)
2. Throttle (10 min / PR)
3. `@coderabbitai fix` (scoped instructions)
4. **Ruff** + allowlist commit (same-repo only)
5. **Cursor** (opt-in only)

## Merge policy

- No auto-merge
- CodeRabbit `auto_approve: false`
- Required: **CI `all-green`** + **human approval** + review bot commits in diff

## Files

- [`.github/workflows/pr-autofix.yml`](../../.github/workflows/pr-autofix.yml)
- [`scripts/ci/autofix-pr-guard.sh`](../../scripts/ci/autofix-pr-guard.sh)
- [`scripts/ci/autofix-safe-commit.sh`](../../scripts/ci/autofix-safe-commit.sh)
- [`scripts/ci/cursor-pr-autofix.sh`](../../scripts/ci/cursor-pr-autofix.sh)
- [`.coderabbit.yaml`](../../.coderabbit.yaml)
