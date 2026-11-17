# PLAN.md – Orion demo build

Living plan for the Orion – Operate Readiness Agent demo. Source of truth for behaviour: `docs/REQUIREMENTS.md`
(the "spec"); for data: `seed/*.json`. This file tracks milestones M1–M10 (spec §16), maps every task to
FR / BR / NFR / AC ids, records every assumption, and holds the engineering conventions all contributors follow.

**Scope of this build: the MVP = every MUST item.** SHOULD items are listed under
[Deferred SHOULD items](#deferred-should-items-not-in-the-mvp) and are not built unless asked.

Status legend: `[ ]` to do · `[~]` in progress · `[x]` done (verified by tests/build) · `[-]` deferred

---

## 0. Definition of done (every milestone)

1. `cd backend && pytest -q` – all green; `ruff check .` clean.
2. `cd frontend && npm run build` (= `tsc -b` strict type-check + `vite build`) – green; `npm run lint` clean.
2a. VAPT hygiene: `npm audit` and `pip-audit -r backend/constraints.txt` report no known vulnerabilities (or each one is recorded here).
3. Every write path creates an `AuditEvent` with an actor type (NFR-03); Orion never writes decisions (BR-050).
4. `PLAN.md` updated (tasks ticked, new assumptions recorded, status log line).
5. One commit on branch `build/mvp` whose message references the FR/BR ids delivered.

---

## 1. Runtime and toolchain

| Item | Choice | Why |
|---|---|---|
| Python | **Target 3.15.2** (latest stable, released 2026‑10‑25); currently built & tested on the installed **3.14.7** | See A‑01. All pinned packages verified to ship cp315 Windows wheels, so moving to 3.15 is a venv rebuild only. |
| Backend packages | FastAPI 0.163.1 · Starlette 1.10.0 · Uvicorn 0.54.0 · Pydantic 2.14.3 · pydantic‑settings 2.16.3 · SQLAlchemy 2.1.9 · python‑multipart 0.0.34 · python‑pptx 1.0.2 · openpyxl 3.1.5 · APScheduler 3.11.3 | Latest stable releases (VAPT: fewer known CVEs); exact pins in `backend/requirements*.txt`. |
| Backend dev | pytest 9.2.0 · httpx 0.28.1 · ruff 0.17.5 · black 26.10.1 · pip‑audit 2.10.1 | NFR‑02, NFR‑08, VAPT hygiene. |
| Node | 24.x / npm 11.x | Installed. Vite 8 needs ≥ 22.12. |
| Frontend | React 18.3.1 · Fluent UI v9 9.75.2 · React Router 6.30.6 · TanStack Query 5.107.1 · react‑hook‑form 7.92 · zod 4.6 · Recharts 3.10 · @xyflow/react 12.12.1 · dayjs 1.11 · Vite 8.3 · TypeScript 5.9.3 | Majors fixed by spec §5.1; latest patch of each. See A‑19 for TS and xyflow. |

---

## 2. Milestones

### M1 Foundation  – status: `[x]` (done 2026‑11‑17)
Spec §16.1: repo scaffold, config, DB models, seed loader + synthesis, `/reference`, `/users`, demo login + user switcher, app shell/navigation, tests for rules skeleton.

- [x] M1.1 Repo scaffold exactly as spec §5.2; `.gitignore`, `.gitattributes`, `.env.example` (NFR‑07), `requirements.txt` + `requirements-dev.txt`, `pyproject.toml` (ruff/black/pytest), root `Makefile` (`make dev/test/reset`) + `scripts/*.ps1` / `scripts/*.sh` equivalents (§5.4, A‑02), `README.md` skeleton.
- [x] M1.2 `config.py` with every §5.3 key (+ `SEED_DIR`, `STORAGE_DIR`, `MOCK_DELAY_MS`, `APP_BASE_URL`, `CORS_ORIGINS`); `db.py` (engine URL configurable, SQLite default); `clock.py` (today = admin override → `SEED_DATE` → real date, A‑15).
- [x] M1.3 SQLAlchemy 2 models for every spec §6 entity (+ helper tables: `ApprovalStep`, `OrionProposal`, `AppSetting`, `ReferenceData`, `ApprovalChainConfig`, `ReminderRule`, `ReminderRun`, `EvalTarget`), all with `created_at`/`updated_at`.
- [x] M1.4 Auth dependency (`X-Demo-User` → user; 401 if missing/unknown) structured for later Entra ID swap (FR‑001); permission matrix as data + `require()` dependency returning 403 with a human reason (BR‑001).
- [x] M1.5 Audit writer `domain/audit.py` (actor types Human / Workflow rule / Orion agent / System, before/after JSON) (NFR‑03).
- [x] M1.6 Pure rules + unit tests (NFR‑02): `rules/constants.py`, `rules/checklist.py` (BR‑010 assembly incl. tier exclusion, owner defaults), `rules/readiness.py` (BR‑020), `rules/rag.py` (BR‑021), `rules/synthesis.py` (§11.3).
- [x] M1.7 Seed loader `seed/loader.py` (§11.2 order), idempotent, auto‑runs on startup when DB empty, reset helper (AC‑01, NFR‑06); flagship overrides, conditions, exceptions, risks, gate history, actions, evidence, eval results, OCET sample; "Seeded" audit events.
- [x] M1.8 API: `GET /api/v1/reference`, `GET /users`, `GET /me` (user + permission list); router modules pre‑registered for every §9 area; error contract (403/409 with `reasons[]`, normalised 422); security headers; CORS allow‑list.
- [x] M1.9 Service layer skeleton: `services/interfaces.py` (8 Protocols, §10), `services/factory.py`, `services/mock/` (ServiceNow, Confluence, DocumentStore, Transcript, Mail, Notification implemented; AI + SupportModelGenerator grow per milestone), `services/live/` stubs with docstrings of the real call (NFR‑01). Adaptive Card templates + renderer (`services/cards/`, §10.4) added early.
- [x] M1.10 Frontend scaffold: Vite + React 18 + TS `strict` + Fluent UI v9 + Router v6 + TanStack Query v5; typed API client generated from the backend OpenAPI (`npm run gen:api`); `X-Demo-User` on every call; Vite proxy `/api` → `:8000`; eslint + prettier (NFR‑08).
- [x] M1.11 Demo login page (users from `/users`, role badges, no password) + **Switch user** in the top bar on every page (FR‑001); app shell: left nav (all §8 items, Admin only for ADMIN), top bar (Orion name, global search placeholder, bell placeholder, Orion button → panel placeholder, user menu) (FR‑002); placeholder routes for every page incl. deep links; theme tokens for lens/RAG/actor colours (§12).
- [x] M1.12 Tests: synthesis within ±3 points of every snapshot (§11.3), checklist counts per project type / Tier 2 exclusions (AC‑03 rule level), seed idempotency, auth/permissions, reference API. Backend `pytest` + frontend `npm run build` green; commit.

### M2 Visibility  – status: `[ ]`
FR‑010, FR‑011, FR‑012, BR‑020, BR‑021, AC‑01, AC‑02.
- [ ] M2.1 `GET /transitions?portfolio&region&gate&rag&type&q` with computed lens readiness, overall, open/critical gaps, RAG (live, never stored), next decision + days (FR‑012).
- [ ] M2.2 `GET /control-tower?filters` → KPI tiles (active, red, decisions ≤ 14 d, with critical gaps, compliance < 70 %), heatmap portfolio × gate (count + worst RAG), readiness by region, register, escalation queue (red + blockers), decision calendar (45 days), operating rhythm (static, from prototype) (FR‑011).
- [ ] M2.3 `GET /dashboard` role‑aware: KPI tiles, "My work" (items/actions/approvals with deep links), recent activity (last 10 audit events in my transitions), LEADERSHIP portfolio tiles (FR‑010).
- [ ] M2.4 `AIService.insights()` mock + `GET /orion/insights?scope=dashboard|control-tower|transition` (Orion insights cards, AI badge) (FR‑010, FR‑011).
- [ ] M2.5 UI: Transitions page (searchable register + "New transition"), Control tower (filters in URL, clickable KPI tiles, heatmap cell filter, Recharts region bars, register with B/T/C mini bars, escalation queue, calendar, insights card, operating rhythm card), Dashboard; global transition search in top bar.
- [ ] M2.6 Tests: RAG table cases (BR‑021), list filters, control‑tower aggregates; 18 transitions visible (AC‑01).

### M3 Intake  – status: `[ ]`
FR‑020, FR‑021, FR‑022, BR‑010, BR‑011, AC‑03, AC‑04, AC‑05.
- [ ] M3.1 ServiceNow mock + `GET /integrations/servicenow/projects/{id}` (PRJ0052210, PRJ0049920; friendly not‑found).
- [ ] M3.2 `POST /transitions` intake with validation: required fields, AI‑only required fields, Retail Site Systems ⇒ ≥ 1 site row with Site ID + Site key (AC‑05); defaults OR focal = current user (if OR focal), PM U10, Architect U11, OLM U12, IRM U14; next id `TR-00NN`.
- [ ] M3.3 `rules/tiering.py` (BR‑011, ordered rules + rationale) + `POST /tiering/propose`; `PUT /transitions/{id}/tier` (OR focal proposes); `POST /transitions/{id}/tier/confirm` (IRM only, confirm or change with reason) (AC‑04).
- [ ] M3.4 `GET/PUT /transitions/{id}/ai-profile` (questionnaire §6 AIProfile).
- [ ] M3.5 `GET/PUT /transitions/{id}/scope` (golden set + counts; mandatory rows locked) + `AIService.recommend_applicability()` mock + "Accept all recommendations" (human click, BR‑050) (FR‑022).
- [ ] M3.6 `POST /transitions/{id}/launch-assessment` creates TransitionItems (BR‑010); re‑assembly after tier change keeps statuses/evidence/notes and marks newly excluded items N/A (tier), audit with counts (BR‑010 step 7); proposed‑tier banner data.
- [ ] M3.7 UI: intake form (labels/options per §8.4 + prototype §18), ServiceNow Fetch, repeatable site rows, live **Auto‑scope** panel; tiering wizard (3 steps, IRM confirm/change); scope page (golden set table, counts, Orion recommendation card, Launch).
- [ ] M3.8 Tests: tiering cases (Tier 2 for internal/no writes/non‑sensitive/TQ4, Tier 4 when TQ2), only IRM confirms, assembly per project type (Normal/Infrastructure = Framework only; Agentic AI/Combined + playbook), Tier 2 excludes Tier 3/4‑only items as "not applicable (tier)" (AC‑03), Retail sites validation (AC‑05).

### M4 Workspace  – status: `[ ]`
FR‑030, FR‑031, FR‑032, FR‑033, FR‑035, FR‑036, FR‑037, FR‑110, BR‑030, AC‑06, AC‑13.
- [ ] M4.1 Workspace header (flavour chips, 7‑gate stepper with decision gates marked, overall readiness, RAG chip, next decision, OR focal, autonomous toggle (OR focal only) `POST /transitions/{id}/autonomous-mode`, Ask Orion) + tab routing `/transitions/:id/<tab>`.
- [ ] M4.2 Overview tab: lens cards (readiness, done / in progress / not started / gaps, lens question, owner), open conditions, pending exceptions, risks, blocker, recent activity, gate history timeline.
- [ ] M4.3 Assessment tab: `GET /transitions/{id}/items` filters (gate default ≤ current, lens, source, status, owner, mine, applicability incl. excluded, q), grouped by gate → lens; inline status (permission‑aware), severity, DE, evidence count, updated‑by badge, row menu; bulk owner / N/A (OR focal); gate summary bar; deep link `?item=` (FR‑031).
- [ ] M4.4 `PATCH /items/{id}` + `POST /items/bulk` enforcing BR‑030 (Gap/Non‑compliant needs severity + note; N/A needs reason and OR focal (B/T) / IRM (C); Compliant with conditions creates a Condition; Compliant needs DE Yes/N/A) + audit before/after (AC‑06).
- [ ] M4.5 Evidence tab: list/filter, upload (mock DocumentStore → fake SharePoint URL), link, email sign‑off text, review Accept/Reject (OR focal B/T, IRM C), download (FR‑033).
- [ ] M4.6 Gaps & actions tab: gaps list (severity, lens, owner, days to decision); actions CRUD (`/transitions/{id}/actions`, `PATCH /actions/{id}`); Orion recommendation card per gap (mock, buttons → Create action (human) / Draft chaser) (FR‑032).
- [ ] M4.7 Conditions / exceptions / risks tab: conditions table + close; exceptions list + "Request exception" (chain wiring in M5); risk register (FR‑035).
- [ ] M4.8 Hypercare tab: defects CRUD, "No defects – tracker in place" confirmation (FR‑036).
- [ ] M4.9 AI playbook tab (AI flavours): tier card, AI profile (editable), eval metrics table (target for tier, result input, auto pass/fail, manual toggle), **Import eval results (mock)** (flagship from seed; others deterministic plausible values), tier‑threshold banner (FR‑037).
- [ ] M4.10 OCET + Support model link cards (status, version, totals) (FR‑030 h/i).
- [ ] M4.11 Activity tab + global Audit trail page `GET /audit?transition_id&actor&actor_type&entity&from&to` with before/after diff (FR‑110, AC‑13).
- [ ] M4.12 Tests: BR‑030 rules + permissions (AC‑06), evidence review permissions, audit written for each write.

### M5 Gates & approvals  – status: `[ ]`
FR‑034, FR‑050, FR‑070, FR‑071 (core), FR‑072 (core), BR‑040, BR‑041, AC‑07 (first half), AC‑08.
- [ ] M5.1 `rules/gates.py`: stage‑review validation (Proceed / Proceed with conditions / Hold; SG0 needs confirmed tier for AI; SG3 ignores Compliance lens), decision validation (Approve / Approve with conditions / Return), failed eval metrics as Technical blockers at AtD, AtO extra rules, Closure rules (no conditions), carried items + unit tests (BR‑040, AC‑08).
- [ ] M5.2 `GET /transitions/{id}/readiness?gate=` → verdict (Ready / Ready with conditions / Not ready), why (blocking items by lens, critical gaps, conditions due, pending exceptions, failed evals, OCET, support model, chain status), Orion narrative (`AIService.readiness_narrative`), recommended actions (`AIService.recommend_actions`) as stored proposals (FR‑050).
- [ ] M5.3 `POST /transitions/{id}/gates/{gate}/review`, `/request-approval`, `/decision`; gate advance; conditions created from dialog; Return cancels chain + requires note (BR‑040).
- [ ] M5.4 Approval chains (BR‑041): types OCET / AtD / AtO / SUPPORT_MODEL / EXCEPTION from config; sequential steps, role check, approve (comment optional) / reject (comment required → whole request Rejected + requester notified); completion hooks per type; exception chain CISO/BISO step mock‑approvable by IRM in demo mode.
- [ ] M5.5 Notifications on each step: in‑app (bell) + mock email (Outbox) + mock Teams Adaptive Card (`services/cards/approval_request.json`) (BR‑041, §10.3–10.4).
- [ ] M5.6 Drafts core (moved forward from M8 because approval requests are drafted in assistive mode): `OrionDraft` CRUD, `GET /orion/drafts`, `PATCH`, `send`, `discard`; MailService/NotificationService mocks write Outbox; `GET /outbox`; `GET /notifications` + read (FR‑071, FR‑072 core).
- [ ] M5.7 UI: Gates & decisions tab (panel per gate, readiness check panel, chain status, Request approval → Orion draft dialog → Send, decision dialog with conditions editor, disabled reasons), Approvals inbox (Waiting for me / Requested by me / All), Orion drafts page (basic), Outbox page (email + Adaptive Card preview + raw JSON), notification bell.
- [ ] M5.8 Tests: gate rules matrix, chain role enforcement, reject flow, flagship readiness = "Not ready for AtD" with scripted blockers (AC‑07 first half).

### M6 OCET  – status: `[ ]`
FR‑060, BR‑070, AC‑09.
- [ ] M6.1 `rules/ocet.py`: compounding projection with per‑year overrides, missing base ⇒ 0 + "Inputs pending", category × year totals, grand totals, 5‑year total, variance vs previous version (line + category) + tests incl. 100k @ 10 % → 100,000 · 110,000 · 121,000 · 133,100 · 146,410.
- [ ] M6.2 API: `GET /transitions/{id}/ocet`, `PUT /ocet/versions/{vid}/lines` (Draft / Inputs pending only), `POST /ocet/versions/{vid}/submit` (blocked when base missing; chain Planner → OLM), `POST /transitions/{id}/ocet/new-version` (copy lines; previous superseded on submit), `POST /ocet/versions/{vid}/request-inputs` (Orion drafts with deep link), `GET /ocet/compare?from&to`.
- [ ] M6.3 Chain completion: version Approved; linked items (FW‑008, S45‑006) → Complete with actor "Workflow rule" (BR‑030 linked modules); rejection → Rejected (new version needed).
- [ ] M6.4 `AIService.explain_ocet_change()` mock card.
- [ ] M6.5 UI `/transitions/:id/ocet`: header (currency, start year, horizon, version/status, chain progress, 5‑year total, variance), editable lines grid (overrides popover with reason, input owner/status), read‑only yearly columns, category × year table, stacked bar + total line charts, worked‑example tooltip, buttons (Request inputs, Submit, New version, Compare), ATO+12 note.
- [ ] M6.6 Tests: maths, versioning rules, submit blocked on missing base, Planner → OLM across user switches, linked items complete (AC‑09).

### M7 Support model  – status: `[ ]`
FR‑040, AC‑10.
- [ ] M7.1 Mocks: ConfluenceService.fetch (url_contains match), TranscriptService.get_text (.vtt/.txt/.docx read; audio/video canned + log), DocumentStore.save (storage/<transition>/), SupportModelGenerator (VOC sample by name/URL; generic landscape otherwise, §10.6.1).
- [ ] M7.2 API: `GET /transitions/{id}/support-model`, `POST …/support-model/inputs` (multipart + confluence_url), `POST …/support-model/generate`, `PUT /support-models/{id}`, `POST /support-models/{id}/send-for-review` (Architect → OLM), `POST /support-models/{id}/pptx`, `GET /support-models` (list).
- [ ] M7.3 PPT export with python‑pptx (16:9, 5 slides: title, radial landscape with arrows + vendor box, L1→L2→L3 flow, contacts & SLA table, open questions & sources; `TEMPLATE_NAME = "PTIV ORB (placeholder)"`, single theme function, footer "Confidential") → Evidence (Generated, FW‑035); regeneration = new version.
- [ ] M7.4 Agreed ⇒ support‑model‑linked items Complete (Workflow rule).
- [ ] M7.5 UI: generator page (inputs, info note, 3‑step simulated progress, React Flow radial editor with add/rename/retype/delete nodes and edges, side panels: hosting & vendor, responsibilities, L1/L2/L3, contacts & SLA, open questions with "Draft question to architect", sources), status flow, Generate PPT + download (no `window.open`); list page `/support-models`.
- [ ] M7.6 Tests: VOC + generic generation, PPT has 5 slides and opens (python‑pptx re‑read), review chain, linked items (AC‑10).

### M8 Orion  – status: `[ ]`
FR‑071, FR‑072, FR‑080, FR‑090, BR‑050, BR‑060, AC‑11, AC‑12.
- [ ] M8.1 AIService mock complete: `readiness_narrative`, `recommend_actions`, `recommend_applicability`, `draft_message` (chaser / reminder / input request / approval request / leadership), `leadership_update`, `explain_ocet_change`, `chat` (keyword intents §8.15), `insights`; deterministic templates; `[MOCK AIService]` log lines; live stub.
- [ ] M8.2 `POST /orion/chat` (quick actions + form cards + free text) returning typed message cards (text, readiness, table, drafts, link, proposal, form).
- [ ] M8.3 Proposals: stored `OrionProposal`; `POST /orion/proposals/{pid}/accept` executes the normal domain operation **as the current human** (`actor_type=Human`, note "Accepted Orion proposal <id>"); Orion service has no write path to statuses/decisions + test (BR‑050, NFR‑04).
- [ ] M8.4 Reminder engine `rules/reminders.py` R1–R7 + `POST /reminders/run` (counts per rule, last run), 24 h de‑dup per rule+transition+recipient, autonomous mode sends R1/R2/R3/R5 directly (R3 reminders only), optional APScheduler job (`REMINDER_JOB_ENABLED`) + tests (BR‑060, AC‑11).
- [ ] M8.5 Adaptive Card templates `reminder_digest.json`, `ocet_approval.json` (+ `approval_request.json` from M5).
- [ ] M8.6 Leadership updates: `POST /orion/leadership-update {scope, scope_id}`, `GET /leadership-updates`, send via email (mock), copy (FR‑080).
- [ ] M8.7 UI: Orion side panel (≈420 px, every page) + `/orion` full page: context chip, 7 quick actions, form‑first cards, card renderers, AI badges, footer "Orion recommends and drafts. People decide." (FR‑090); drafts queue complete (edit recipients/subject/body, Send/Discard, Run reminder engine + counts, assistive/autonomous banner) (FR‑071); leadership updates page (FR‑080).
- [ ] M8.8 Tests: chat intents, proposal accept audit, reminder rules + de‑dup + autonomous, leadership update content (AC‑11, AC‑12).

### M9 Admin & demo  – status: `[ ]`
FR‑100, NFR‑06.
- [ ] M9.1 Admin API + UI (ADMIN only): playbook library (search, edit title/description/gate/lens/tiers/mandatory/active, "lens suggested – confirm" badge), flavour rules, portfolio golden sets (add/remove/mandatory), eval targets grid metric × Tier 1–4 + "targets confirmed" flag, approval chains, reminder rules (thresholds, enable/disable), users (read‑only); notice "changes affect new transitions".
- [ ] M9.2 Demo controls (`DEMO_MODE=true` only): Reset (re‑seed < 10 s), **Fast‑forward flagship** (complete open items due ≤ current gate except OCET/support‑model‑linked and exception items; re‑import passing evals), Set "today", Run reminder engine.
- [ ] M9.3 Tests: admin permission 403 for non‑ADMIN, reset idempotent, fast‑forward + scripted fixes ⇒ "Ready for AtD" (AC‑07 second half).

### M10 Polish  – status: `[ ]`
§12, NFR‑05, NFR‑09, NFR‑10, AC‑01, AC‑14, AC‑15.
- [ ] M10.1 Loading skeletons, empty states with next step, error toasts showing `reasons[]`, disabled buttons with reason tooltips, aria labels, keyboard focus, RAG chips with text.
- [ ] M10.2 README: run instructions, demo users, Mermaid architecture diagram, mock → real service mapping (Graph, Teams bot, ServiceNow, Confluence, SharePoint, Azure OpenAI/Foundry), security placeholders (Entra ID SSO + RBAC, Key Vault, data classification, Orion as Tier 2 agent), "Open points for the client" (§17) (NFR‑09, NFR‑10).
- [ ] M10.3 `docs/DEMO_SCRIPT.md` from §13 with exact clicks; scripted API walk of the full storyline (`backend/tests/test_storyline.py`) + manual UI walk; fix issues (AC‑14).
- [ ] M10.4 VAPT hygiene: `pip-audit` and `npm audit` clean or documented; security headers verified; p95 timing spot check (NFR‑05).
- [ ] M10.5 Final regression: all tests (AC‑15), build, lint; summary of what's built, how to run, known gaps.

---

## 3. Deferred SHOULD items (not in the MVP)

| Item | Spec | Placeholder in MVP |
|---|---|---|
| Teams preview page | FR‑120, §8.18 | Nav entry hidden; Adaptive Cards are visible in the Outbox (A‑13). |
| Risk acceptance (conditional AtO) | §8.7 f (SHOULD) | Not shown. |
| OCET Excel export | §8.10, `GET /ocet/versions/{vid}/export.xlsx` | Button hidden. |
| Support Model Retriever | FR‑130, §8.19 | `/support-models` lists generated models only. |
| Live LLM mode (`AI_MODE=live`) | §10.1 | `services/live/ai.py` stub documents the call; mock always used. |

---

## 4. Engineering conventions (all contributors)

**Backend**
- Layers: `routers/` (HTTP only, thin) → `domain/` (DB‑aware operations: validation via rules, writes, audit, notifications) → `rules/` (pure functions, no DB, no I/O) and `services/` (external systems & AI, always via `services/factory.py`). `domain/` is an addition to the §5.2 layout so routers stay thin and Orion proposals reuse exactly the same operations as user endpoints (BR‑050).
- Every write goes through a `domain` function that calls `domain.audit.record(...)` with `actor_type` ∈ {`Human`, `Workflow rule`, `Orion agent`, `System`}.
- Orion (AI service, proposal generation) never calls domain write functions for statuses, applicability, tiers, evidence acceptance, conditions, approvals or gate decisions. Accepting a proposal is a **human** request handled by `POST /orion/proposals/{pid}/accept`, which runs the normal domain function with the current user and `note="Accepted Orion proposal <id>"`.
- API errors: `403 {"detail": str, "reasons": [str]}` (permissions), `409 {"detail": str, "reasons": [str]}` (rule violations), `404 {"detail": str}`, `422 {"detail": "Validation failed", "reasons": [str], "errors": [...]}`. Use helpers in `app/errors.py`.
- Dates: `app.clock.today()` / `app.clock.now()` only — never `date.today()` / `datetime.now()` directly (demo "today" override).
- Pydantic v2 DTOs in `schemas/<area>.py`; response models on every route (keeps the generated TypeScript types exact).
- Seed/JSON files are always opened with `encoding="utf-8"` (Windows default code page would corrupt text).
- Tests: `backend/tests/`, fixtures in `conftest.py` give a fresh seeded SQLite DB in a temp dir with `MOCK_DELAY_MS=0`; use `client.get(..., headers={"X-Demo-User": "U01"})`.
- Formatting/lint: black (line length 100) + ruff.

**Frontend**
- `src/api/schema.d.ts` is generated (`npm run gen:api`) from `src/api/openapi.json`, which `backend/scripts/export_openapi.py` writes. Never hand‑edit either; regenerate after backend schema changes.
- All HTTP calls go through `src/api/client.ts` (adds `X-Demo-User`, parses `reasons[]` into `ApiError`). Server state via TanStack Query hooks in `src/features/<area>/api.ts`.
- Pages in `src/pages/` or `src/features/<area>/`; shared UI in `src/components/`; colours only from `src/theme/tokens.ts` (lens: Business amber, Technical blue, Compliance teal; RAG red/amber/green/grey; actor badges: Human neutral, Workflow rule blue outline, Orion agent purple + "AI").
- URL holds filters and tabs (deep links); no `window.open`; downloads via authenticated fetch → blob → `<a download>` (iframe‑safe, A‑17).
- Disabled controls always carry a tooltip with the reason (§12). Every list: skeleton, empty state, error toast.
- TypeScript `strict`; eslint + prettier.

---

## 5. Assumptions

Recorded per spec §0 ("choose the simplest behaviour that keeps the demo story working"). Ids are stable; new ones are appended.

- **A‑01 Python version.** The user asked for the latest stable Python to minimise future VAPT findings. Latest stable is **3.15.2** (python.org, 2026‑10‑25). This machine's corporate web filter blocks installer downloads from python.org ("Site Blocked"), so the build is developed and tested on the installed **3.14.7** (a supported, security‑maintained line). Every pinned dependency was verified to publish cp315 Windows wheels; PyYAML (no cp315 wheel yet) is avoided by installing plain `uvicorn` + `watchfiles` instead of `uvicorn[standard]`. `scripts/setup.ps1` prefers 3.15 automatically once installed via an approved channel. Note: 3.14.7 is three patch releases behind 3.14.10 – upgrade either way. *Update 2026‑11‑17:* `winget install Python.Python.3.15` (official PSF manifest) was also tried; it downloads from the same python.org URL, received the filter's block page and correctly aborted with "Installer hash does not match" – nothing was installed. **Action for IT / the user:** allow `https://www.python.org/ftp/python/` or provide Python 3.15.2 through the software center, then run `scripts\setup.ps1` (rebuilds the venv on 3.15 automatically) and `scripts\test.ps1`.
- **A‑02 `make` is not installed on this Windows machine.** A root `Makefile` (`make dev/test/reset`) is provided for macOS/Linux/CI, with PowerShell equivalents `scripts/dev.ps1`, `scripts/test.ps1`, `scripts/reset.ps1`, `scripts/setup.ps1`.
- **A‑03 Spec pack layout.** `orion_spec.zip` was extracted into `docs/`, `seed/`, `reference/` (byte‑identical to the loose copies in the repo root). The loose root copies are left untouched and git‑ignored.
- **A‑04 Seed location.** The backend reads `/seed/*.json` in place (`SEED_DIR`, default `<repo>/seed`) instead of copying files at build time; a future container build copies the folder.
- **A‑05 IRM on seeded transitions.** `sample_transitions.json` has no `irm_user_id`; all seeded transitions use U14 (Fatima Khan, the only IRM).
- **A‑06 Seeded AI transitions other than the flagship** get a `TierAssessment` with proposed = confirmed = `risk_tier`, confirmed by their OR focal and U14, answers empty, rationale "Tier confirmed before Orion (seeded)".
- **A‑07 Flagship critical gap = S45‑014** (red‑team evidence) – spec §8.1's example insight; the flagship's other gaps are Major. The flagship snapshot blocker becomes a High risk as for every transition (§11.3 step 5).
- **A‑08 Synthesis with pinned items.** Flagship override items are treated as fixed when synthesising, and the remaining scope is filled to hit the snapshot's done/gap targets, so the ±3‑point readiness test holds for all 18 transitions (§11.3).
- **A‑09 Approved exceptions cover an item** exactly like a condition: an item whose exception is `Approved` is not "open", not an open/critical gap, and counts as done for readiness and RAG (spec BR‑040 already treats it as acceptable for gate decisions).
- **A‑10 Linked modules.** `OCET` → FW‑008, S45‑006. `SUPPORT_MODEL` → FW‑027…FW‑035 plus the Support Model sheet items (`SM-*`) in the Business/Technical lenses. The 4 Compliance‑lens `SM-*` items stay IRM‑owned: workflow rules never set compliance statuses.
- **A‑11 Default owners (BR‑010 step 6).** Compliance → transition IRM. Business/Technical → first role clearly named in `owner_role_hint` (keywords: "S&T" → OR focal, "Architect" → Architect, "SOM"/"OLM" → OLM, "Project"/"PM" → PM), otherwise the lens default (Business → PM; Technical → Architect when category is "Scope Clarity & Architecture" or kind is "Support model", else PM).
- **A‑12 SG3 stage review** does not require Compliance lens sign‑off: open Compliance items are shown as information, not blockers (BR‑040 "SG3 rule").
- **A‑13 Teams preview is SHOULD.** In the MVP, storyline step 9's "Sofia approves the AtD card" is done in the Approvals inbox; the same Adaptive Card JSON (with Approve/Reject `Action.Execute`) is visible in the Outbox preview.
- **A‑14 OCET Excel export is SHOULD** and is not built in the MVP.
- **A‑15 Demo clock.** `today()` = admin override (Demo controls) → `SEED_DATE` → real date. `now()` = `today()` + real time of day, so audit timestamps stay coherent after "Set today".
- **A‑16 Identifiers.** String ids where the seed provides them (`TR-0001`, `EVD-001`, `ACT-001`, `CON-001`, `EX-01`, `CR-01`); new records continue the sequence (`TR-0019`, `ACT-004`, …). Other entities use integer ids. Deep links use the playbook item id (`?item=S45-014`).
- **A‑17 Downloads** use authenticated `fetch` → blob → temporary `<a download>`; no `window.open` (works inside the Teams iframe later).
- **A‑18 Mock latency** is configurable with `MOCK_DELAY_MS` (default 600 ms, 0 in tests) and never counted in NFR‑05.
- **A‑19 Frontend versions.** TypeScript 5.9.3 (TS 6/7 are not yet supported by `typescript-eslint`/`openapi-typescript`); `@xyflow/react` 12.x (spec's React Flow API; v13 is a fresh major).
- **A‑20 Gate history** is seeded only for the flagship (from the seed); other transitions show an empty timeline until reviews are recorded.
- **A‑21 Infrastructure** projects behave like Normal (Framework only), per the `reference.json` note.
- **A‑22 Readiness scope.** Items with applicability `To confirm` are outside readiness scope until confirmed; items with status `N/A`/`Not applicable` are removed from the denominator (BR‑020).
- **A‑23 Demo authentication.** `X-Demo-User` is a demo‑only mechanism (no password, spec FR‑001). It is isolated in `deps.get_current_user` so Entra ID token validation can replace it without router changes.
- **A‑24 Security / VAPT hygiene (demo level).** Latest pinned dependencies; `pip-audit` / `npm audit` in M10; CORS allow‑list; security headers (`X-Content-Type-Options`, `Referrer-Policy`, CSP `frame-ancestors` allowing self + Teams domains instead of `X-Frame-Options: DENY`, because the app must run in a Teams iframe); upload filename sanitisation, size and extension limits, path‑traversal safe storage; no stack traces in API errors; no secrets in code (`.env.example` only).
- **A‑25 Drafts, Outbox and notifications core move from M8 to M5**, because AtD/AtO approval requests are drafted by Orion and sent by the OR focal (BR‑040 step 2, FR‑071) and approval steps notify approvers (BR‑041).
- **A‑26 Git.** Repository initialised for this build. `main` holds the untouched spec pack; milestone commits go to branch `build/mvp` (merge when accepted). Commits use this machine's existing git identity.
- **A‑27 Public endpoints.** `GET /reference`, `GET /users` and `GET /health` need no `X-Demo-User` (the login page and forms need them before sign‑in; demo users are fictional). Every other endpoint requires it (router‑level dependency).
- **A‑28 Derived permissions** (rows not in the §3.3 table, mapped to the closest spec row): conditions – OR focal, IRM; request exception – OR focal, IRM; risks – OR focal, IRM; hypercare defects – OR focal, PM, Architect, OLM; eval results – OR focal, PM, Architect; AI profile – OR focal, PM, Architect; autonomous toggle – OR focal; generate/send leadership update – OR focal, Admin; run reminder engine – OR focal, Admin. All in `app/permissions.py`.
- **A‑29 Seeded scope is confirmed.** For the 18 seeded transitions every golden‑set and common item is `Applies` (scope was confirmed before Orion); only tier exclusions are `Not applicable`. New transitions follow BR‑010 (`To confirm` until the OR focal decides).
- **A‑30 Flagship OCET history.** v1 (`Superseded`) = seed lines L1–L5 without the L2 2028 override (initial estimate from IP figures); v2 = the seed lines exactly (`Inputs pending`, L6 monitoring cost `Requested` from the Architect 2 days before the seed date).
- **A‑31 Module tabs.** The workspace tabs "OCET" (`/transitions/:id/ocet`) and "Support model" (`/transitions/:id/support-model`) render the full module pages (§8.10, §8.8) inside the workspace – a superset of the spec's link cards (§8.7 h/i).
- **A‑32 Rounding.** Percentages and synthesis targets use round‑half‑up (not Python's banker's rounding).
- **A‑33 Covered items.** An item covered by an open condition due after the current gate, or by an approved exception (A‑09), is neither "open" nor an open gap, and counts as done (BR‑020).
- **A‑34 Grey RAG.** A transition whose assessment has not been launched (no items yet) shows RAG `Grey` ("not started", §12).
- **A‑35 Tier not yet known.** If assembly runs before any tier is proposed, all AI Playbook items apply (conservative, equivalent to Tier 4); the UI flow always proposes a tier before launch.
- **A‑36 Seeded condition items are pinned** in status synthesis like overrides: the Compliance item becomes `Compliant with conditions` (DE Yes – S02‑012 / CON‑002), a Business/Technical item becomes `In progress` (S3‑019 / CON‑001, so the open condition blocks AtD as the storyline needs). Flagship overrides win if an item is in both.
- **A‑37 ±3‑point synthesis tolerance (§11.3) is mathematically impossible for small lens scopes**: a scope of *n* items can only show multiples of 100/*n*. The test asserts the best achievable value (half a step, `max(3, 50/n + 0.5)`), which equals ±3 for scopes of 17+ items. Measured exceptions (all scopes of 2–5 items): TR‑0018 Compliance 50 vs 64, TR‑0015 Compliance 50 vs 62, TR‑0015 Technical 50 vs 60, TR‑0009 Compliance 50 vs 58, TR‑0004 Business 92 vs 88.
- **A‑38 Infeasible gap budgets are capped.** When a snapshot asks for more open gaps than the scope has non‑done items, every remaining item becomes a gap (TR‑0005: 7 vs 8; TR‑0009: 8 vs 10). Critical gap counts match all 18 snapshots exactly; the flagship matches exactly (9 gaps, 1 critical).
- **A‑39 Synthesis details.** Only `Applies` items are synthesised (tier‑excluded items keep their N/A status); covered items that are not pinned get the plain done status; pinned gap items default to severity Major unless they are the preferred critical item (A‑07).
- **A‑40 Re‑assembly (BR‑010 step 7).** Keeps statuses, notes, severity, DE and evidence of items that still apply; items no longer in the flavour become `Not applicable` with `excluded_by` = `tier`, `project_type` or `portfolio`; a human's own N/A (`excluded_by` empty) is never overridden or restored.
- **A‑41 Blocker notes.** The snapshot blocker becomes a High risk (`CR-05`…, continuing the flagship's CR‑01…04) and the text "Blocker: …" on the first critical gap item's note. For the flagship the override note wins (S45‑014 keeps "Red‑team / prompt‑injection evidence not yet available"); the blocker remains visible as risk CR‑05.
- **A‑42 Library defaults for sources the seed does not describe.** Golden‑set items: category "Portfolio golden set", kind Deliverable, all four project types. Common items: category "Common items", source label "Common items (all portfolios)".
- **A‑43 React Router 7.18.5 instead of v6 (deviation from spec §5.1, for VAPT).** The whole 6.x line carries two moderate advisories (GHSA‑wrjc‑x8rr‑h8h6 open redirect via backslash; GHSA‑337j‑9hxr‑rhxg) with no 6.x fix; v7 supports React 18 and keeps the same API for this app (data router, hooks, `NavLink`). The login `?next=` parameter is additionally validated against the origin.
- **A‑44 `excluded_by` vocabulary** is `tier | project_type | portfolio` (portfolio added for golden sets of a previous portfolio, A‑40).
- **A‑45 Seeded Retail Site Systems transitions have no site rows**; their RSS‑01 status comes from synthesis and is not tied to `Transition.sites`. Site rows are captured for new transitions at intake (AC‑05).
- **A‑46 Test client and pins.** `httpx2` replaces `httpx` for FastAPI/Starlette's `TestClient` (Starlette deprecates `httpx`). `backend/constraints.txt` pins the full transitive dependency set (`pip install -r requirements-dev.txt -c constraints.txt`) and is what `pip-audit` scans.
- **A‑47 Middleware design.** Pure ASGI middlewares (no `BaseHTTPMiddleware`): security headers outermost, then CORS, request‑size limit (413 above `MAX_UPLOAD_MB`), then an unhandled‑error converter, so even 500 responses carry security and CORS headers and never leak internals. Framework 404/405 errors use the same `{detail, reasons}` body.
- **A‑48 Configuration is validated** at startup (`AI_MODE` ∈ mock|live, `MAIL_MODE` ∈ mock|graph); `/admin/demo/*` endpoints answer 404 when `DEMO_MODE=false` (M9).
- **A‑49 Dev server port.** Vite binds `127.0.0.1:5173` with `strictPort` (spec §5.4) and proxies `/api` to `127.0.0.1:8000`. On this machine another local app ("SP&A One", `node.exe`) already listens on `127.0.0.1:5173`; previously Vite silently took `[::1]:5173`, so `localhost:5173` could reach either app. Now a conflict fails with "Port 5173 is already in use"; run `scripts\dev.ps1 -WebPort 5174` (or `npm run dev -- --port 5174`) and open `http://127.0.0.1:5174`.

---

## 6. Open questions for the S&T team (spec §17, shown in README)

1. First module for the real build: AI transition flavour or a business portfolio (e.g. GCC)?
2. Confirm lens per Framework activity and final golden sets per portfolio.
3. Tier‑specific eval thresholds.
4. Who signs AtD/AtO exactly (SOM / OR focal / IRM); is ERS the same as IRM?
5. OCET: default growth rules, currency, horizon (5 vs 6 years), must the Excel template be kept?
6. Support model PPT template ("PTIV ORB" format) – please share the master.
7. Access for the real build: ServiceNow API, Confluence, SharePoint site, Orion shared mailbox (Graph), Azure OpenAI / Foundry, Teams app approval.

---

## 7. Status log

| Date | Milestone | Notes |
|---|---|---|
| 2026‑11‑17 | Setup | Spec pack extracted; repo initialised (`main` = spec pack, work on `build/mvp`); PLAN.md created; toolchain verified (A‑01, A‑02, A‑19). |
| 2026‑11‑17 | M1 Foundation | Done. Backend: 164 tests green (rules, synthesis ±3 per A‑37, seed, API core, security, services, cards), ruff + black clean, `pip-audit` 0 known vulns over the full pin set. Frontend: strict build + lint green, `npm audit` 0 vulns after React Router 7.18.5 (A‑43). Live smoke test via the Vite proxy (users, /me 401/200, 404/405 contract, security headers, deep link). Review findings (21) fixed or documented (A‑36…A‑49). Python 3.15.2 still blocked by the corporate filter, also via winget (A‑01). |
