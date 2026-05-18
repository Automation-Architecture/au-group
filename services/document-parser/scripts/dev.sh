#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  PYTHON_BIN="${PYTHON_BIN:-python3.11}"
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    PYTHON_BIN=python3
  fi
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

export PYTHONPATH="$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
# Swagger at /docs (override with EXPOSE_OPENAPI=false in .env for prod-like local runs)
export EXPOSE_OPENAPI="${EXPOSE_OPENAPI:-true}"

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8001}" --reload
