# Orion demo – spec pack

1. Create an empty folder (e.g. `orion/`) and copy everything from this pack into it, keeping the folders:
   `CLAUDE.md`, `docs/`, `seed/`, `reference/`.
2. Open the folder in VS Code, start Claude Code, and paste the prompt from `docs/KICKOFF_PROMPT.md`.
3. Claude Code builds the backend (FastAPI) and frontend (React + Fluent UI) with mock services, following `docs/REQUIREMENTS.md`.

Contents
- `docs/REQUIREMENTS.md` – detailed build spec (scope, roles, data model, business rules, screens, API, mocks, seed, demo storyline, acceptance criteria, build order).
- `docs/KICKOFF_PROMPT.md` – the prompt to paste into Claude Code.
- `CLAUDE.md` – standing project rules Claude Code reads automatically.
- `seed/` – data extracted from the client's Framework workbook, AI Playbook checklist and HTML prototype (72 Framework activities, 216 AI Playbook items with tiers, 6 portfolio golden sets, 38 eval metrics, 18 sample transitions + scripted flagship, OCET sample, VOC support model sample, mock ServiceNow/Confluence data, demo users).
- `reference/` – the client's HTML prototype (field reference only).
