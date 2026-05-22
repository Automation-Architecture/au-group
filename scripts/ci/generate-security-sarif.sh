#!/usr/bin/env bash
# Emit SARIF for GitHub Security tab (gitleaks + bandit). Non-fatal on tool warnings.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${ROOT}/vbsec-reports"
mkdir -p "${OUT_DIR}"

cd "${ROOT}"

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect \
    --source . \
    --report-format sarif \
    --report-path "${OUT_DIR}/gitleaks.sarif" \
    --no-banner \
    --redact || true
  if [ ! -s "${OUT_DIR}/gitleaks.sarif" ]; then
    echo '{"version":"2.1.0","$schema":"https://json.schemastore.org/sarif-2.1.0.json","runs":[]}' > "${OUT_DIR}/gitleaks.sarif"
  fi
else
  echo "::warning::gitleaks not installed — skipping SARIF"
fi

if command -v bandit >/dev/null 2>&1; then
  bandit -r services/document-parser/app scripts \
    -f sarif \
    -o "${OUT_DIR}/bandit.sarif" \
    -ll \
    -q || true
  if [ ! -f "${OUT_DIR}/bandit.sarif" ]; then
    echo '{"version":"2.1.0","$schema":"https://json.schemastore.org/sarif-2.1.0.json","runs":[]}' > "${OUT_DIR}/bandit.sarif"
  fi
else
  echo "::warning::bandit not installed — skipping SARIF"
fi

echo "SARIF files in ${OUT_DIR}:"
ls -la "${OUT_DIR}"/*.sarif 2>/dev/null || true
