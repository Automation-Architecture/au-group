#!/usr/bin/env bash
# Ephemeral credentials for document-parser CI and local E2E (not production secrets).
set -euo pipefail

_gen_hex() {
  openssl rand -hex 32
}

API_KEY="${API_KEY:-$(_gen_hex)}"
JWT_SECRET="${JWT_SECRET:-$(_gen_hex)}"
AUTH_USERNAME="${AUTH_USERNAME:-test-user}"
AUTH_PASSWORD="${AUTH_PASSWORD:-test-password}"

if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "API_KEY=${API_KEY}"
    echo "JWT_SECRET=${JWT_SECRET}"
    echo "AUTH_USERNAME=${AUTH_USERNAME}"
    echo "AUTH_PASSWORD=${AUTH_PASSWORD}"
  } >>"${GITHUB_ENV}"
fi

export API_KEY JWT_SECRET AUTH_USERNAME AUTH_PASSWORD
