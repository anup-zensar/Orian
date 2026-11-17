# Orion – Operate Readiness Agent (demo)

A working, clickable **demo** for Shell Mobility's Supportability & Transition (S&T) team: an Operate
Readiness workspace (system of record + workflow) and an AI assistant that **drafts, recommends and chases
while people make every decision**. Every external system (Microsoft Graph, Teams, ServiceNow, SharePoint,
Confluence, transcription) and every AI capability is a **deterministic mock behind an interface**, so the
real integrations can be dropped in later without touching the UI or the business rules.

- Behaviour spec: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) · Build plan, status and assumptions: [`PLAN.md`](PLAN.md)
- Demo storyline with exact clicks: `docs/DEMO_SCRIPT.md` (written in milestone M10)
- Seed data (source of truth for data): [`seed/`](seed/) · Client prototype (field labels only): [`reference/`](reference/)

> **Status:** under construction, milestone by milestone (M1–M10). See [`PLAN.md`](PLAN.md) for what is done.

---

## Quick start

### Prerequisites
- **Python 3.15** (latest stable, recommended) or 3.14 – see [PLAN.md A‑01](PLAN.md#5-assumptions)
- **Node.js 22.12+** (tested with 24.x) and npm

### Windows (PowerShell)
```powershell
scripts\setup.ps1     # creates backend\.venv (prefers Python 3.15) and installs all dependencies
scripts\dev.ps1       # API on http://127.0.0.1:8000 (docs: /docs), web app on http://127.0.0.1:5173
                      # port 5173 taken by another local app? scripts\dev.ps1 -WebPort 5174
scripts\test.ps1      # backend tests + lint, frontend type-check/build + lint
scripts\reset.ps1     # re-seed the demo data
scripts\audit.ps1     # dependency vulnerability scan (pip-audit + npm audit)
```

### macOS / Linux
```bash
make setup && make dev      # also: make test · make lint · make reset · make audit · make openapi
```

### Manual
```bash
cd backend  && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt -c constraints.txt   # Windows: .venv\Scripts\...
            && .venv/bin/python -m uvicorn app.main:app --reload --port 8000           # seeds automatically when the DB is empty
cd frontend && npm install && npm run dev                                             # proxies /api -> http://localhost:8000
cd backend  && .venv/bin/python -m pytest -q                                          # tests
```

Configuration lives in `backend/.env` (copy [`backend/.env.example`](backend/.env.example)). No secrets are
stored in source control.

---

## Demo users (no password – pick one on the login page; switch any time from the top bar)

| User | Role | Typical use in the demo |
|---|---|---|
| Asha Menon (U01) | OR focal | Owns the flagship *Mobility Knowledge Agent*; records reviews and decisions |
| Rahul Iyer, Neha Kulkarni, Vikram Shah, Priya Nair, Arjun Rao, Kavya Reddy, Sanjay Pillai, Divya Joshi (U02–U09) | OR focal | Own the other seeded transitions |
| Daniel Brooks (U10) | Project manager | Item status, evidence, OCET inputs |
| Mei Lin (U11) | Solution architect | Technical items, OCET monitoring cost, support model review |
| Sofia Garcia (U12) | SOM OLM | Approves AtD/AtO and OCET (final step), agrees the support model |
| Tom Becker (U13) | Planner (Finance) | First OCET approval step |
| Fatima Khan (U14) | IRM (Compliance) | Confirms tiers, compliance statuses, exceptions |
| Laura Evans (U15) | Leadership | Read-only dashboard, control tower, leadership updates |
| Playbook Admin (U16) | Admin | Playbook configuration and demo controls |

---

## Architecture

```
frontend/  React 18 + TypeScript + Vite + Fluent UI v9 + TanStack Query + React Router
   └─ talks only to /api/v1 (header X-Demo-User); typed client generated from the backend OpenAPI
backend/   Python + FastAPI + SQLAlchemy 2 + SQLite (DATABASE_URL configurable)
   app/routers/   HTTP endpoints, one module per area (thin)
   app/domain/    DB-aware operations: validation via rules, writes, audit trail, notifications
   app/rules/     PURE business rules, unit-tested (checklist, tiering, readiness, RAG, gates, OCET, reminders)
   app/services/  interfaces.py (Protocols) · mock/ (default) · live/ (documented stubs) · factory.py
   app/seed/      seed loader + deterministic status synthesis
```

A full Mermaid diagram and the mock → real service mapping are added in M10.

**Guardrail (BR‑050):** Orion never changes statuses, applicability, tiers, evidence acceptance,
conditions, approvals or gate decisions. It drafts and proposes; a permitted human clicks. Every write is
recorded in the audit trail with its actor type: *Human*, *Workflow rule*, *Orion agent* or *System*.

---

## Security notes (demo level – see PLAN.md A‑23/A‑24)
- Demo login (`X-Demo-User`) is for demonstration only; it is isolated in `backend/app/deps.py` so Entra ID
  token validation can replace it without router changes.
- Dependencies are pinned to the latest stable releases; run `scripts\audit.ps1` / `make audit` regularly.
- API responses carry `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control: no-store` and a CSP
  `frame-ancestors` allow-list (the app must run inside a Microsoft Teams tab later).
- Uploads are stored by a mock SharePoint store with filename sanitisation, size and type limits.
