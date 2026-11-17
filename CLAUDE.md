# CLAUDE.md – Orion demo build

Project memory for Claude Code. Read before every task.

## What we are building
Orion – Operate Readiness Agent: a **demo** web app (React + FastAPI) for Shell Mobility's S&T team. Full spec: `docs/REQUIREMENTS.md` (source of truth for behaviour). Seed data: `seed/*.json` (source of truth for data). Client prototype: `reference/OR_Agent_Prototype_V4_4.html` – use **only** to cross-check form field labels/options (§18 of the spec). Never copy its layout, CSS, JS or logic.

## Non-negotiables
- Stack: React 18 + TypeScript + Vite + Fluent UI v9 + TanStack Query + React Router; Python 3.11 + FastAPI + SQLAlchemy 2 + SQLite + python-pptx (spec §5).
- Every external system and every AI capability is a **mock behind an interface** (`backend/app/services/`), deterministic, selected by config (spec §10).
- Business rules live in `backend/app/rules/` as pure functions with unit tests (spec §7, NFR-02).
- **Orion never changes statuses, applicability, tiers, evidence acceptance, conditions, approvals or gate decisions.** It only drafts and proposes; a permitted human clicks (BR-050). Label outputs "Orion agent" (AI badge) vs "Workflow rule".
- Every write creates an AuditEvent with actor type (Human / Workflow rule / Orion agent / System).
- API-first: the UI only talks to `/api/v1`; app must work inside an iframe (Teams tab later); stable deep links.
- One gate model everywhere: SG0 → SG2 → SG3 → SG4_ATD → SG5_HYPERCARE → SG6_ATO → CLOSURE.

## Working style
- Keep `PLAN.md` up to date (milestones M1–M10 from spec §16, assumptions, status).
- Don't stop to ask questions; choose the simplest behaviour that keeps the demo storyline (spec §13) working and record it under "Assumptions" in `PLAN.md`.
- After each milestone: `pytest` in backend, `npm run build` (type-check) in frontend, fix failures, update `PLAN.md`, commit with a message referencing FR/BR ids.
- Prefer clear, boring code over clever code; the client's team should be able to read it.

## Commands
- Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev` (proxy `/api` → `http://localhost:8000`)
- Tests: `cd backend && pytest -q`
