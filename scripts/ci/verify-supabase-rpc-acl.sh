#!/usr/bin/env bash
# Verify au_group_* RPCs are service_role-only (no anon/authenticated/public execute).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DB_URL="${DB_URL:-}"
if [ -z "${DB_URL}" ] && command -v supabase >/dev/null 2>&1; then
  DB_URL="$(supabase status -o json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('DB_URL') or '')
" 2>/dev/null || true)"
fi
if [ -z "${DB_URL}" ] && command -v supabase >/dev/null 2>&1; then
  DB_URL="$(supabase status -o env 2>/dev/null | sed -n 's/^DB_URL=//p' | head -1 | tr -d "\"'")"
fi

if [ -z "${DB_URL}" ]; then
  echo "::error::Could not resolve local DB_URL (run after supabase db start)"
  exit 1
fi

export PGPASSWORD=""
psql "${DB_URL}" -v ON_ERROR_STOP=1 -f scripts/supabase/verify-rpc-acl.sql
echo "RPC ACL verification passed."
