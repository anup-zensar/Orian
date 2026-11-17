# Orion – Operate Readiness Agent · Demo Build Requirements

Version 1.0 · 16 Nov 2026 · Audience: Claude Code (implementer) and the delivery team

> **Purpose of this build:** a working, clickable **demo** (frontend + backend) that shows the client (Shell Mobility S&T / Operate Readiness team) exactly what we plan to build. Every external system and every AI capability is a **dummy (mock) service** behind a clean interface, so the real integration can be dropped in later without touching the UI or business logic.
>
> **Read this whole document before writing code.** Seed data lives in `/seed/*.json` and is the source of truth for checklists, portfolios, reference lists and demo data. The client's HTML prototype (in `/reference/`) is used **only to cross-check form fields and option lists** — do **not** copy its layout, CSS, JavaScript or solution logic.

---

## 0. How to use this document

- Requirements are numbered (`FR-…` functional, `BR-…` business rule, `NFR-…` non-functional, `AC-…` acceptance). Reference them in commits and in `PLAN.md`.
- **MUST** = required for the demo. **SHOULD** = build if time allows, after all MUSTs. **LATER** = do not build; leave a placeholder or a stub only where stated.
- Where this document and the seed files disagree, **the seed files win for data**, and **this document wins for behaviour**.
- If something is ambiguous, choose the simplest behaviour that keeps the demo story working, write the assumption into `PLAN.md` under "Assumptions", and continue. Do not stop to ask.

---

## 1. Product summary

### 1.1 The problem
Shell Mobility's Supportability & Transition (S&T) team runs "operate readiness" for every project moving from Project to Operations (SOM). Each transition passes stage gates SG0 → SG6 with:
- ~**72 standard activities** (Operate Readiness Framework) plus **5–10 portfolio-specific items** ("golden set"), and for AI solutions an **AI Playbook** checklist that depends on the agent's **risk tier**;
- two heavy manual deliverables: the **OCET** (5-year run-and-maintain cost estimate) and the **support model** (landscape + support flows);
- constant **chasing**: reminders, evidence requests, input requests, approval requests.

Today this is done in Excel and email. Status goes stale on transitions that run a year or more, and the team spends most of its time chasing.

### 1.2 The client's success measure
> "If my team spends 8 hours on this work, how can I make it 4?"

The value is **not** a nicer tracker. The value is the system **taking action**: reminding owners, requesting inputs, routing approvals when criteria are met, telling the OR focal whether a gate decision can be taken and where the gap is, and generating the support model.

### 1.3 What Orion is
**Orion** (client's working name) = an **Operate Readiness workspace** (web app, system of record, workflow) + an **AI agent** (assistant panel) that drafts, recommends, chases and generates — while **people make every decision**.

Two kinds of automation, and the UI must label which is which (the client explicitly asked "why is this not agentic?"):
- **Workflow rules (deterministic):** checklist assembly, status, readiness %, RAG, gate blocking, approval chains, OCET maths, reminder triggers.
- **Orion agent (AI):** readiness assessment narrative and recommendations, gap → action proposals, drafting chasers and leadership updates, AI-transition (playbook) assessment, support model generation from walkthrough + documents, Q&A over transition data.

### 1.4 Demo goals (what the client must see)
1. One place for every transition, with a control tower view by portfolio, region and gate.
2. A new transition started in minutes: intake form → (AI) tiering → portfolio scope → checklist auto-assembled for that **transition flavour**.
3. Readiness by gate and lens (Business / Technical / Compliance), evidence, gaps, actions.
4. "Are we ready for AtD? Where is the gap?" answered by Orion, with one-click chasers.
5. OCET built from inputs with a 5-year projection and a **Planner → OLM** approval chain.
6. Support model generated from a walkthrough recording + Confluence/solution design document → editable landscape → **downloadable PPT**.
7. When criteria are met, Orion asks the OLM to approve AtD; the approval is recorded with a full audit trail.
8. A preview of how the same features will appear in **Microsoft Teams** (Phase 2).

---

## 2. Scope

### 2.1 In scope (MUST)
Login with demo role switcher · Dashboard · Control tower · Transition register · New transition (intake) · AI tiering wizard · Portfolio scope confirmation · Transition workspace (overview, assessment, gaps & actions, evidence, conditions/exceptions/risks, gate decisions, hypercare defects, AI playbook & eval metrics, activity) · Approvals inbox · OCET module · Support model generator with PPT export · Orion assistant panel (chat + quick actions + proposal cards) · Reminder engine + Orion drafts queue · Outbox (mock email) + notifications · Leadership update generator · Admin: playbook & configuration · Audit trail · Demo controls (reset / fast-forward) · Mock services for AI, Graph mail, Teams, ServiceNow, SharePoint, Confluence, transcript.

### 2.2 SHOULD
Teams preview page · Risk acceptance (conditional AtO) flow · Excel export of OCET · Support Model Retriever (search over past support models) · Optional live LLM mode behind the AI interface.

### 2.3 LATER (do not build)
Real SSO (Entra ID), real Microsoft Graph / ServiceNow / Confluence / SharePoint calls, real Teams bot, autonomous mode beyond reminders, post-AtO "AI Ops" pages from the prototype (operational monitoring, AI incidents, kill switch, model governance, executive health), mobile layouts, multi-language.

---

## 3. Users, roles and permissions

### 3.1 Roles (from `seed/reference.json → roles`)
| Code | Who | Main jobs in Orion |
|---|---|---|
| `OR_FOCAL` | S&T Operate Readiness focal | Owns transitions; confirms scope/applicability; reviews Orion drafts; records stage reviews and gate decisions; accepts evidence (Business/Technical) |
| `PM` | Project manager | Updates item status, uploads evidence, supplies OCET inputs |
| `ARCHITECT` | Solution architect | Technical items, architecture docs, support model inputs and review, OCET technical inputs |
| `OLM` | SOM Ops lead (OLM) | Business lens sign-off; approves AtD/AtO; final OCET approval; agrees support model |
| `PLANNER` | Finance planner | First OCET approval step |
| `IRM` | Compliance (IRM) | Compliance item statuses, design effectiveness, compliance sign-off at every gate, exceptions |
| `LEADERSHIP` | Head of SOM / leadership | Read-only: dashboard, control tower, leadership updates |
| `ADMIN` | Playbook admin | Edits playbooks, golden sets, flavour rules, eval thresholds, approval chains, reminder rules; demo controls |

### 3.2 Demo login (FR-001 MUST)
- Login page lists the demo users from `seed/demo_users.json` (name + role badge). Clicking one logs in. No password.
- Top bar shows the current user and a **"Switch user"** dropdown available on every page (essential for the approval demo).
- Frontend sends `X-Demo-User: <userId>` on every API call. Backend resolves the user and enforces permissions (§3.3). Structure the auth dependency so it can later be replaced by Entra ID token validation without changing routers.

### 3.3 Permission matrix (BR-001 MUST)
| Action | OR_FOCAL | PM | ARCHITECT | OLM | PLANNER | IRM | LEADERSHIP | ADMIN |
|---|---|---|---|---|---|---|---|---|
| View all transitions, control tower | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create transition (intake) | ✓ | ✓ | – | – | – | – | – | ✓ |
| Confirm tier | ✓ (propose) | – | – | – | – | ✓ (confirm) | – | – |
| Confirm scope / applicability, mark N/A | ✓ | – | – | – | – | – | – | – |
| Update Business/Technical item status | ✓ | ✓ | ✓ | ✓ | – | – | – | – |
| Update Compliance item status + DE | – | – | – | – | – | ✓ | – | – |
| Upload/link evidence | ✓ | ✓ | ✓ | ✓ | – | ✓ | – | – |
| Accept/reject evidence | ✓ (B/T) | – | – | – | – | ✓ (C) | – | – |
| Create/close actions | ✓ | ✓ | ✓ | ✓ | – | ✓ | – | – |
| Record stage review (SG0/SG2/SG3/Hypercare) | ✓ | – | – | – | – | – | – | – |
| Approve in an approval chain | only if the step's role matches the user | | | | | | | |
| Record gate decision (AtD/AtO/Closure) | ✓ (after chain approved) | – | – | – | – | – | – | – |
| Edit OCET lines | ✓ | ✓ | ✓ | – | – | – | – | – |
| Generate / edit support model | ✓ | – | ✓ | – | – | – | – | – |
| Send Orion drafts (assistive mode) | ✓ | – | – | – | – | – | – | – |
| Admin configuration, demo controls | – | – | – | – | – | – | – | ✓ |

Unauthorised actions: hide or disable the control in the UI with a tooltip ("Only IRM can set compliance status"), and return `403` from the API.

---

## 4. Core concepts (glossary the code must model)

- **Stage gates** — one gate model everywhere (fixes an inconsistency in the prototype). From `reference.json → gates`:
  `SG0` Initiate & tiering → `SG2` Scope, blueprint & architecture (SG1–SG2) → `SG3` Build & test → `SG4_ATD` **Agreement to Deploy** → `SG5_HYPERCARE` Hypercare → `SG6_ATO` **Agreement to Operate** → `CLOSURE`.
  Gate types: `stage_review` (outcomes Proceed / Proceed with conditions / Hold), `decision` (Approve / Approve with conditions / Return), `closure` (Close / Return).
- **Current gate** of a transition = the gate it is currently working towards (next review/decision).
- **Item** = one checklist line a transition must satisfy. Sources: Framework activity (`FW-…`), AI Playbook item (`S0…/S02…/S3…/S45…/S6…/SM…/OC…/TR…/UD…` ids as in seed), portfolio golden-set item (`GCC-01`, `TEL-06`…), common item (`ALL-01`, `ALL-02`).
- **Lens** — every item belongs to exactly one lens: **Business**, **Technical**, **Compliance**. Lens colours: Business = amber, Technical = blue, Compliance = teal (use consistently in chips, bars, charts).
- **Transition flavour** = project type (`Normal`, `Infrastructure`, `Agentic AI`, `Combined`) + portfolio (+ region/market) (+ tier for AI). The flavour decides which items apply. The client said: *"My policies are changing with every flavour"* — flavour handling is a first-class concept, not an afterthought.
- **Golden set** — portfolio-specific deliverables (5–10 per portfolio), some mandatory, others confirmed by the OR focal.
- **Risk tier (1–4)** — for Agentic AI / Combined. Decides which AI Playbook items apply and which eval-metric thresholds are used.
- **Readiness %** — per lens, over items due at or before the current gate (BR-020).
- **Gap** — an item in status `Gap` or `Non-compliant`. Each gap has a **severity**: Critical / Major / Minor.
- **Condition** — an open item allowed to carry past a gate with an owner and a due gate.
- **Exception** — a compliance control deviation approved by CISO/BISO (mocked).
- **AtD / AtO** — Agreement to Deploy (go-live decision, ~SG4) / Agreement to Operate (formal handover to SOM, SG6).
- **OCET** — Operate Cost Estimation Toolkit: 5-year run-and-maintain projection by cost category; approved Planner → OLM.
- **Support model** — landscape (central app, integrations, hosting, vendors), support tiers L1/L2/L3, responsibilities, contacts/SLAs, open questions.
- **Assistive mode** (default) — Orion drafts and proposes; a human sends/accepts. **Autonomous mode** (opt-in per transition) — routine reminders are sent without per-item approval. Decisions are always human.

---

## 5. Architecture and tech stack

### 5.1 Stack (MUST)
**Frontend**
- React 18 + TypeScript + Vite
- **Fluent UI React v9** (`@fluentui/react-components`, `@fluentui/react-icons`) — chosen so the UI looks native when embedded in Teams later
- React Router v6, TanStack Query v5, react-hook-form + zod
- Recharts (charts), `@xyflow/react` (React Flow) for the support model landscape editor
- dayjs for dates

**Backend**
- Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x
- SQLite (`backend/orion.db`) for the demo; keep the engine URL configurable (Azure SQL/PostgreSQL later)
- `python-pptx` (support model PPT), `openpyxl` (OCET Excel export), APScheduler (reminder job), `pytest` + `httpx`

### 5.2 Repository layout (MUST)
```
orion/
  README.md                 # how to run, demo users, demo script link
  PLAN.md                   # created by Claude Code: milestones, assumptions, status
  docs/REQUIREMENTS.md      # this file
  docs/DEMO_SCRIPT.md       # created by Claude Code from §13, verified against the build
  reference/                # client HTML prototype (read-only reference)
  seed/                     # provided JSON seed files (copied into backend at build)
  backend/
    app/
      main.py  config.py  db.py  deps.py (current user, permissions)
      models/        # SQLAlchemy models (§6)
      schemas/       # Pydantic DTOs
      routers/       # one router per area (§9)
      rules/         # PURE functions, unit-tested: checklist.py readiness.py rag.py tiering.py gates.py ocet.py reminders.py
      services/
        interfaces.py   # Protocols: AIService, MailService, NotificationService, ServiceNowService,
                        # DocumentStore (SharePoint), ConfluenceService, TranscriptService, SupportModelGenerator
        mock/           # MUST: mock implementations (default)
        live/           # stubs only: classes with NotImplementedError + docstring of the real call
        factory.py      # picks mock/live from config
      seed/loader.py    # loads /seed/*.json, synthesises statuses (§11.3), idempotent
      storage/          # uploaded files, generated PPT/XLSX
    tests/
  frontend/
    src/
      api/ (typed client)  components/  features/<area>/  pages/  theme/  hooks/
```

### 5.3 Configuration (`backend/.env`, MUST)
```
DEMO_MODE=true              # shows Demo controls, enables /admin/demo endpoints
AI_MODE=mock                # mock | live  (live = optional Azure OpenAI for free-text chat only)
MAIL_MODE=mock              # mock | graph (graph = stub)
ORION_MAILBOX=orion-noreply@example.com
REMINDER_JOB_ENABLED=false  # true = APScheduler runs reminder engine every 15 min
SEED_DATE=                  # optional fixed "today" for deterministic demos (YYYY-MM-DD)
DATABASE_URL=sqlite:///./orion.db
AZURE_OPENAI_ENDPOINT= AZURE_OPENAI_KEY= AZURE_OPENAI_DEPLOYMENT=   # only for AI_MODE=live
```

### 5.4 Run (MUST)
- `backend`: `pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000` (seeds automatically on first start if DB empty).
- `frontend`: `npm install && npm run dev` (port 5173, proxy `/api` → 8000).
- One-command option: root `Makefile` or `scripts/dev.sh` that starts both.
- `README.md` lists demo users and links `docs/DEMO_SCRIPT.md`.

### 5.5 Teams-ready constraints (NFR, MUST)
- API-first: every UI action goes through the REST API (the Teams bot will reuse it).
- No pop-up windows or `window.open` for core flows; app must work inside an iframe (Teams tab later).
- Deep links: every transition, item, approval and support model has a stable URL (e.g. `/transitions/TR-0001/assessment?item=S45-014`).
- Notification payloads are rendered as **Adaptive Card JSON** in the mock Teams service (§10.4), so Phase 2 can post them unchanged.

---

## 6. Data model (MUST)

Use these entities (SQLAlchemy). Names are guidance; keep fields. All tables get `created_at`, `updated_at`. IDs are strings where the seed provides them.

**User** `id, name, email, role, focal_label?`

**PlaybookItem** (library; loaded from seed) `id, source (FRAMEWORK|AI_PLAYBOOK|PORTFOLIO|COMMON), portfolio?, title, description, detail, gate, lens, lens_is_suggested, category/section, kind (Check|Question|KPI|Evidence|Support model|Deliverable), applicable_tiers[int], tier_label, tier_unspecified, mandatory, mandatory_rule (always|if_applicable), applies_to_project_types[], owner_role_hint, automation_tag, phase_window, source_sheet, source_cell, note, is_compliance_control, active`

**FlavourRule** `project_type, checklists[] (FRAMEWORK, AI_PLAYBOOK), requires_tiering` (from `reference.json → project_types`; editable in Admin)

**Portfolio** `name, code, focus_areas[], intake_extra_fields (json)`

**Transition**
`id, name, servicenow_project_id?, description, portfolio, region, market, project_type, investment_type?, delivery_method?, audience, write_actions, sensitive_data, target_gate, current_gate, risk_tier?, tier_status (Proposed|Confirmed), or_focal_user_id, pm_user_id, architect_user_id, olm_user_id, irm_user_id, next_decision_date, autonomous_mode (bool, default false), status (Active|Closed), sites (json, Retail only), blocker_note?, is_flagship`

**TierAssessment** `transition_id, answers {TQ1..TQ5: bool}, proposed_tier, rationale[], proposed_by, confirmed_tier?, confirmed_by_or_focal?, confirmed_by_irm?, confirmed_at?`

**TransitionItem** (one per applicable library item per transition)
`id, transition_id, playbook_item_id, applicability (Applies|Not applicable|To confirm), na_reason?, excluded_by (tier|project_type|null), status, gap_severity? (Critical|Major|Minor), owner_user_id?, due_gate, design_effectiveness? (–|Yes|No|N/A, Compliance only), note, linked_module? (OCET|SUPPORT_MODEL|null), last_updated_by, last_updated_source (Human|Workflow rule|Orion agent — Orion never sets status, see BR-050)`

**Evidence** `id, transition_id, transition_item_id?, title, type (Document|Link|Email sign-off|Recording|Generated), url, file_path?, submitted_by, status (Submitted|Accepted|Rejected), reviewed_by?, review_note?`

**Action** `id, transition_id, title, item_ids[], owner_user_id, due_date, status (Open|In progress|Done|Cancelled), priority (High|Medium|Low), origin (Human|Orion proposal accepted by <user>)`

**Condition** `id, transition_id, transition_item_id, set_at_gate, due_gate, owner_user_id, text, status (Open|Closed)`

**Exception** `ref, transition_id, transition_item_id, text, status (Draft|Pending CISO/BISO|Approved|Rejected)`

**Risk** `id, transition_id, title, rating (High|Medium|Low), decision, item_ids[]`

**GateReview** `id, transition_id, gate, outcome, decided_by, decided_at, note, conditions_created[], approval_request_id?`

**ApprovalRequest** `id, type (OCET|AtD|AtO|SUPPORT_MODEL|EXCEPTION|RISK_ACCEPTANCE), transition_id, subject_id (e.g. OCET version id), steps [{step, role, approver_user_id, status (Waiting|Pending|Approved|Rejected), decided_at, comment}], status (Pending|Approved|Rejected|Cancelled), created_by, created_source`

**HypercareDefect** `id, transition_id, title, priority (P1|P2|P3|P4), status (Open|Resolved), owner`

**AIProfile** (Agentic AI / Combined only) questionnaire: `infrastructure_solution, agentic_framework, multi_agent_orchestration (bool), number_of_users, agentic_workflows, models_used, data_sources, hosting, write_actions_detail`

**EvalResult** `transition_id, metric_id, value_number?, value_text?, pass (bool|null), evaluated_at`

**EvalTarget** (from `eval_metrics.json`) `metric_id, metric, tier, target_text, operator?, value?, unit?, evaluation (auto|manual)`

**OcetEstimate** `id, transition_id, currency, start_year, horizon_years, current_version`
**OcetVersion** `id, estimate_id, version, status (Draft|Inputs pending|Submitted|Planner approved|Approved|Rejected|Superseded), note, created_by, submitted_at?, approval_request_id?`
**OcetLine** `id, version_id, category, description, vendor, pricing_basis, base_amount?, growth_pct, year_overrides {year: pct}, override_reason?, input_owner_role, input_owner_user_id?, input_status (Provided|Requested|Missing)`

**SupportModel** `id, transition_id, version, status (Draft|In review|Agreed), inputs {confluence_url?, files[]}, landscape (json – schema in §8.8), generated_pptx_path?, approval_request_id?`

**OrionDraft** (assistive queue) `id, transition_id?, kind (Reminder|Chaser|Input request|Approval request|Leadership update), to[], cc[], subject, body_html, rule_id?, status (Draft|Sent|Discarded), created_source (Workflow rule|Orion agent), sent_by?`

**OutboxMessage** (mock Graph) `id, channel (Email|Teams), from, to[], cc[], subject, body_html, adaptive_card_json?, related_ids, sent_at, mode (mock)`

**Notification** (in-app bell) `id, user_id, text, link, read`

**AuditEvent** `id, at, actor_user_id?, actor_type (Human|Workflow rule|Orion agent|System), transition_id?, entity, entity_id, action, before (json), after (json), note`

**LeadershipUpdate** `id, scope (transition|portfolio|all), scope_id?, content_md, generated_by, created_at`

---

## 7. Business rules (implement in `backend/app/rules/` as pure, unit-tested functions)

### 7.1 Checklist assembly (BR-010 MUST)
When a transition is created (and whenever project type, tier or portfolio changes, after confirmation):
1. Look up the **flavour rule** for the project type → checklists to include (`FRAMEWORK`, `AI_PLAYBOOK`). Default from `reference.json`: Normal / Infrastructure → Framework; Agentic AI / Combined → Framework + AI Playbook.
2. **Framework**: add all active Framework items (72).
3. **AI Playbook** (if included): add items whose `applicable_tiers` contains the transition tier. Items outside the tier are still created with `applicability = Not applicable`, `excluded_by = tier`, so the UI can show "13 items not applicable for Tier 2 (view)". Items with `tier_unspecified = true` apply to all tiers and show a small "tier to confirm" marker.
   - If tier is not yet confirmed, use the **proposed** tier and show a banner "Checklist based on proposed Tier N — confirm tier to finalise".
4. **Portfolio golden set**: add the portfolio's items. `mandatory=true` → `Applies`. Others → `To confirm` (OR focal decides on the Scope page).
5. **Common items** `ALL-01` (always) and `ALL-02` (if applicable → `To confirm`).
6. Set `due_gate` = item gate; `status` = first status of its lens list (`Not started`); default owner by lens: Business → PM, Technical → Architect if category is "Scope Clarity & Architecture" or kind is "Support model", else PM; Compliance → IRM. Use `owner_role_hint` text where it clearly names a role.
7. Re-assembly after a tier change must **keep** existing statuses, evidence and notes for items that still apply, and mark newly excluded items `Not applicable (tier)`. Log an audit event listing added/excluded item counts.

### 7.2 AI tiering (BR-011 MUST)
Inputs: intake fields (audience, write actions, sensitive data) + 5 questions `TQ1–TQ5` (`reference.json → tier_questions`). Deterministic proposal, evaluated in order:
1. `TQ2` yes (autonomous writes to systems of record) **or** `TQ3` yes (regulated function) **or** sensitive data = `SOX / MC` → **Tier 4**
2. `TQ1` yes (external parties) **or** audience = `External` **or** sensitive data = `Personal sensitive` **or** write actions = `Yes` → **Tier 3**
3. `TQ5` yes (time-boxed <90 days, <100 users, no autonomous writes) → **Tier 1**
4. `TQ4` yes (internal, bounded, advisory) → **Tier 2**
5. Otherwise → **Tier 3** (conservative default)

Return the proposed tier + a rationale list ("Internal audience", "No write actions", "TQ4 = yes → Tier 2"). Show the three tier dimensions and the tier definition card (definition, examples, builder persona) next to the proposal. **Confirmation is human:** OR focal proposes, IRM confirms (`tier_status = Confirmed`). Orion may explain the proposal but never confirms it.

### 7.3 Readiness and progress (BR-020 MUST)
For a transition at current gate `G` (order `o(G)`), per lens `L`:
- `scope_L` = items of lens L with applicability `Applies` and `o(due_gate) ≤ o(G)`, excluding N/A statuses.
- `done_L` = items in `scope_L` with status in `done_statuses` (`Complete`, `Compliant`, `Compliant with conditions`) **or** covered by an **open condition** whose due gate is later than G.
- `readiness_L = round(100 × done_L / |scope_L|)` (100 if scope empty).
- `overall = round(mean of the three lens values)`.
- **Open gaps** = items in scope with status in `gap_statuses` (`Gap`, `Non-compliant`).
- **Critical gaps** = open gaps with `gap_severity = Critical`.
- **Not started / in progress** counts are shown separately (an item in progress is not a gap).
- N/A does **not** count as done; it is removed from the denominator (the prototype counted N/A as done, which inflated readiness).

### 7.4 RAG (BR-021 MUST) — from `reference.json → rag_rule`
- **Red** if `critical_gaps ≥ 2` OR `min(readiness_L) < 50` OR (`critical_gaps ≥ 1` AND `days_to_next_decision ≤ 7`)
- **Amber** if `critical_gaps ≥ 1` OR `min(readiness_L) < 70`
- **Green** otherwise.
Compute live; never store RAG.

### 7.5 Status rules (BR-030 MUST)
- Business/Technical statuses: `Not started, In progress, Complete, Gap, N/A`. Compliance: `Not started, In review, Compliant, Compliant with conditions, Non-compliant, Not applicable`.
- Setting `Gap` / `Non-compliant` requires `gap_severity` and a note.
- Setting `N/A` / `Not applicable` requires a reason; only the OR focal (B/T) or IRM (C) can do it.
- `Compliant with conditions` requires creating a Condition (owner, due gate, text).
- Compliance items carry **design effectiveness** (`–, Yes, No, N/A`); `Compliant` requires DE = Yes or N/A.
- **Eval metrics (AI flavours):** a failed eval metric (result present and not meeting the tier target) counts as an open **Technical** blocker at `SG4_ATD` in the readiness check and decision rules (shown as "Eval metric below target: <metric> <result> vs <target>"). Metrics without a result are listed as "not yet evaluated" (warning, not blocking).
- **Linked modules:** items with `linked_module = OCET` (`FW-008`, `S45-006`) move to `Complete` automatically when the OCET version is **Approved**; items linked to `SUPPORT_MODEL` (`FW-027`–`FW-035`, Support Model sheet items) move to `Complete` when the support model is **Agreed**. Actor type = `Workflow rule`. This is a deterministic workflow outcome of a human approval, not an AI decision.
- Every change writes an AuditEvent with before/after.

### 7.6 Gate reviews and decisions (BR-040 MUST)
**Stage reviews** (`SG0`, `SG2`, `SG3`, `SG5_HYPERCARE`) — recorded by the OR focal:
- `Proceed`: only if no open items due ≤ this gate (except those covered by conditions).
- `Proceed with conditions`: allowed when remaining open items are Business/Technical (each gets a Condition with owner + due gate) and Compliance items are either compliant, under an approved exception, or conditioned by IRM. SG0 additionally requires a **confirmed tier** for AI flavours.
- `Hold`: always allowed.
- **SG3 rule from the client playbook:** IRM gives no attestation at SG3 (evidence only); Compliance lens sign-off is not required at SG3.
- After `Proceed`/`Proceed with conditions`, `current_gate` advances to the next gate.

**Decision gates** (`SG4_ATD`, `SG6_ATO`):
1. **Readiness check** (Orion + rules) shows: blocking items, gaps by lens, open conditions, pending exceptions, approval chain status, recommended actions.
2. **Request approval** creates an ApprovalRequest using `reference.json → approval_chains` (AtD: OLM → IRM; AtO: IRM → OLM). In assistive mode Orion drafts the request and the OR focal sends it (FR-071).
3. After the chain is **Approved**, the OR focal records the decision: `Approve`, `Approve with conditions`, or `Return`.
4. **Approve** is enabled only if: no open items due ≤ gate (except covered by conditions), no open Critical gaps, all Compliance items due ≤ gate are compliant / not applicable / under approved exception, chain approved.
5. **Approve with conditions**: same as above, except open Business/Technical items are allowed and each becomes a Condition (owner + due gate required in the dialog). Compliance items still need compliance or an approved exception (compliance can only be conditioned via exception). Critical gaps still block.
6. **Return**: always allowed; requires a note; chain is cancelled.
7. **AtO extra rules** (from the Framework / client): no `Open` hypercare defects with priority P1/P2; hypercare issue tracker exists (≥1 defect record or explicit "no defects" confirmation); all AtD conditions closed or re-conditioned with IRM agreement; OCET Approved; support model Agreed.
8. **Closure** (`CLOSURE`): `Close` only if no open conditions, no open actions, no open defects and all carried items are done. **No conditions allowed at closure.** `Return` otherwise.
9. **Carried items:** open items from earlier gates that were conditioned are listed on every later gate page ("Carried from SG3: S3-019 stress test – owner Asha – due AtD").

### 7.7 Approval chains (BR-041 MUST)
- Steps execute sequentially. Only a user whose role equals the step role can act (choose a specific user from that role at request time; default from transition roles: `olm_user_id`, `irm_user_id`; Planner = first PLANNER user).
- Actions: Approve (optional comment) or Reject (comment required). Reject sets the whole request `Rejected` and notifies the requester.
- On each step change: notification to the next approver (in-app + mock email + mock Teams Adaptive Card with Approve/Reject buttons — §10.4).
- OCET chain: `Planner → OLM` (on final approval, OCET version `Approved`, linked items complete).
- Exception chain: `IRM → CISO/BISO` (the CISO/BISO step is **mocked**: an "Approve as CISO/BISO (mock)" button visible to IRM in demo mode).

### 7.8 Reminder engine (BR-060 MUST) — `rules/reminders.py`
Runs on demand ("Run reminder engine now" button on the Orion drafts page and in Demo controls) and, if `REMINDER_JOB_ENABLED`, every 15 minutes. Each rule produces **OrionDraft** records (assistive) or sends directly (autonomous, only where marked):

| Rule | Trigger | Recipient | Autonomous-eligible |
|---|---|---|---|
| R1 Items due soon | Open items due at current gate and `next_decision_date − today ≤ 14 days` | Item owner (one **digest** per owner per transition) | Yes |
| R2 Overdue actions | Action `due_date < today` and not done | Owner, cc OR focal | Yes |
| R3 Pending approval | Approval step pending > 2 days → reminder; > 5 days → escalation to OR focal | Approver / OR focal | Yes (reminder only) |
| R4 Gate ready | All items due ≤ current **decision** gate done (or conditioned) and no chain open | OR focal: "Ready for AtD – send approval request to OLM?" | No – always needs confirmation |
| R5 Missing inputs | OCET line `input_status = Requested` for > 3 days | Input owner | Yes |
| R6 Monitoring trigger | Transition reaches `SG2` | Architect: request monitoring requirements (FW-048–FW-054: tools e.g. Azure Monitor / Dynatrace / AppDynamics, thresholds, dashboards) | No |
| R7 Support model prompt | Evidence for `FW-006` (architecture walkthrough) accepted and no support model exists | OR focal: "Create support model now?" | No |

- De-duplicate: never create a second open draft for the same rule + transition + recipient within 24 h.
- Each draft shows its source label: **Workflow rule R1** etc. Text is generated by the AI service (mock) from a template.
- Autonomous mode is per transition (toggle on the transition overview, OR focal only, default off); it only affects rules marked "Yes".

### 7.9 OCET calculation (BR-070 MUST) — `rules/ocet.py`
- Years = `start_year … start_year + horizon_years − 1` (default 5 years).
- For each line: `amount[start_year] = base_amount`; for later years `amount[y] = amount[y−1] × (1 + g_y/100)` where `g_y = year_overrides[y]` if present else `growth_pct` (compounding).
- Lines with missing `base_amount` contribute 0 and mark the version "Inputs pending".
- Outputs: per-line yearly amounts, totals by category × year, grand total by year, 5-year total, and **variance vs previous version** (per line and per category).
- Worked example that must pass a unit test: base 100,000 at 10% → 100,000 · 110,000 · 121,000 · 133,100 · 146,410.
- Rounding: keep full precision in calculations; display in thousands with one decimal ("146.4k") and full numbers in the table/export.
- Versioning: editing a `Submitted`/`Approved` version is not allowed; "Create new version" copies lines into `vN+1` (`Draft`) and marks the previous one `Superseded` only when vN+1 is submitted.
- Status flow: `Draft → (Inputs pending) → Submitted → Planner approved → Approved` or `Rejected` (back to Draft for a new version).

### 7.10 Orion guardrails (BR-050 MUST)
- The Orion agent **never** changes an item status, applicability, tier, evidence acceptance, condition, approval or gate decision. It produces **proposals** (cards with a button) that a permitted human clicks; the resulting change is logged with `actor_type = Human` and `note = "Accepted Orion proposal <id>"`.
- Enforce in the backend: the Orion service has no write access to those endpoints; proposals are stored and executed only via the normal user endpoints.
- Every Orion output is labelled **"Orion agent"** with a small "AI" badge; workflow outputs are labelled **"Workflow rule"**. A persistent footer in the Orion panel: *"Orion recommends and drafts. People decide."*
- Emails/Teams messages in assistive mode are never sent without a human clicking **Send**.

---

## 8. Screens and features

Global layout (FR-002 MUST): left navigation, top bar (app name "Orion", global search for transitions, notifications bell, **Orion** button that opens the assistant side panel, current user + Switch user). Navigation items:
`Dashboard · Control tower · Transitions · New transition · Approvals · Orion drafts · Outbox · Leadership updates · Support models · Admin (ADMIN only) · Audit trail · Teams preview (SHOULD)`.

### 8.1 Dashboard (FR-010 MUST)
Role-aware home page.
- KPI tiles: My open items · My pending approvals · Transitions I own (OR focal) · Decisions due in 14 days · Critical gaps (in my transitions).
- "My work" table: items/actions/approvals assigned to me with due dates and deep links.
- "Orion insights" card (agent): 3–5 bullet insights generated from data (e.g. "Mobility Knowledge Agent: AtD in 21 days, blocked by 1 critical gap (S45-014 red-team evidence). Draft a chaser?") with action buttons.
- Recent activity (last 10 audit events in my transitions).
- LEADERSHIP sees portfolio summary tiles instead of "My work".

### 8.2 Control tower (FR-011 MUST)
Portfolio-wide view (all transitions).
- Filters: portfolio, region, current gate, RAG, project type, search (name, market, OR focal). Filters reflected in URL query.
- KPI tiles: Active transitions · Red · Decisions ≤ 14 days · Transitions with critical gaps · Compliance readiness < 70%. Clicking a tile filters the register.
- **Heatmap** portfolio (rows) × gate (columns): count of transitions per cell, cell colour = worst RAG; click a cell to filter.
- **Readiness by region**: bar chart of average overall readiness.
- **Transition register** table with columns (from the client prototype): Transition · Portfolio · Region / market · Type · Gate · Lenses (three mini bars B/T/C %) · Readiness % · Gaps (critical in red) · Next decision (date + days) · OR focal · RAG. Row click → transition workspace.
- **Escalation queue**: Red transitions and blockers (blocker note, owner, days to decision).
- **Decision calendar**: next 45 days of AtD/AtO/closure decisions.
- **Orion – control tower insights** (agent card): top 3 risks across the portfolio + suggested asks for the leadership meeting.
- "Operating rhythm" info card (static, from prototype): weekly OR stand-up; fortnightly portfolio/regional SME review; IRM checkpoint before each gate; monthly leadership update.

### 8.3 Transitions list (FR-012 MUST)
Simple searchable table of all transitions (same columns as register) with "New transition" button.

### 8.4 New transition – intake (FR-020 MUST)
Two ways to start, both landing on the same form:
- **"Start gate review"** quick action in the Orion panel or the New transition menu.
- **Fetch from ServiceNow (mock):** field "ServiceNow project ID" + Fetch button → `ServiceNowService.get_project(id)` pre-fills name, project type, investment type, delivery method, portfolio, region, market, description, PM. Demo IDs in `seed/mock_external_systems.json` (`PRJ0052210`, `PRJ0049920`). Unknown ID → friendly "Not found in ServiceNow (mock) – enter manually".

Form fields (labels and options must match `reference.json` and the client prototype):
| Field | Type | Required | Options / notes |
|---|---|---|---|
| Solution / transition name | text | ✓ | |
| ServiceNow project ID | text + Fetch | – | mock lookup |
| Project type | select | ✓ | Agentic AI · Normal · Combined · Infrastructure |
| Mobility landscape category (portfolio) | select | ✓ | GCC · eMobility · Global Marketing · Fleets · Telecoms · Retail Site Systems |
| Region | select | ✓ | Global · Europe & South Africa · Asia Pacific · Americas · Central Apps |
| Market / country | text | – | e.g. "Netherlands", "Multi-market" |
| In-scope sites (Site ID + Site key) | repeatable rows | ✓ only when portfolio = Retail Site Systems | at least one row |
| Audience | select | ✓ for AI types | Internal department · Enterprise · External |
| Write actions | select | ✓ for AI types | No · Yes |
| Sensitive data | select | ✓ for AI types | No · Personal sensitive · SOX / MC |
| Target gate | select | – | SG0-SG2 · SG3 · AtD · AtO · Closure |
| Investment type | select | – | Run · Change · Grow |
| Delivery method | select | – | Waterfall · Agile · AI / Agentic |
| Description | textarea | – | |
| OR focal / PM / Architect / OLM / IRM | user pickers | OR focal ✓ | defaults: current OR focal user, U10, U11, U12, U14 |
| Next decision date | date | – | |

On submit:
- If project type is Agentic AI or Combined → go to **Tiering wizard** (8.5).
- Else → go to **Scope** (8.6).
- Right-hand "Auto-scope" panel (live preview while typing): shows the flavour ("Agentic AI · GCC · Global"), which checklists will apply (Framework 72 + AI Playbook (Tier ?) + GCC golden set 5 + common 2), and the portfolio focus areas.

### 8.5 AI tiering wizard (FR-021 MUST, AI flavours only)
- Step 1: the five questions TQ1–TQ5 (yes/no) with helper text; intake answers (audience, write actions, sensitive data) shown read-only.
- Step 2: proposed tier (BR-011) with rationale bullets, tier definition card (definition, examples, builder persona) and the three dimensions. Buttons: **Propose tier N** (OR focal). IRM sees **Confirm tier** / **Change tier** (with reason).
- Step 3: **AI profile questionnaire** (from the playbook SG0–SG2 sheet): infrastructure solution, agentic development framework, multi-agent orchestration (yes/no), number of users, agentic workflows (text), models used, data sources, hosting, write-actions detail.
- Continue → Scope.

### 8.6 Portfolio scope requirements (FR-022 MUST)
"Confirm applicability before launching the assessment."
- Header: portfolio operating set-up (focus areas from `portfolios.json`).
- **Golden set table**: ID · Requirement · Type (Mandatory / Portfolio) · Gate · Owner hint · Lens · Applies? (Yes / No / To confirm). Mandatory rows locked to Yes.
- Summary counts: Framework items, AI Playbook items (applicable vs excluded by tier), golden set, common items, total.
- Orion card (agent): "Recommended applicability" for `To confirm` rows with one-line reasons (mock) → **Accept all recommendations** button (human click).
- Button **Launch readiness assessment** → creates TransitionItems (BR-010) → opens the workspace.

### 8.7 Transition workspace (FR-030 MUST)
URL `/transitions/:id/<tab>`. Header: name, flavour chips (type, portfolio, region/market, Tier N Confirmed/Proposed), current gate stepper (all 7 gates, current highlighted, decision gates marked), overall readiness, RAG chip, next decision date, OR focal, autonomous-mode toggle (OR focal only), **Ask Orion** button.

**Tabs:**

**a) Overview** — lens cards (readiness %, done/in progress/not started/gaps, sign-off status for current gate, lens question and owner), open conditions, pending exceptions, risks, blocker, recent activity, gate history timeline (outcome, who, when, note).

**b) Assessment** (core) — FR-031
- Filters: gate (default = current gate and earlier), lens, source (Framework / AI Playbook / Portfolio / Common), status, owner, "only my items", applicability (show excluded items toggle), search.
- Grouped by gate, then lens. Row: ID · Item (title + expandable description/detail/source sheet & cell) · Source badge · Lens · Owner · Status (inline select, permission-aware) · Severity (if gap) · DE (compliance) · Evidence count (clickable) · Updated by (with Human/Workflow rule badge) · ⋯ menu (add evidence, create action, add condition, request exception (compliance), view audit).
- Bulk actions (OR focal): set owner, mark N/A with reason.
- Gate summary bar on top: per lens readiness for the selected gate; "Readiness check" button.

**c) Gaps & actions** — FR-032
- Gaps list (items in Gap/Non-compliant up to current gate) with severity, lens, owner, days to decision.
- **Orion recommendations** (agent card per gap): proposed action, proposed owner, proposed due date, draft chaser. Buttons: **Create action** (human), **Draft chaser** (→ Orion drafts).
- Actions table: ID, title, linked items, owner, due, status, priority, origin. Create/edit/close.

**d) Evidence** — FR-033
- List with filters (item, type, status). Upload file (stored locally by mock `DocumentStore`, returns a fake SharePoint URL `https://sharepoint.example/sites/orion/<transition>/<file>`) or add link / email sign-off text.
- Review: Accept / Reject with note (OR focal for B/T, IRM for C).
- Generated artefacts (support model PPT, OCET Excel) appear here automatically with type `Generated`.

**e) Gates & decisions** — FR-034
- One panel per gate. Stage-review gates: checklist summary, carried items, outcome buttons (BR-040).
- Decision gates (AtD, AtO): **Readiness check** panel (§8.9), approval chain status with steps, **Request approval** (via Orion draft in assistive mode), decision dialog (Approve / Approve with conditions / Return) enforcing BR-040, conditions editor.
- Closure panel with closure checklist (UD-002 hypercare tracker, UD-003 no open defects, UD-004 no open actions + no open conditions).

**f) Conditions, exceptions & risks** — FR-035
- Conditions table (set at gate, due gate, owner, status, close).
- Exceptions (ref, control item, rationale, status) with **Request exception** → approval chain IRM → CISO/BISO (mock).
- Risk register (ID, title, rating, decision, linked items).
- SHOULD: **Risk acceptance (conditional AtO)** — choose gap category → shows the endorsement route from `reference.json → risk_acceptance_routes` and the follow-on approvals; creates an ApprovalRequest of type RISK_ACCEPTANCE (all steps mock-approvable by the OR focal in demo mode, clearly labelled "mock").

**g) Hypercare** — FR-036
- Defect tracker: ID, title, priority P1–P4, status, owner. "No defects – tracker in place" confirmation checkbox. Feeds AtO rules.

**h) OCET** — link card to the OCET module for this transition (status, current version, 5-year total, approval step).

**i) Support model** — link card to the generator (status, version, last generated PPT).

**j) AI playbook** (only AI flavours) — FR-037
- Tier card (proposed/confirmed, rationale, who confirmed).
- AI profile answers (editable).
- **Eval metrics table**: metric · target for this tier (from EvalTarget) · result (input) · Pass/Fail (auto when `evaluation=auto`, manual toggle otherwise) · last evaluated. Button **Import eval results (mock)** fills results from `sample_transitions.json → eval_results` for the flagship, or generates plausible values for others. Failed metrics appear as Technical gaps at AtD ("Eval metric below target: Hallucination rate 3.1% vs ≤ 2%").
- Note banner: "Targets currently identical for all tiers — tier-specific thresholds to be confirmed by the S&T team (editable in Admin)."

**k) Activity** — audit trail filtered to this transition, with actor type badges (Human / Workflow rule / Orion agent / System).

### 8.8 Support model generator (FR-040 MUST)
Route `/transitions/:id/support-model` and list page `/support-models`.
**Step 1 – Inputs:**
- Confluence / Atlassian solution link (text). On blur, `ConfluenceService.fetch(url)` returns title + summary (mock).
- Upload: architecture walkthrough recording or transcript (`.mp4/.m4a/.vtt/.txt/.docx`), solution design document (`.pdf/.docx`), architecture diagrams (`.png/.jpg/.pdf`). Files are stored by the mock DocumentStore.
- Info note: "Orion doesn't join meetings. Upload the recording or transcript after the walkthrough." (client constraint)
**Step 2 – Generate:** button **Generate support model** → progress UI with three simulated steps (~1.5 s each): "Reading transcript", "Reading diagrams and documents", "Drafting landscape and support flows". Backend: `SupportModelGenerator.generate(transition, inputs)` (mock, §10.6) returns the landscape JSON.
**Step 3 – Review and edit:**
- **Landscape canvas** (React Flow): central app node in the middle, components around it (radial layout), edges with direction; nodes editable (rename, type, delete, add), edges editable.
- Side panels: hosting & vendor, vendor/supplier responsibilities (list), **support tiers** L1/L2/L3 (editable text), contacts & SLA table (party, role, email, SLA), **open questions for the architect** (list, each with "Draft question to architect" → Orion draft), **sources** (each fact links to a source: diagram/page or recording timestamp).
- Status: Draft → **Send for review** (approval chain Architect → OLM) → Agreed.
**Step 4 – Export:** **Generate PPT** → backend builds a `.pptx` with `python-pptx` (§10.6.2), saves it as Evidence (`Generated`, linked to `FW-035`), and offers download. Re-generation creates a new version.

Landscape JSON schema:
```json
{
  "central_app": "Medallia VOC",
  "hosting": "Vendor SaaS on vendor AWS (not Shell AWS)",
  "vendor": "Medallia", "supplier": "KPMG",
  "vendor_responsibilities": ["Hosting", "Development", "Configuration", "Technical access"],
  "components": [{"id": "c1", "name": "GCC Integration", "type": "Integration", "relation": "bidirectional", "target": null}],
  "support_tiers": {"L1": "...", "L2": "...", "L3": "..."},
  "contacts": [{"party": "KPMG", "role": "Supplier support", "email": "...", "sla": "..."}],
  "open_questions": ["..."],
  "sources": [{"type": "diagram|recording|document", "ref": "..."}]
}
```

### 8.9 Readiness check (FR-050 MUST) — the client's core ask
Available on the decision-gate panel, the Overview tab, the Orion panel ("Assess gate readiness"), and via API.
Output card:
- **Verdict** (rules): `Ready for <gate>` / `Ready with conditions` / `Not ready` — computed from BR-040 rules.
- **Why** (rules): blocking items grouped by lens, critical gaps, open conditions due, pending exceptions, failed eval metrics (AI), OCET status, support model status, approval chain status.
- **Orion assessment** (agent, mock text): 3–5 sentence narrative ("Mobility Knowledge Agent is not ready for AtD. Three blockers: red-team evidence (S45-014) is non-compliant with exception EX-01 pending; OCET v2 still has a missing monitoring-cost input; the support model has not been drafted; two eval metrics are below the Tier 2 targets…").
- **Recommended next actions** (agent proposals), each with a button: Draft chaser · Create action · Request inputs · Open OCET · Create support model · Request exception · Request approval (only when verdict is Ready/Ready with conditions).

### 8.10 OCET module (FR-060 MUST)
Route `/transitions/:id/ocet`.
- Header: currency, start year, horizon, current version + status, approval chain progress (Planner → OLM), 5-year total, variance vs previous version.
- **Lines grid** (editable while Draft): category · description · vendor · pricing basis · base amount (start year) · growth %/yr · year overrides (popover per year with reason) · input owner · input status · computed yearly amounts (read-only columns) · line total.
- **Summary**: category × year table + stacked bar chart by category per year + line chart of total.
- **Worked example** tooltip on growth: "100k at +10% compounding → 110k, 121k, 133.1k, 146.4k".
- Buttons: **Request inputs** (select lines with missing/requested inputs → Orion drafts emails to the input owners with a deep link), **Submit for approval** (creates chain Planner → OLM; blocked if any line has missing base amount), **Create new version**, **Export to Excel** (SHOULD; openpyxl, saved as Evidence), **Compare versions** (diff table).
- **Orion card** (agent): explains the version change in plain words ("Total up 8.4% vs v1, mainly AI tokens: 2028 growth overridden to +30% because two more markets onboard").
- Note: "R&M costs are picked up by SOM per the ATO+12 principle" (info text).

### 8.11 Approvals inbox (FR-070 MUST)
- Tabs: Waiting for me · Requested by me · All (OR focal/ADMIN).
- Card per request: type, transition, subject summary (e.g. OCET v2 total, AtD readiness verdict), step chain with status, due/age, buttons Approve / Reject (comment). Deep link to subject.
- Approving sends notifications to the next step (in-app + mock email + mock Teams card).

### 8.12 Orion drafts queue (FR-071 MUST)
- List of OrionDraft records: kind, transition, recipients, subject, source (Workflow rule R1…R7 / Orion agent), created.
- Open → editable subject/body (rich text or markdown), recipients editable → **Send** (MailService mock + NotificationService for Teams variant), **Discard**.
- Button **Run reminder engine now** + last run time + counts per rule.
- Assistive/autonomous explanation banner.

### 8.13 Outbox (FR-072 MUST)
Shows every message "sent" through the mock MailService / NotificationService: channel (Email / Teams), from (`ORION_MAILBOX`), to/cc, subject, time, rendered body; for Teams messages, render the Adaptive Card preview (simple custom renderer is fine) and show the raw JSON in a collapsible panel. Banner: "Mock mode – in production this calls Microsoft Graph `POST /users/{orion-mailbox}/sendMail` and the Orion Teams bot."

### 8.14 Leadership updates (FR-080 MUST)
- Generate for: one transition, one portfolio, or all. Output (agent, mock template filled with live data): headline, status by portfolio/gate, top risks/blockers, decisions due (next 30 days), asks for leadership, wins.
- Actions: copy, **Send via email (mock)**, save to history list.

### 8.15 Orion assistant panel (FR-090 MUST)
Right-side panel (≈420 px) available on every page; full-page route `/orion` too.
- Header "Orion – Operate Readiness Agent", context chip (current transition if on a transition page).
- **Quick actions** (the six starters from the client's own Orion mock-up + one more): `Start Gate Review` · `Assess Gate Readiness` · `Track Owner Actions` · `Draft Owner Reminders` · `Create Leadership Update` · `Create Support Model` · `Create / Update OCET`.
- **Form-first** (client concern about token cost): quick actions that need inputs open a small **form card** (e.g. transition picker + gate) rather than asking questions one by one in chat; free-text chat is still available.
- Response types (render as cards): text, readiness card (§8.9), table (owner actions), drafts list (with "Review in drafts queue"), link button (navigate), proposal card (button that calls a normal user endpoint after the user clicks — BR-050).
- Behaviour by intent (mock, deterministic; §10.1):
  - Start Gate Review → navigates to `/transitions/new` (or opens the intake form card).
  - Assess Gate Readiness → transition picker → readiness card.
  - Track Owner Actions → table of open actions/items by owner for the chosen transition, overdue first.
  - Draft Owner Reminders → runs R1/R2 for the transition → shows drafts → link to queue.
  - Create Leadership Update → generates and shows the update.
  - Create Support Model → navigates to the generator for the chosen transition.
  - Free text: keyword intents — "status of <transition>", "what is blocking AtD/AtO for <transition>", "who owns <item id>", "what is OCET / AtD / AtO" (glossary answers), "show red transitions". Unknown → helpful fallback listing quick actions.
- Footer: "Orion recommends and drafts. People decide." Every agent message shows the "AI" badge.

### 8.16 Admin – playbook and configuration (FR-100 MUST, ADMIN only)
- **Playbook library**: browse/search all items (Framework, AI Playbook, Portfolio, Common); edit title, description, gate, lens, applicable tiers, mandatory, active. Badge "lens suggested – confirm" where `lens_is_suggested`.
- **Flavour rules**: project type → checklists (checkboxes), requires tiering.
- **Portfolio golden sets**: edit items per portfolio; add/remove; mandatory flag.
- **Eval metric targets by tier**: grid metric × Tier 1–4 (text + parsed operator/value/unit); "targets confirmed" flag.
- **Approval chains**: steps per type (role per step).
- **Reminder rules**: thresholds (14 days, 2/5 days, 3 days), enable/disable each rule.
- **Users** (read-only list of demo users and roles).
- **Demo controls** (only `DEMO_MODE=true`): Reset demo data (re-seed) · **Fast-forward flagship** (marks every remaining open item due ≤ the current gate as done/compliant **except** items linked to the OCET or support-model workflows and items under an exception, and re-imports eval results with all metrics passing — so the demo only has to resolve the scripted blockers) · Set "today" (SEED_DATE) · Run reminder engine.
- Changes to playbooks affect **new** transitions; existing transitions keep their items (show a notice).

### 8.17 Audit trail (FR-110 MUST)
Global table with filters (transition, actor, actor type, entity, date range); before/after diff view.

### 8.18 Teams preview (FR-120 SHOULD)
Route `/teams-preview` titled "Preview – Orion in Microsoft Teams (Phase 2)". Mimic a Teams chat window (narrow, Teams-like chrome — do not use Microsoft logos):
- Orion bot welcome message with the quick-action buttons.
- Example **Adaptive Card**: "AtD approval request – Mobility Knowledge Agent" with readiness summary and **Approve / Reject** buttons that call the real approvals API (so approving here updates the web app).
- Example reminder digest card and an OCET approval card.
- A "Open in Orion" button on each card (deep link to the web app — this is how the tab will work in Teams).

### 8.19 Support Model Retriever (FR-130 SHOULD)
`/support-models` page: search across generated support models + 3 seeded historical ones (mock) by app name and question (e.g. "Capillary P1 contacts"); answer shows matching section, contacts and diagram link (mock), with source reference. Clearly marked "Later phase – preview".

---

## 9. REST API (MUST) — prefix `/api/v1`, JSON, OpenAPI docs at `/docs`

All endpoints require `X-Demo-User`. Return `403` on permission failures, `409` on rule violations (with a `reasons[]` list the UI shows), `422` on validation errors.

**Reference & users**
- `GET /reference` (gates, lenses, statuses, options, tiers, questions, rag rule, roles, ocet config)
- `GET /users`, `GET /me`

**Transitions**
- `GET /transitions?portfolio&region&gate&rag&type&q` → list with computed readiness, gaps, critical, RAG, next decision
- `POST /transitions` (intake) · `GET /transitions/{id}` · `PATCH /transitions/{id}`
- `POST /transitions/{id}/autonomous-mode` `{enabled}`
- `GET /control-tower?filters` → KPIs, heatmap, region bars, register, escalations, calendar
- `GET /dashboard` (role-aware)

**Tiering & AI profile**
- `POST /tiering/propose` `{intake fields, answers}` → `{proposed_tier, rationale[]}` (pure rule; also used by the wizard live)
- `PUT /transitions/{id}/tier` `{answers, proposed_tier}` (OR focal) · `POST /transitions/{id}/tier/confirm` `{tier, reason?}` (IRM)
- `GET/PUT /transitions/{id}/ai-profile`

**Scope & items**
- `GET /transitions/{id}/scope` (golden set + counts) · `PUT /transitions/{id}/scope` (applicability decisions)
- `POST /transitions/{id}/launch-assessment` (creates items, BR-010)
- `GET /transitions/{id}/items?gate&lens&source&status&owner&applicability&q`
- `PATCH /items/{itemId}` `{status, gap_severity, note, owner_user_id, design_effectiveness, applicability, na_reason}` (BR-030)
- `POST /items/bulk` (owner / N/A)

**Evidence, actions, conditions, exceptions, risks, defects**
- `GET/POST /transitions/{id}/evidence` (multipart upload or link) · `POST /evidence/{eid}/review` `{decision, note}` · `GET /evidence/{eid}/download`
- `GET/POST /transitions/{id}/actions` · `PATCH /actions/{aid}`
- `GET/POST /transitions/{id}/conditions` · `PATCH /conditions/{cid}`
- `GET/POST /transitions/{id}/exceptions` (POST creates approval chain)
- `GET/POST /transitions/{id}/risks`
- `GET/POST /transitions/{id}/defects` · `PATCH /defects/{did}` · `POST /transitions/{id}/defects/confirm-none`

**Gates & approvals**
- `GET /transitions/{id}/readiness?gate=` → readiness check (rules verdict + reasons + Orion narrative + proposals) (§8.9)
- `POST /transitions/{id}/gates/{gate}/review` `{outcome, note, conditions[]}` (stage reviews, BR-040)
- `POST /transitions/{id}/gates/{gate}/request-approval` → creates ApprovalRequest (from an accepted Orion draft or directly)
- `POST /transitions/{id}/gates/{gate}/decision` `{decision, note, conditions[]}`
- `GET /approvals?scope=mine|requested|all` · `POST /approvals/{rid}/steps/{step}/approve|reject` `{comment}`

**OCET**
- `GET /transitions/{id}/ocet` (estimate + current version + lines + computed projection + variance)
- `PUT /ocet/versions/{vid}/lines` (bulk save while Draft) · `POST /ocet/versions/{vid}/submit` · `POST /transitions/{id}/ocet/new-version`
- `POST /ocet/versions/{vid}/request-inputs` `{line_ids[]}` → Orion drafts
- `GET /ocet/versions/{vid}/export.xlsx` (SHOULD) · `GET /ocet/compare?from&to`

**Support model**
- `GET /transitions/{id}/support-model` · `POST /transitions/{id}/support-model/inputs` (multipart + confluence_url)
- `POST /transitions/{id}/support-model/generate` → landscape JSON (+ job progress simulated client-side or via polling `GET /jobs/{jid}`)
- `PUT /support-models/{smid}` (edited landscape) · `POST /support-models/{smid}/send-for-review` · `POST /support-models/{smid}/pptx` → file + evidence
- `GET /support-models?q=` (list + retriever SHOULD)

**Orion agent**
- `POST /orion/chat` `{message?, quick_action?, form_data?, context:{transition_id?, page?}}` → `{messages:[{type:text|readiness|table|drafts|link|proposal|form, ...}]}`
- `GET /orion/insights?scope=dashboard|control-tower|transition&id=`
- `POST /orion/proposals/{pid}/accept` → executes the underlying user endpoint **as the current user** (BR-050)
- `POST /orion/leadership-update` `{scope, scope_id?}` · `GET /leadership-updates`

**Drafts, outbox, notifications**
- `GET /orion/drafts` · `PATCH /orion/drafts/{did}` · `POST /orion/drafts/{did}/send` · `POST /orion/drafts/{did}/discard`
- `POST /reminders/run` → `{created: {R1: n, …}, sent_autonomously: n}`
- `GET /outbox` · `GET /notifications` · `POST /notifications/{nid}/read`

**Integrations (mock)**
- `GET /integrations/servicenow/projects/{projectId}` · `POST /integrations/confluence/fetch` `{url}`

**Admin**
- `GET/PUT /admin/playbook-items[/{id}]` · `GET/PUT /admin/flavour-rules` · `GET/PUT /admin/portfolios/{name}/golden-set`
- `GET/PUT /admin/eval-targets` · `GET/PUT /admin/approval-chains` · `GET/PUT /admin/reminder-rules`
- `POST /admin/demo/reset` · `POST /admin/demo/fast-forward` `{transition_id}` · `POST /admin/demo/today` `{date}`

**Audit**
- `GET /audit?transition_id&actor&actor_type&entity&from&to`

---

## 10. Mock services (MUST) — `backend/app/services/`

Define each as a Python `Protocol` in `interfaces.py`, implement in `mock/`, add a `live/` stub whose docstring states the real call. `factory.py` selects via config. Mocks must be **deterministic** (same input → same output) and add a small artificial delay (300–1500 ms) where it helps the demo feel real. Every mock call writes a log line `[MOCK <Service>] <operation> <key params>`.

### 10.1 AIService (Orion agent)
Methods: `readiness_narrative(ctx)`, `recommend_actions(gaps)`, `recommend_applicability(items, flavour)`, `draft_message(kind, ctx)`, `leadership_update(scope_data)`, `explain_ocet_change(diff)`, `chat(message, context)`, `insights(scope_data)`.
- **Mock implementation:** template-based text filled with real data (names, item IDs, counts, dates). No randomness. Examples:
  - readiness narrative: "{name} is {verdict_lower} for {gate_short}. {n_block} item(s) block approval: {top3}. {conditions_sentence} Recommended next step: {first_action}."
  - chaser: subject "Action needed: {item_title} for {transition} ({gate_short} in {days} days)"; polite body with item list, due gate, deep link, sign-off "Orion, on behalf of {or_focal_name}".
- Intent router for `chat`: keyword rules as in §8.15.
- **Live stub (optional, SHOULD):** if `AI_MODE=live` and Azure OpenAI env vars exist, use it **only** for free-text chat and narratives, with a system prompt that includes the computed facts; on any error fall back to mock. All decisions and numbers still come from rules.

### 10.2 MailService (Microsoft Graph mock)
`send_mail(from_mailbox, to[], cc[], subject, html_body, related_ids)` → writes OutboxMessage (channel Email) + log `would POST https://graph.microsoft.com/v1.0/users/{from}/sendMail`. Live stub documents: application permission `Mail.Send` restricted to the Orion shared mailbox via Exchange RBAC for Applications.

### 10.3 NotificationService (in-app + Teams mock)
`notify(user_ids, text, link)` → Notification rows. `post_teams_card(user_ids, card_json, summary)` → OutboxMessage (channel Teams) with Adaptive Card JSON. Live stub documents: Teams bot proactive message via Azure Bot Service (Phase 2).

### 10.4 Adaptive Card templates (MUST, JSON files in `backend/app/services/cards/`)
- `approval_request.json` — title, transition, gate/subject, readiness summary (3 facts), Approve / Reject (`Action.Execute` with `verb: approve|reject`, data `{request_id, step}`), "Open in Orion" (`Action.OpenUrl`).
- `reminder_digest.json` — owner name, list of up to 5 items (title, due gate), "Open my items".
- `ocet_approval.json` — version, 5-year total, top 3 categories, variance, Approve / Reject.
The Teams preview page (8.18) renders these and wires the buttons to the approvals API.

### 10.5 ServiceNowService, ConfluenceService, DocumentStore (SharePoint), TranscriptService
- ServiceNow: `get_project(id)` from `mock_external_systems.json`.
- Confluence: `fetch(url)` → first page whose `url_contains` matches (case-insensitive), else the generic page.
- DocumentStore: `save(transition_id, file)` → saves under `backend/app/storage/<transition>/`, returns `{url: https://sharepoint.example/sites/orion/<transition>/<filename>, path}`.
- Transcript: `get_text(file)` → for `.vtt/.txt/.docx` return text (read the file); for audio/video return a canned transcript snippet (mock) and log "would transcribe with Azure AI Speech".

### 10.6 SupportModelGenerator
#### 10.6.1 Generation (mock)
- If transition name or Confluence URL matches a sample in `seed/support_model_samples.json` (`voc`), return that landscape (the Medallia VOC example from the client's own experiment: Medallia at the centre, GCC Integration, App Teams, Shell Asia Integration with escalation to L1 Support, MDH Data Flow → MDH, SFTP Ownership, Middleware (Logic Apps) → SSO → SPN / Groups; Medallia + KPMG handle hosting, development, configuration, technical access; hosted on Medallia's own SaaS on their AWS, not Shell AWS).
- Otherwise build a **generic landscape** from the transition: central app = transition name; 6–8 components from the portfolio focus areas + typical integrations (Entra ID SSO, ServiceNow, monitoring tool, data platform, middleware); support tiers "L1 Service Desk / L2 vendor or AMS / L3 product team"; 3 open questions; sources referencing the uploaded files by name.
- Live stub documents the intended pipeline: transcript text + diagram images → Azure OpenAI multimodal (Azure AI Foundry) → structured JSON (same schema) → human review.

#### 10.6.2 PPT export (real, not mocked)
Use `python-pptx`, 16:9:
1. **Title slide**: "Support model – {central_app}", transition, portfolio, version, date, "Draft – generated by Orion, reviewed by {user}".
2. **Landscape slide**: central app as a large circle in the centre; components as rounded rectangles placed radially; connectors with arrowheads following `relation`; right-hand text box "{vendor} + {supplier}: • Hosting • Development • …" and "{vendor} is: • {hosting}". (Mirrors the client's VOC slide.)
3. **Support flow slide**: L1 → L2 → L3 boxes with owners + escalation note.
4. **Contacts & SLA slide**: table.
5. **Open questions & sources slide**.
Use a neutral template (dark-teal header bar, white background); put a constant `TEMPLATE_NAME = "PTIV ORB (placeholder)"` and a single function for colours/fonts so the client's real template can be swapped in later. Footer "Confidential".

---

## 11. Seed data (MUST)

### 11.1 Files (in `/seed`, provided — do not edit by hand; copy into the backend at build)
| File | Content |
|---|---|
| `reference.json` | gates, gate outcomes, lenses, statuses, project types + flavour rules, portfolios, regions, intake options, tiers, tier dimensions, tier questions, RAG rule, approval chains, risk-acceptance routes, OCET config, roles |
| `framework_activities.json` | 72 Operate Readiness Framework activities (`FW-001…FW-072`) with phase window, mapped gate, category, description, action owner, SOM sign-off, comments, automation tag, **suggested** lens |
| `ai_playbook_items.json` | 216 assessable AI Playbook items (v3.0 + 4 OR-focal additions `UD-001…UD-004`) with gate, lens, kind, applicable tiers (recovered from the workbook's Tier column where present), source sheet/cell |
| `portfolios.json` | 6 portfolios: focus areas, golden-set deliverables (mandatory flags), common items `ALL-01/02`, Retail extra intake fields (sites) |
| `eval_metrics.json` | 38 eval/KPI metrics with targets and machine-checkable operator/value/unit where parseable; per-tier targets (identical for now) |
| `sample_transitions.json` | 18 transitions (from the client prototype) with snapshot metrics; the **flagship** `TR-0001 Mobility Knowledge Agent` has full scripted detail |
| `ocet_sample.json` | Flagship OCET: 6 lines, v1 superseded, v2 "Inputs pending" (monitoring tool cost requested from the Architect) |
| `support_model_samples.json` | VOC landscape sample + rules for generic generation |
| `mock_external_systems.json` | ServiceNow projects and Confluence pages for mocks |
| `demo_users.json` | 16 fictional demo users across all roles |

### 11.2 Loader (MUST)
`seed/loader.py` runs on startup if the DB is empty and on `POST /admin/demo/reset`. Steps: reference → users → playbook items (all sources) → portfolios → eval targets → transitions (tier assessments for AI ones) → items via BR-010 → synthesised statuses (§11.3) → flagship overrides → conditions, exceptions, risks, gate history, actions, evidence, eval results → OCET → audit events "Seeded".
`today` = `SEED_DATE` or the real date. `next_decision_date = today + snapshot.days_to_next_decision`.

### 11.3 Deterministic status synthesis (MUST)
For each transition (including the flagship before overrides):
1. Scope per lens = applicable items with `o(due_gate) ≤ o(current_gate)`, sorted by (gate order, id).
2. `k_L = round(snapshot.readiness_pct[L] / 100 × |scope_L|)`; first `k_L` items → done status (`Complete`; Compliance → `Compliant`, DE = `Yes`).
3. Remaining items: distribute `snapshot.open_gaps` across lenses proportionally to remaining counts; the last items of each lens become `Gap` / `Non-compliant` (severity `Major`); the first `snapshot.critical_gaps` gap items overall (lowest gate first) get severity `Critical`; the rest become `In progress` (Compliance → `In review`).
4. Items due after the current gate → `Not started`.
5. `snapshot.blocker` (if any) → create a Risk (rating High) and attach it to the first critical gap item's note.
6. **Flagship:** then apply `item_overrides` exactly (status, note, design effectiveness, linked module) and create its conditions, exceptions, risks, gate history (as GateReview records), actions (`due_in_days` from today), evidence (with fake SharePoint URLs), eval results.
7. Assign owners per BR-010 step 6; the OR focal from `or_focal_user_id`.
Write a unit test asserting that computed readiness for each seeded transition is within ±3 points of its snapshot.

### 11.4 Data notes the UI must surface (honesty for the client)
- Framework lens mapping is **suggested** (badge "lens suggested") — the source workbook has no lens column.
- 192 AI Playbook items have no tier in the workbook → apply to all tiers, marker "tier to confirm".
- Eval-metric targets are identical across tiers until the S&T team provides tier-specific thresholds.
- Golden sets are "approximate (client prototype)".

---

## 12. UX and visual guidance (MUST)

- Clean enterprise look using **Fluent UI v9** defaults (light theme), not the prototype's design. Density: comfortable tables, sticky headers, column filters.
- Consistent semantic colours: lenses (Business amber, Technical blue, Compliance teal); RAG (red, amber, green, grey = not started); actor badges (Human = neutral, Workflow rule = blue outline, Orion agent = purple with "AI").
- Every list has: loading skeletons, empty states with a helpful next step, error toasts with the API `reasons[]`.
- Disabled buttons always explain why (tooltip from rule reasons, e.g. "Approve disabled: 2 compliance items not compliant (S45-014, S45-026)").
- Deep links and browser back work everywhere. URL holds filters.
- Desktop first (1280–1920 px), usable at 1024 px. Works inside an iframe.
- Text: plain English, short labels, consistent terms (AtD, AtO, OCET, OR focal, lens, gate). Show full names on hover for abbreviations.
- Accessibility: keyboard navigation, focus states, aria labels on icon buttons, colour never the only signal (RAG chips carry text).

---

## 13. Demo storyline (MUST — the build must support this end to end; write it as `docs/DEMO_SCRIPT.md` with exact clicks)

1. **Login** as Asha Menon (OR focal). Dashboard shows her work, decisions due and Orion insights.
2. **Control tower**: heatmap and register; filter Retail Site Systems → "Forecourt POS refresh" is Red (3 critical gaps, decision in 4 days); open escalation queue.
3. **Start a new transition** via Orion → "Start Gate Review": fetch ServiceNow `PRJ0052210` (SMSM Photo Capture) → Agentic AI, Retail Site Systems → add two sites (Site ID + key) → answer tier questions (internal, no writes) → proposed **Tier 2** with rationale → switch user to **Fatima (IRM)** → confirm tier → back to Asha → Scope: golden set (Retail mandatory site item locked), accept Orion's applicability recommendations → Launch assessment → item counts shown (Framework 72, AI Playbook n applicable / m excluded for Tier 2, golden set, common).
4. Open the **flagship** "Mobility Knowledge Agent" (Agentic AI, GCC, Tier 2, current gate AtD). Assessment tab filtered to AtD; show lens readiness, items with evidence, workflow vs human badges.
5. **Assess gate readiness** (Orion panel) → verdict **Not ready for AtD**: S45-014 red-team non-compliant (exception EX-01 pending), FW-008 OCET not approved (input pending), FW-035 support model gap, condition CON-001 open, AI eval metrics below target (hallucination 3.1% vs ≤ 2%, prompt-injection resistance 84% vs ≥ 90% — after **Import eval results (mock)** on the AI playbook tab); Orion recommends actions → click **Draft chaser** for S45-014 → Orion drafts queue → edit → **Send** → Outbox shows the email and the Teams card.
6. **OCET**: open v2 → lines and 5-year chart (cloud 100k → 146.4k) → monitoring line missing → **Request inputs** → draft → send. Switch to **Mei (Architect)** → enter 10,000 → switch to Asha → Submit → switch to **Tom (Planner)** → Approve in Approvals inbox → switch to **Sofia (OLM)** → Approve → OCET **Approved**, FW-008 and S45-006 become Complete (badge "Workflow rule").
7. **Support model**: Asha → Create support model → paste Confluence link containing "voc" (or use the flagship generic) + upload a transcript `.txt` and a diagram → Generate → edit landscape (rename a node, answer an open question) → Send for review → Mei approves → Sofia agrees → **Generate PPT** → download (opens in PowerPoint) → evidence auto-linked to FW-035 → support model items Complete.
8. **Exception**: Fatima (IRM) approves EX-01 and, in demo mode, "Approve as CISO/BISO (mock)" → S45-014 covered by approved exception. Close CON-001 (stress test evidence uploaded).
9. **Demo controls → Fast-forward flagship** (clearly a demo shortcut: completes the many routine items and re-imports passing eval results) → Readiness check: **Ready for AtD** → Orion (rule R4) drafts "Ready for AtD – request OLM approval" → Asha sends → **Teams preview**: Sofia approves the AtD card there → Fatima approves the IRM step in the web Approvals inbox → Asha records **Approve** → gate moves to Hypercare.
10. **Leadership update** for GCC → shows the AtD approval and remaining risks → send (mock).
11. **Audit trail**: filter the flagship → show Human vs Workflow rule vs Orion agent entries — "Orion drafted, people decided".

---

## 14. Non-functional requirements

- **NFR-01** All external calls behind interfaces with mock defaults; switching to live must not change routers or UI.
- **NFR-02** Rules in `rules/` are pure functions with unit tests: checklist assembly, tiering, readiness, RAG, gate decision validation, OCET maths (incl. the 100k/10% example), reminder triggers, status synthesis (±3 pts).
- **NFR-03** Every write creates an AuditEvent with actor type.
- **NFR-04** Orion cannot write statuses/decisions (BR-050) — enforced in the service layer and covered by a test.
- **NFR-05** API p95 < 300 ms on the seeded dataset (excluding simulated mock delays).
- **NFR-06** Idempotent seeding and reset; demo can be reset in < 10 s.
- **NFR-07** No secrets in code; `.env.example` provided.
- **NFR-08** Lint/format: ruff + black (backend), eslint + prettier (frontend); TypeScript `strict`.
- **NFR-09** README explains architecture (one diagram in Mermaid), how mocks map to the real services (Graph, Teams bot, ServiceNow, Confluence, SharePoint, Azure OpenAI/Foundry), and how to run the demo.
- **NFR-10** Security placeholders documented: Entra ID SSO + RBAC, Key Vault, data classification (OCET and architecture data = Confidential), Orion targeted as a **Tier 2** agent under the client's AI Playbook.

---

## 15. Acceptance criteria (Definition of Done for the demo)

- **AC-01** Both apps start with the documented commands; DB seeds automatically; 18 transitions visible.
- **AC-02** Control tower KPIs, heatmap, register, escalations and calendar render and filter correctly; RAG matches BR-021.
- **AC-03** Creating a transition for each project type assembles the correct item sets; an Agentic AI Tier 2 transition excludes Tier 3/4-only items and shows them as "not applicable (tier)".
- **AC-04** Tiering wizard returns Tier 2 for (internal, no writes, non-sensitive, TQ4 yes) and Tier 4 when TQ2 is yes; only IRM can confirm.
- **AC-05** Retail Site Systems intake requires at least one Site ID + Site key.
- **AC-06** Status changes respect permissions and BR-030; N/A requires a reason; Gap requires severity.
- **AC-07** Readiness check for the flagship returns "Not ready for AtD" with the scripted blockers, and "Ready for AtD" after the scripted fixes + fast-forward.
- **AC-08** Approve/Approve with conditions/Return enforce BR-040; disabled states explain why.
- **AC-09** OCET maths matches the worked example; Planner → OLM chain works across user switches; approval completes linked items.
- **AC-10** Support model: VOC sample and a generic landscape both generate; landscape is editable; PPT downloads and opens in PowerPoint with the 5 slides.
- **AC-11** Reminder engine creates drafts per rule with de-duplication; Send writes to Outbox (email + Teams card JSON); autonomous mode sends R1/R2/R3/R5 directly.
- **AC-12** Orion panel quick actions all work; every agent output carries the AI badge; Orion proposals execute only after a human click.
- **AC-13** Audit trail shows actor types for every change in the demo storyline.
- **AC-14** `docs/DEMO_SCRIPT.md` exists and was followed end to end against the running build.
- **AC-15** All unit tests pass.

---

## 16. Build order for Claude Code (write into `PLAN.md`, tick off as you go)

1. **M1 Foundation** — repo scaffold, config, DB models, seed loader + synthesis, `/reference`, `/users`, demo login + user switcher, app shell/navigation. Tests for rules skeleton.
2. **M2 Visibility** — transitions list, control tower, dashboard (readiness/RAG rules + tests).
3. **M3 Intake** — intake form (ServiceNow mock, Retail sites), tiering wizard (rule + tests), AI profile, scope page, checklist assembly (tests), launch assessment.
4. **M4 Workspace** — overview, assessment grid, evidence (DocumentStore mock), gaps & actions, conditions/exceptions/risks, hypercare, activity, audit trail.
5. **M5 Gates & approvals** — stage reviews, readiness check, approval chains, approvals inbox, decision dialogs (BR-040 + tests).
6. **M6 OCET** — lines grid, projection maths (tests), versions, request inputs, approval chain, linked-item completion, Excel export (SHOULD).
7. **M7 Support model** — inputs, Confluence/transcript mocks, generator mock, React Flow editor, review chain, PPT export.
8. **M8 Orion** — AI mock service, chat intents, quick actions + form cards, readiness narrative, proposals, insights, drafts queue, reminder engine (tests), outbox, notifications, leadership updates.
9. **M9 Admin & demo** — admin screens, demo controls (reset, fast-forward, today), Teams preview (SHOULD), retriever (SHOULD).
10. **M10 Polish** — empty/loading/error states, tooltips with reasons, README + Mermaid diagram, `DEMO_SCRIPT.md`, run the full storyline, fix issues.

After each milestone: run backend tests and the frontend type-check/build, then update `PLAN.md`.

---

## 17. Assumptions and open questions (show these in README → "Open points for the client")

Assumptions built into the demo (configurable):
1. The 72 Framework activities apply to every transition; the AI Playbook adds tier-filtered items for Agentic AI and Combined.
2. Framework items' lens (Business/Technical/Compliance) is a suggested mapping by category.
3. Gate model: SG0 → SG1–SG2 → SG3 → AtD (SG4) → Hypercare (SG4–SG5) → AtO (SG6) → Closure.
4. OCET approval: Planner → Lead SOM OLM. AtD approval: OLM → IRM. AtO: IRM → OLM.
5. Evidence lives in SharePoint (mocked); Orion stores links.
6. Eval-metric targets identical across tiers until confirmed.
7. Orion itself is designed as a Tier 2 agent (internal, bounded, advisory, no writes to systems of record).

Open questions for the S&T team:
1. First module for the real build: AI transition flavour or a business portfolio (e.g. GCC)?
2. Confirm lens per Framework activity and final golden sets per portfolio.
3. Tier-specific eval thresholds.
4. Who signs AtD/AtO exactly (SOM / OR focal / IRM); is ERS the same as IRM?
5. OCET: default growth rules, currency, horizon (5 vs 6 years), must the Excel template be kept?
6. Support model PPT template ("PTIV ORB" format) — please share the master.
7. Access for the real build: ServiceNow API, Confluence, SharePoint site, Orion shared mailbox (Graph), Azure OpenAI / Foundry, Teams app approval.

---

## 18. Field cross-reference to the client HTML prototype

Use the HTML only to verify these labels/options; everything else in it (layout, styles, scripts, AI Ops pages, hard-coded N/A list, gate list) is superseded by this document.

| Prototype element | Where it lives now |
|---|---|
| Intake: Solution, Project type (Agentic AI/Normal/Combined), Mobility landscape category, Region, Market/country, Site ID*, Site key*, Audience, Write actions, Sensitive data, Target gate, Description | §8.4 + `reference.json → intake_options`, `portfolios.json` |
| "Proposed Tier 2: internal, bounded and advisory. Human confirmation required." | §8.5 tiering wizard (now computed, not hard-coded) |
| Scope requirements register (ID, Requirement, Type, Gate, Owner, Applies?) | §8.6 |
| Lenses with questions and owners | `reference.json → lenses` |
| Item statuses (Complete/In progress/Not started/Gap/N/A; Compliant…; DE –/Yes/No/N/A) | `reference.json → item_statuses`, BR-030 |
| AtD / AtO decision options (Approve / Approve with conditions / Return) | BR-040 |
| Control tower filters, heatmap, register columns, escalation queue, decision calendar, operating rhythm | §8.2 |
| Risks CR-01…04, exception EX-01, conditions S3-019 / S02-012, gate log | `sample_transitions.json` (flagship) |
| Portfolio deliverables (PF) + ALL-01/02 | `portfolios.json` |
| Transition dummy data (RAW, 18 rows) | `sample_transitions.json` |
| Playbook traceability register (REG) | `ai_playbook_items.json` (canonical items) |
