#!/usr/bin/env bash
# Stage and commit only allowlisted paths; block sensitive repo areas. Never merges.
set -euo pipefail

COMMIT_MSG="${1:?commit message required}"
BRANCH="${2:?branch required}"

# Paths autofix may commit (parser only)
ALLOWLIST=(
  "services/document-parser"
)

# Never commit these prefixes even if present in working tree
BLOCKED_REGEX='^(\.github/|\.git|workflows/|supabase/|scripts/ci/|\.env|\.cursor/|\.vbsec)'

if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to commit"
  exit 0
fi

echo "Changed files before staging:"
git diff --name-only
git diff --cached --name-only 2>/dev/null || true

git add "${ALLOWLIST[@]}"

if git diff --cached --quiet; then
  echo "No allowlisted changes to commit"
  exit 0
fi

BLOCKED=$(git diff --cached --name-only | grep -E "${BLOCKED_REGEX}" || true)
if [ -n "${BLOCKED}" ]; then
  echo "::error::Autofix blocked — sensitive paths staged:"
  echo "${BLOCKED}"
  git reset HEAD
  exit 1
fi

echo "Staging allowlisted commit:"
git diff --cached --name-only

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git commit -m "${COMMIT_MSG}"
git push origin "HEAD:refs/heads/${BRANCH}"
