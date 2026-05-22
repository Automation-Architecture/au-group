#!/usr/bin/env bash
# Install vbsec agent skill locally (full /vbs-scan-security — not CI).
# https://github.com/tanviet12/vbsec
set -euo pipefail

VBSEC_SRC="${VBSEC_SRC:-$HOME/vbsec}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "${VBSEC_SRC}/skills/vbs-scan-security" ]; then
  echo "Cloning vbsec to ${VBSEC_SRC}..."
  git clone https://github.com/tanviet12/vbsec.git "${VBSEC_SRC}"
fi

install_link() {
  local target="$1"
  local name="$2"
  mkdir -p "$(dirname "${target}")"
  ln -sfn "${VBSEC_SRC}/skills/vbs-scan-security" "${target}/${name}"
  echo "Linked ${target}/${name}"
}

# Cursor / Claude Code paths (best-effort)
install_link "${HOME}/.claude/skills" "vbs-scan-security" 2>/dev/null || true
install_link "${REPO_ROOT}/.claude/skills" "vbs-scan-security" 2>/dev/null || true

echo ""
echo "Full scan (agent): /vbs-scan-security lang=en"
echo "CI scan (deterministic): python3 scripts/ci/vbsec_ci_scan.py"
