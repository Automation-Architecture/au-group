#!/usr/bin/env bash
# Security guard for pr-autofix: same-repo only, trusted actors on manual triggers.
set -euo pipefail

PR_NUMBER="${PR_NUMBER:?}"
REPO="${REPO:?}"
ACTOR="${ACTOR:?}"
TRIGGER_KIND="${TRIGGER_KIND:?}"  # bot | manual | label

can_push=true
comments_only=false
reason="ok"

IS_FORK=$(gh pr view "${PR_NUMBER}" --repo "${REPO}" --json isCrossRepository --jq '.isCrossRepository')
if [ "${IS_FORK}" = "true" ]; then
  can_push=false
  comments_only=true
  reason="fork PR — comments only, no checkout/push"
fi

is_allowed_actor() {
  if [ -n "${AUTOFIX_ALLOWED_ACTORS:-}" ]; then
    if echo ",${AUTOFIX_ALLOWED_ACTORS}," | grep -q ",${ACTOR},"; then
      return 0
    fi
  fi
  local owner perm
  owner=$(gh repo view "${REPO}" --json owner --jq '.owner.login')
  if [ "${ACTOR}" = "${owner}" ]; then
    return 0
  fi
  perm=$(gh api "repos/${REPO}/collaborators/${ACTOR}/permission" -q .permission 2>/dev/null || echo "none")
  case "${perm}" in
    admin|maintain|write) return 0 ;;
    *) return 1 ;;
  esac
}

case "${TRIGGER_KIND}" in
  manual|label)
    if ! is_allowed_actor; then
      echo "::error::Only repo maintainers (write+) or AUTOFIX_ALLOWED_ACTORS may trigger manual/label autofix"
      exit 1
    fi
    ;;
  bot)
    ;;
  *)
    echo "::error::unknown trigger kind: ${TRIGGER_KIND}"
    exit 1
    ;;
esac

{
  echo "can_push=${can_push}"
  echo "comments_only=${comments_only}"
  echo "reason=${reason}"
} >> "${GITHUB_OUTPUT:?}"

echo "Guard: can_push=${can_push} comments_only=${comments_only} (${reason})"
