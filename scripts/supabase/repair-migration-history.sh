#!/usr/bin/env bash
# Align remote supabase_migrations.schema_migrations with supabase/migrations/*.sql
# Use when: "Remote migration versions not found in local migrations directory"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

REMOTE_VERSIONS=(
  20260515073354 20260515073402 20260515073409 20260515073411
  20260515073749 20260515073800 20260515073925
  20260518094914 20260518102838 20260518102901 20260518154749
  20260519021755 20260519021759 20260519021805
  20260519022934 20260519023032 20260519023043
  20260519023627 20260519023643 20260519094637 20260519095853 20260519102432
  20260520091106 20260520094046 20260520094047 20260520114906
  20260522035722 20260522040636 20260522040940
)

LOCAL_VERSIONS=()
for file in supabase/migrations/*.sql; do
  base="$(basename "$file")"
  LOCAL_VERSIONS+=("${base%%_*}")
done

echo "Reverting remote-only migration history entries..."
supabase migration repair --status reverted "${REMOTE_VERSIONS[@]}"

echo "Marking local migration files as applied on remote..."
supabase migration repair --status applied "${LOCAL_VERSIONS[@]}"

echo "Done. Run: supabase db push"
