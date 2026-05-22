#!/usr/bin/env bash
# Install bandit, pip-audit, and pinned gitleaks for CI security composite action.
set -euo pipefail

pip install bandit==1.8.3 pip-audit==2.9.0

GITLEAKS_VERSION="8.24.2"
GITLEAKS_RELEASE="v${GITLEAKS_VERSION}"
GITLEAKS_BASE="https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_RELEASE}"
GITLEAKS_TARBALL="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
GITLEAKS_CHECKSUMS="gitleaks_${GITLEAKS_VERSION}_checksums.txt"
gitleaks_tmp="$(mktemp -d)"
trap 'rm -rf "${gitleaks_tmp}"' EXIT

echo "Downloading gitleaks ${GITLEAKS_RELEASE} checksums..."
curl -sSfL "${GITLEAKS_BASE}/${GITLEAKS_CHECKSUMS}" -o "${gitleaks_tmp}/${GITLEAKS_CHECKSUMS}"

echo "Downloading gitleaks tarball..."
curl -sSfL "${GITLEAKS_BASE}/${GITLEAKS_TARBALL}" -o "${gitleaks_tmp}/${GITLEAKS_TARBALL}"

echo "Verifying gitleaks tarball SHA256..."
expected="$(grep -F " ${GITLEAKS_TARBALL}" "${gitleaks_tmp}/${GITLEAKS_CHECKSUMS}" | tr -d '\r' | awk '{print $1}')"
if [ -z "${expected}" ]; then
  echo "::error::Could not find SHA256 for ${GITLEAKS_TARBALL} in ${GITLEAKS_CHECKSUMS}"
  exit 1
fi
actual="$(sha256sum "${gitleaks_tmp}/${GITLEAKS_TARBALL}" | awk '{print $1}')"
if [ "${actual}" != "${expected}" ]; then
  echo "::error::gitleaks tarball SHA256 mismatch for ${GITLEAKS_TARBALL}"
  echo "Expected: ${expected}"
  echo "Actual:   ${actual}"
  exit 1
fi
echo "gitleaks tarball verified (${actual})"

tar -xzf "${gitleaks_tmp}/${GITLEAKS_TARBALL}" -C "${gitleaks_tmp}"
sudo mv "${gitleaks_tmp}/gitleaks" /usr/local/bin/gitleaks
