# Kickoff prompt for Claude Code

Paste this into Claude Code (VS Code) from the repository root:

---

You are the lead full-stack engineer for **Orion – Operate Readiness Agent**, a demo web application for Shell Mobility's Supportability & Transition (S&T) team. The goal is a working, clickable demo with a real frontend and backend in which **all external systems and AI features are mocked behind clean interfaces**, so the client can see exactly what we plan to build.

Context files in this repo:
- `CLAUDE.md` – project rules (read first).
- `docs/REQUIREMENTS.md` – the full specification. Read it completely before writing any code.
- `seed/*.json` – seed data and reference lists (the data source of truth). The files are large; read their structure and a few records, not every line.
- `reference/OR_Agent_Prototype_V4_4.html` – the client's prototype. Use it **only** to cross-check form field labels and option lists (spec §18). Do not copy its design, CSS, JavaScript or logic.

Do this:
1. Read `CLAUDE.md` and `docs/REQUIREMENTS.md` end to end. Inspect the seed files' structure.
2. Create `PLAN.md` with milestones M1–M10 (spec §16), a task checklist per milestone mapped to FR/BR/AC ids, and an "Assumptions" section. Do not ask me questions – record assumptions and continue.
3. Scaffold the repository exactly as in spec §5.2 (backend + frontend), with `.env.example`, `requirements.txt`, `package.json`, a root `Makefile` (`make dev`, `make test`, `make reset`) and `README.md`.
4. Implement milestone by milestone. After each milestone run backend tests and the frontend build, fix failures, update `PLAN.md`, and commit.
5. Business rules go in `backend/app/rules/` as pure functions with unit tests (checklist assembly, tiering, readiness, RAG, gate validation, OCET maths incl. 100k @ 10% → 146,410 in year 5, reminder triggers, status synthesis within ±3 points of snapshots).
6. Enforce the guardrail: Orion only drafts and proposes; humans change statuses and decisions (BR-050), with audit actor types everywhere.
7. When all MUST items are done, build the SHOULD items in spec order (Teams preview, risk acceptance, OCET Excel export, support model retriever).
8. Finally, write `docs/DEMO_SCRIPT.md` from spec §13 with exact clicks, walk the full storyline against the running app (use the API to verify each step), fix anything that breaks, and give me a short summary: what's built, how to run it, known gaps.

Start now with M1.

---

Tips for running the session:
- If the session gets long, ask Claude Code to "continue with the next unchecked task in PLAN.md".
- To demo-reset at any time: `make reset` or Admin → Demo controls → Reset.
