#!/usr/bin/env bash
# Verify RLS is enabled and document-parser tables have explicit deny policies.
set -euo pipefail

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
psql "${DB_URL}" -v ON_ERROR_STOP=1 <<'SQL'
\set ON_ERROR_STOP on

-- Tables that must have RLS enabled (NFR-5.2 / NFR-5.3)
DO $$
DECLARE
  t text;
  missing text[] := ARRAY[]::text[];
  rls_tables text[] := ARRAY[
    'bankruptcies', 'creditors', 'bankruptcy_creditors',
    'zoom_info_contacts', 'salesforce_accounts', 'processing_jobs',
    'schedule_f_queue', 'pipeline_executions',
    'documents', 'document_parse_results', 'form201_extractions', 'creditor_matrix_extractions',
    'creditor_matrix_rows', 'manual_review_queue'
  ];
BEGIN
  FOREACH t IN ARRAY rls_tables LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public' AND c.relname = t AND c.relrowsecurity
    ) THEN
      missing := array_append(missing, t);
    END IF;
  END LOOP;
  IF array_length(missing, 1) > 0 THEN
    RAISE EXCEPTION 'RLS not enabled on: %', array_to_string(missing, ', ');
  END IF;
END $$;

-- Document-parser tables must have an explicit restrictive deny policy
DO $$
DECLARE
  t text;
  missing text[] := ARRAY[]::text[];
  policy_tables text[] := ARRAY[
    'documents', 'document_parse_results', 'form201_extractions', 'creditor_matrix_extractions',
    'creditor_matrix_rows', 'manual_review_queue'
  ];
  pol_count int;
BEGIN
  FOREACH t IN ARRAY policy_tables LOOP
    SELECT count(*) INTO pol_count
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = t
      AND permissive = 'RESTRICTIVE';
    IF pol_count < 1 THEN
      missing := array_append(missing, t);
    END IF;
  END LOOP;
  IF array_length(missing, 1) > 0 THEN
    RAISE EXCEPTION 'No restrictive deny policy on: %', array_to_string(missing, ', ');
  END IF;
END $$;

SELECT 'RLS verification passed' AS status;
SQL
