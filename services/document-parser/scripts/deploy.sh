#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [[ -f /etc/systemd/system/document-parser.service ]]; then
  sudo systemctl daemon-reload
  sudo systemctl restart document-parser
  sudo systemctl status document-parser --no-pager
else
  echo "Install deploy/document-parser.service to /etc/systemd/system/ first."
  exit 1
fi
