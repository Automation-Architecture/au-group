#!/usr/bin/env bash
# Optional Cursor autofix — disabled unless AUTOFIX_CURSOR_ENABLED=true. Same-repo + allowlist commit only.
set -euo pipefail

PR_NUMBER="${1:?PR number required}"
REPO="${2:?owner/repo required}"
BRANCH="${3:?branch required}"

if [ "${AUTOFIX_CURSOR_ENABLED:-false}" != "true" ]; then
  echo "AUTOFIX_CURSOR_ENABLED is not true — skip Cursor autofix"
  exit 0
fi

if [ -z "${CURSOR_API_KEY:-}" ]; then
  echo "CURSOR_API_KEY not set — skip Cursor autofix"
  exit 0
fi

if [ "${AUTOFIX_COMMENTS_ONLY:-false}" = "true" ]; then
  echo "Fork/comments-only mode — skip Cursor autofix"
  exit 0
fi

if ! command -v node >/dev/null 2>&1; then
  echo "::warning::Node.js required for Cursor autofix"
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REVIEW_BOTS="${REVIEW_BOTS:-[]}"
COMMENTS_FILE="$(mktemp)"
trap 'rm -f "${COMMENTS_FILE}"' EXIT

# Strict bot allowlist (same as workflow)
gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" --paginate \
  --jq --argjson bots "${REVIEW_BOTS}" \
  '.[] | select(.user.login as $u | $bots | index($u)) | "--- \(.path // "general"):\n\(.body)\n"' \
  > "${COMMENTS_FILE}" 2>/dev/null || true

if [ ! -s "${COMMENTS_FILE}" ]; then
  gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" --paginate \
    --jq --argjson bots "${REVIEW_BOTS}" \
    '.[] | select(.user.login as $u | $bots | index($u)) | "--- review:\n\(.body // "")\n"' \
    >> "${COMMENTS_FILE}" 2>/dev/null || true
fi

# Cap prompt size to reduce injection surface (~24KB)
if [ -s "${COMMENTS_FILE}" ]; then
  head -c 24000 "${COMMENTS_FILE}" > "${COMMENTS_FILE}.trim"
  mv "${COMMENTS_FILE}.trim" "${COMMENTS_FILE}"
fi

export AUTOFIX_PROMPT
AUTOFIX_PROMPT="$(cat <<EOF
You are fixing PR #${PR_NUMBER} in ${REPO} on branch ${BRANCH}.

RULES (mandatory):
- Only edit files under services/document-parser/ (app/ and tests/).
- Do NOT modify .github/, workflows/, supabase/, scripts/, or root config files.
- Do not add secrets, env files, or network exfiltration code.
- Do not merge the PR.

Review feedback:
$(cat "${COMMENTS_FILE}" 2>/dev/null || echo "(none)")
EOF
)"

# Pinned SDK (supply chain) — bump intentionally in scripts/ci/autofix-node-deps.json
CURSOR_SDK_VERSION="${CURSOR_SDK_VERSION:-1.0.0}"
export AUTOFIX_PROMPT CURSOR_API_KEY

node <<NODE
const { execSync } = require("child_process");
const prompt = process.env.AUTOFIX_PROMPT;
const apiKey = process.env.CURSOR_API_KEY;
const sdkVersion = process.env.CURSOR_SDK_VERSION || "1.0.0";
const root = process.cwd();

async function main() {
  try {
    execSync(\`npm install --no-save @cursor/sdk@\${sdkVersion}\`, { cwd: root, stdio: "pipe" });
  } catch {
    console.log("::warning::Could not install @cursor/sdk");
    return;
  }
  const { Agent } = await import("@cursor/sdk");
  const result = await Agent.prompt(prompt, {
    apiKey,
    model: { id: "composer-2" },
    local: { cwd: root },
  });
  console.log("Cursor agent status:", result.status);
}

main().catch((e) => console.log("::warning::Cursor autofix:", e.message));
NODE

chmod +x "${SCRIPT_DIR}/autofix-safe-commit.sh"
"${SCRIPT_DIR}/autofix-safe-commit.sh" \
  "chore(ci): cursor autofix from review comments" \
  "${BRANCH}"
