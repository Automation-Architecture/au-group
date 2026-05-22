#!/usr/bin/env bash
# Start document-parser for Playwright E2E (CI or local).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PARSER_DIR="${ROOT}/services/document-parser"
PORT="${PARSER_PORT:-8001}"
HOST="${PARSER_HOST:-127.0.0.1}"
BASE_URL="http://${HOST}:${PORT}"
PID_FILE="${TMPDIR:-/tmp}/au-group-parser-e2e.pid"

cd "${PARSER_DIR}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements-dev.txt

export API_KEY="${API_KEY:-test-api-key-for-ci-suite-only-do-not-use-in-production}"
export APP_ENV=development
export RATE_LIMIT_ENABLED=false
export EXPOSE_OPENAPI=true
export JWT_SECRET="${JWT_SECRET:-test-jwt-secret-at-least-32-characters-long}"
export AUTH_USERNAME="${AUTH_USERNAME:-test-user}"
export AUTH_PASSWORD="${AUTH_PASSWORD:-test-password}"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "Parser already running (pid $(cat "${PID_FILE}"))"
else
  uvicorn app.main:app --host "${HOST}" --port "${PORT}" &
  echo $! > "${PID_FILE}"
fi

echo "Waiting for ${BASE_URL}/health ..."
for _ in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
    echo "Parser ready at ${BASE_URL}"
    exit 0
  fi
  sleep 1
done

echo "Parser failed to start" >&2
exit 1
