# Orion demo – one-command helpers (spec §5.4) for macOS / Linux / CI.
# Windows without `make`: use the equivalent PowerShell scripts in scripts/ (PLAN.md A-02).

PY ?= python3
VENV_PY = backend/.venv/bin/python

.PHONY: setup dev test lint reset openapi audit

setup:            ## create backend venv + install backend and frontend dependencies
	cd backend && $(PY) -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -r requirements-dev.txt -c constraints.txt
	cd frontend && npm ci

dev:              ## start API (:8000) and web app (:5173); Ctrl+C stops both
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

test:             ## backend unit/API tests + frontend type-check/build (milestone definition of done)
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run build

lint:             ## ruff + black (backend), eslint (frontend)
	cd backend && .venv/bin/ruff check . && .venv/bin/black --check .
	cd frontend && npm run lint

reset:            ## re-seed the demo database (NFR-06)
	cd backend && .venv/bin/python -c "from app.seed.loader import reset_and_seed; reset_and_seed(); print('Demo data reset')"

openapi:          ## export OpenAPI from the backend and regenerate the frontend API types
	cd backend && .venv/bin/python scripts/export_openapi.py
	cd frontend && npm run gen:api

audit:            ## dependency vulnerability scan (VAPT hygiene, PLAN.md A-24)
	cd backend && .venv/bin/pip-audit -r constraints.txt
	cd frontend && npm audit
