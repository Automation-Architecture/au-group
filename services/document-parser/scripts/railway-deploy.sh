#!/usr/bin/env bash
# Deploy document-parser to Railway (run from services/document-parser).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERVICE_NAME="${RAILWAY_SERVICE_NAME:-au-group-document-parser}"
PROJECT_NAME="${RAILWAY_PROJECT_NAME:-au-group}"

echo "==> Railway deploy: ${SERVICE_NAME}"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install Railway CLI: npm i -g @railway/cli"
  exit 1
fi

if ! railway whoami >/dev/null 2>&1; then
  echo "Not logged in. Opening Railway login..."
  railway login
fi

# Link or create project
if [[ ! -f .railway/config.json ]]; then
  echo "==> Linking Railway project (first time)..."
  railway link -p "$PROJECT_NAME" -s "$SERVICE_NAME" 2>/dev/null || {
    echo "Creating new project: ${PROJECT_NAME}"
    railway init -n "$PROJECT_NAME"
  }
fi

# Required variables (skip if already set unless FORCE_VARS=1)
set_var() {
  local key="$1"
  local val="$2"
  if [[ -n "$val" ]]; then
    railway variables set "${key}=${val}" --skip-deploys
  fi
}

if [[ -f .env.railway ]]; then
  echo "==> Loading variables from .env.railway"
  set -a
  # shellcheck disable=SC1091
  source .env.railway
  set +a
fi

if [[ -z "${API_KEY:-}" ]]; then
  API_KEY="$(openssl rand -hex 32)"
  echo "Generated API_KEY (save this for n8n X-API-Key): ${API_KEY}"
  set_var API_KEY "$API_KEY"
fi

set_var SUPABASE_URL "${SUPABASE_URL:-https://umivttszdnsrosbqryia.supabase.co}"
set_var PARSER_VERSION "${PARSER_VERSION:-0.1.0}"
set_var AWS_REGION "${AWS_REGION:-us-east-1}"
set_var LOG_LEVEL "${LOG_LEVEL:-INFO}"

for required in SUPABASE_SERVICE_ROLE_KEY S3_BUCKET AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
  if [[ -z "${!required:-}" ]]; then
    echo "WARN: ${required} not set — add to .env.railway before production use"
  else
    set_var "$required" "${!required}"
  fi
done

echo "==> Deploying..."
railway up --detach

echo "==> Generating public domain..."
railway domain 2>/dev/null || railway service domain

echo ""
echo "Done. Check status: railway status"
echo "Logs: railway logs"
echo "Health: curl https://\$(railway domain)/health"
