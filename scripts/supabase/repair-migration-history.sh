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

# Filter REMOTE_VERSIONS to exclude any that exist locally
REMOTE_ONLY_VERSIONS=()
for remote_ver in "${REMOTE_VERSIONS[@]}"; do
  found=false
  for local_ver in "${LOCAL_VERSIONS[@]}"; do
    if [[ "$remote_ver" == "$local_ver" ]]; then
      echo "ERROR: Version $remote_ver exists in both REMOTE_VERSIONS and local migrations/" >&2
      echo "This would corrupt migration history. Please remove it from REMOTE_VERSIONS array." >&2
      exit 1
    fi
  done
  REMOTE_ONLY_VERSIONS+=("$remote_ver")
done

# Interactive confirmation before destructive operations
if [[ -z "${FORCE:-}" ]]; then
  echo "WARNING: This will modify migration history in the remote Supabase project!"
  echo ""
  echo "Operations to perform:"
  echo "  1. Mark ${#REMOTE_ONLY_VERSIONS[@]} remote-only versions as reverted"
  echo "  2. Mark ${#LOCAL_VERSIONS[@]} local migration files as applied"
  echo ""
  echo "Type 'YES' to proceed, or set FORCE=1 to skip this prompt:"
  read -r confirmation
  if [[ "$confirmation" != "YES" ]]; then
    echo "Aborted." >&2
    exit 1
  fi
fi

echo "Reverting remote-only migration history entries..."
supabase migration repair --status reverted "${REMOTE_ONLY_VERSIONS[@]}"

echo "Marking local migration files as applied on remote..."
supabase migration repair --status applied "${LOCAL_VERSIONS[@]}"

echo "Done. Run: supabase db push"
