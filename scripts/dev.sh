#!/usr/bin/env bash
# Starts API (:8000) and web app (:5173) together; Ctrl+C stops both. Same as `make dev`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
trap 'kill 0' INT TERM EXIT
(cd "$ROOT/backend" && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
(cd "$ROOT/frontend" && npm run dev) &
wait
