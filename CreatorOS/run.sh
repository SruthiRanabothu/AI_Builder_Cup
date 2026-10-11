#!/usr/bin/env bash
# Creator OS — one-command setup + run.
set -euo pipefail
cd "$(dirname "$0")/backend"

echo "==> Creating virtualenv + installing deps"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "==> Seeding demo data"
.venv/bin/python seed.py

echo "==> Starting server at http://localhost:8000"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
