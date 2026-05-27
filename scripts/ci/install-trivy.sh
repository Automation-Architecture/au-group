#!/usr/bin/env bash
# Install pinned Trivy CLI for CI (filesystem dep scan — no Docker).
set -euo pipefail

TRIVY_VERSION="0.69.3"
TRIVY_RELEASE="v${TRIVY_VERSION}"
TRIVY_BASE="https://github.com/aquasecurity/trivy/releases/download/${TRIVY_RELEASE}"
TRIVY_TARBALL="trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
TRIVY_CHECKSUMS="trivy_${TRIVY_VERSION}_checksums.txt"
trivy_tmp="$(mktemp -d)"
trap 'rm -rf "${trivy_tmp}"' EXIT

echo "Downloading Trivy ${TRIVY_RELEASE} checksums..."
curl -sSfL "${TRIVY_BASE}/${TRIVY_CHECKSUMS}" -o "${trivy_tmp}/${TRIVY_CHECKSUMS}"

echo "Downloading Trivy tarball..."
curl -sSfL "${TRIVY_BASE}/${TRIVY_TARBALL}" -o "${trivy_tmp}/${TRIVY_TARBALL}"

echo "Verifying Trivy tarball SHA256..."
expected="$(grep -F " ${TRIVY_TARBALL}" "${trivy_tmp}/${TRIVY_CHECKSUMS}" | tr -d '\r' | awk '{print $1}')"
if [ -z "${expected}" ]; then
  echo "::error::Could not find SHA256 for ${TRIVY_TARBALL} in ${TRIVY_CHECKSUMS}"
  exit 1
fi
actual="$(sha256sum "${trivy_tmp}/${TRIVY_TARBALL}" | awk '{print $1}')"
if [ "${actual}" != "${expected}" ]; then
  echo "::error::Trivy tarball SHA256 mismatch for ${TRIVY_TARBALL}"
  echo "Expected: ${expected}"
  echo "Actual:   ${actual}"
  exit 1
fi
echo "Trivy tarball verified (${actual})"

tar -xzf "${trivy_tmp}/${TRIVY_TARBALL}" -C "${trivy_tmp}"
sudo mv "${trivy_tmp}/trivy" /usr/local/bin/trivy
trivy --version
