# Orion demo script – M5 build (milestones M1–M5)

Audience: client demo. Duration: 20–25 minutes. Built so far: foundation, visibility (dashboard, control tower, transitions), intake (new transition, tiering, scope, launch), workspace (assessment, gaps, evidence, conditions, gates, hypercare, activity, audit trail), gates and approvals (readiness check, approval chains, approvals inbox, outbox, Orion drafts).
Not built yet (say "coming next"): OCET module, support model generator and PPT, Orion side panel/chat/quick actions/reminders/leadership update, admin and demo controls (fast-forward).

## 1. Setup (before the audience arrives)

- App URL: http://127.0.0.1:5174 (port 5173 belongs to another app on this machine).
- Reset to a clean seed: stop the API, delete `backend/orion.db`, restart the API (it reseeds: 18 transitions). Reload the browser.
- Open the URL. The login page says "Demo login – pick a user, no password". Pick **Asha Menon** (OR focal A).
- Users you will switch to (top-right user menu -> **Switch user**): **Fatima Khan** (IRM). Others on standby: Mei Lin (Architect), Sofia Garcia (OLM), Tom Becker (Planner), Daniel Brooks (PM), Laura Evans (Leadership), Playbook Admin.
- Left navigation: Dashboard, Control tower, Transitions, New transition, Approvals, Orion drafts, Outbox, Leadership updates (placeholder), Support models (placeholder), Admin (admin only, placeholder), Audit trail.
- Do the storyline once in rehearsal only if you can reset afterwards; the demo changes data (new transition TR-00xx, sent drafts, closed condition).

Key messages to weave in (say them early, repeat at the end):
1. One place for every transition: checklists, gaps, evidence, gates, approvals, history.
2. Two kinds of automation: a workflow rule does deterministic things (e.g. RAG, readiness, completing linked items); an Orion agent drafts and recommends. Every row is badged so you can tell them apart.
3. Orion drafts, people decide (BR-050): Orion never changes a status or records a decision. It writes drafts; a human edits and clicks Send/Approve.
4. Audit trail: every change records who or what did it – Human, Workflow rule, Orion agent, System.

## 2. Demo flow

### Step 1 – Login and Dashboard (2 min)
1. Log in as **Asha Menon** (click her name on the login page). You land on the Dashboard: "Welcome back, Asha".
2. Point to the KPI tiles at the top, then the **My work** card (her items and decisions due), **Orion insights**, **Portfolio summary** and **Recent activity**.
3. Say: "Asha is an operate-readiness focal. This is her day: what is mine, what is due, what Orion noticed. Everything here comes from the same data as the control tower."

### Step 2 – Control tower (3 min)
1. Click **Control tower** in the left navigation.
2. Show the KPI tiles, the **Heatmap: portfolio by gate** (portfolio rows, gate columns, colour = RAG) and **Readiness by region**.
3. Filter to Retail Site Systems: click the Retail Site Systems row/cell in the heatmap (or use the portfolio filter in the Filters bar). A tag appears under "Active tile filters"; "Clear filters" resets.
4. In the **Transition register** point to **Forecourt POS refresh**: **Red**, 3 critical gaps, decision in 4 days.
5. Scroll to **Escalation queue** (what is blocked and who is waiting) and **Decision calendar (next 45 days)**. Also **Orion: control tower insights**.
6. Say: "RAG is not typed in by hand; it is computed from the checklist, gaps and decision date. A director sees in one screen what needs attention."

### Step 3 – New transition: ServiceNow fetch (3 min)
1. Click **New transition**.
2. In the field **ServiceNow project ID** type `PRJ0052210` and click **Fetch from ServiceNow**. The form is pre-filled (message "Pre-filled from ServiceNow (mock)"): name **SMSM Photo Capture**, project type **Agentic AI**, portfolio **Retail Site Systems**, region Europe & South Africa, market UK, PM Daniel Brooks.
3. Scroll to **In-scope sites (Site ID + Site key)** (mandatory for Retail Site Systems; at least one row). Fill row 1: Site ID `UK-1001`, Site key `KEY-A1`. Click **Add site**, row 2: `UK-1002`, `KEY-B2`.
4. Because the type is an AI type, the AI fields are required: set **Audience** = Internal department, **Write actions** = No, **Sensitive data** = No. Confirm OR focal is Asha and the Architect / OLM / IRM are pre-picked.
5. Note the "Checklists that will apply" hint (Framework, AI Playbook, golden set, common) and click **Create transition**. You are taken to the tiering page.
6. Say: "The project type and portfolio decide which checklists apply. Retail needs site IDs because that is how the real process works."

### Step 4 – Tiering (3 min)
1. On the tiering wizard tabs **1. Questions**, **2. Proposed tier**, **3. AI profile**, stay on **1. Questions** (Tiering questions TQ1 – TQ5).
2. Answer **TQ4 = Yes** and leave the others No ("Unanswered questions count as No").
3. Go to **2. Proposed tier**: **Proposed tier (live)** shows **Tier 2** with the **Rationale** list and tier dimensions. Click **Propose tier 2** (the button label includes the number).
4. A banner says "Tier 2 proposed – waiting for IRM confirmation". Say: "The rule proposes, only the IRM can confirm."
5. Open the user menu (top right) -> **Switch user** -> **Fatima Khan**. Go to the same transition's tiering page (Transitions -> the new row, or Back button), tab **2. Proposed tier**, click **Confirm tier**.
6. Switch user -> **Asha Menon** again.
7. Optional (30 s): tab **3. AI profile**, fill one or two fields and **Save AI profile**; or skip and click **Continue to scope**.

### Step 5 – Scope and launch (3 min)
1. Open the transition's **Scope** page (link "Go to scope" / **Continue to scope**).
2. Show the items table (Requirement, Type, Gate, Owner hint, Lens, Applies?): the mandatory Retail site item is locked (lock icon, cannot be switched off). Rows marked "To confirm" await applicability.
3. In the card **Orion agent – recommended applicability** click **Accept all recommendations** (toast "Orion recommendations accepted"). Say: "Orion recommends, Asha accepts – one click, but a human click."
4. Click **Launch readiness assessment** (toast "Readiness assessment launched").
5. Show the counts in the scope summary: **Framework 72**, **AI Playbook 208 applicable / 8 excluded** (the excluded ones are Tier 3/4-only items, shown as not applicable for Tier 2), **Golden set**, **Common 2**. Use the link **Open assessment** if you want to show the grid.
6. Say: "In seconds a 280-item assessment is assembled for this exact project, tier and portfolio. Today that is a spreadsheet exercise."

### Step 6 – Flagship: Mobility Knowledge Agent (4 min)
1. Click **Transitions**, search `Mobility` (Search box), open **Mobility Knowledge Agent** (TR-0001; Agentic AI, GCC, Tier 2, current gate AtD).
2. Header: gate stepper, **Overall readiness at AtD**, **Next decision**, OR focal. Tabs: Overview, Assessment, Gaps, Evidence, Conditions, Gates, Hypercare, OCET, Support model, AI playbook, Activity.
3. **Assessment** tab: default Gate filter is "Current gate and earlier" (AtD). Show the **Lens** filter (Business / Technical / Compliance) and the readiness-by-lens bars. Expand an item to show evidence. Point at the **Source** badges: **Human** (a person set the status), **Workflow rule** (completed by a rule), **System** (seeded/imported). Say: "You can always see whether a person or a rule moved an item."
4. **AI playbook** tab: shows risk tier, AI profile and **Evaluation metrics**. Click **Import eval results (mock)**. Two metrics now show Fail: **hallucination 3.1% vs <= 2%** and **prompt-injection resistance 84% vs >= 90%**. Say: "In production this pulls from the evaluation platform."

### Step 7 – Gates tab, readiness check, Orion chaser (4 min)
1. **Gates** tab. The current gate (AtD) shows the **Readiness check** with the verdict **Not ready for AtD** (if you do not see it, click **Show readiness** on the gate card).
2. Walk the sections: **Blocking items** – **S45-014** red-team non-compliant (exception EX-01 pending), **FW-008** OCET not approved (input pending), **FW-035** support model gap; **Critical gaps**; **Open conditions** – **CON-001**; **Pending exceptions** – **EX-01**; **Evaluation results** – the two metrics below target; badges **OCET** and **Support model** status.
3. Read the **Orion assessment** paragraph and the **Recommended actions** (grouped: Chasers, Request exceptions, OCET, Support model, ...). Say: "Orion explains the verdict in plain language. The verdict itself is a rule, not the AI."
4. Click the **Draft chaser** action for S45-014 (or open the **Gaps** tab and click **Draft chaser** on S45-014). You land on **Orion drafts** with the draft open: **Draft preview**.
5. Edit the subject or a line of the body (HTML source box; live preview updates), click **Save changes**, then **Send**. Say: "Orion drafted, Asha reviewed and sent. Nothing leaves without a human click." (Assistive mode banner is visible; autonomous mode comes with M8.)
6. Click **Outbox**: the sent **Email** and the **Teams** row. Open the Teams row: **Adaptive Card preview** and the **Raw Adaptive Card JSON** accordion. The card is a preview only (actions disabled): "In production this goes through Graph and the Teams bot."

### Step 8 – Exception approval and condition (3 min)
1. User menu -> **Switch user** -> **Fatima Khan** (IRM). Click **Approvals** (tab **Waiting for me**).
2. Find the exception request **EX-01** (S45-014, scope red-teaming proportionate to Tier 2). Approval chain: IRM -> CISO/BISO. Click **Approve** on step 1 (IRM), optionally add a comment, confirm.
3. The next step is a mock CISO/BISO step: click **Approve as CISO/BISO (mock)** (note "Mock step: no real CISO/BISO integration"). Say: "The CISO/BISO sign-off is mocked in the demo; in production it routes to the real approver."
4. Go back to the flagship (Transitions -> Mobility Knowledge Agent) -> **Conditions** tab. Under exceptions EX-01 is Approved. On the **Gates** tab S45-014 no longer blocks: it is covered by the approved exception. Say: "A workflow rule re-evaluated readiness the moment the approval landed."
5. Switch user back to **Asha Menon** (conditions are closed by the owner). **Conditions** tab -> row **CON-001** (stress test, S3-019) -> **Close**. In the dialog enter a **Closing note** (for example "Stress test evidence uploaded") and confirm. CON-001 is Closed. (If the Close button is disabled, hover it: the reason is shown.)
6. Optionally return to **Gates** to show the blocker list is shorter. The verdict stays Not ready because OCET, support model and eval metrics remain: "Those are exactly the modules coming next."

### Step 9 – Audit trail (2 min)
1. Click **Audit trail**. Use the filters: **Entity** or search for **TR-0001**, then **Actor type**.
2. Show entries by **Human** (tier confirmed, condition closed, approvals), **Workflow rule** (readiness/exception effects), **Orion agent** (drafts created), **System** (seed/import). Expand a row (Show changes) for the **Before/After** diff.
3. Close with: "Orion drafted, people decided – and you can prove it."

## 3. What is coming next (say this at the end)

- **M6 OCET**: versions, five-year projection chart, "Request inputs" drafts, Architect enters input, Planner then OLM approval; approval completes FW-008 and S45-006 by workflow rule.
- **M7 Support model**: generate the support landscape from Confluence link and transcripts, edit it, review chain, **Generate PPT** download, evidence auto-linked to FW-035.
- **M8 Orion assistant**: side panel and chat ("Assess gate readiness", quick actions), proposals that run only after a human click, the reminder engine (rules R1–R5, assistive and autonomous modes) and the leadership update.
- **M9 Admin and demo controls**: playbook admin and the demo fast-forward for the flagship.
- Then the finale: readiness turns "Ready for AtD", Orion drafts the approval request, OLM approves in the Teams card, IRM approves in the web inbox, Asha records Approve and the gate moves to Hypercare; leadership update; full audit trail.

## 4. Backup answers and known limitations

- **Are these real integrations?** No. ServiceNow, Confluence, SharePoint/document store, Teams, email and the evaluation platform are mock services behind interfaces (NFR-01); switching to live does not change the UI or routers.
- **Login**: demo login, pick a user, no password. Production uses Entra ID SSO with role-based access.
- **Data**: all data (people, projects, scores) is synthetic and fictional.
- **Is Orion an LLM here?** Orion's text is produced by a mock AI service in this build; the architecture targets Azure OpenAI / Foundry. Rules (tiering, readiness, RAG, approvals) are deterministic code with unit tests, not AI.
- **Can Orion approve or change status?** No (BR-050). It drafts and recommends; enforced in the service layer.
- **Side panel / chat**: the Orion toggle in the top bar exists, the assistant itself is part of M8. Leadership updates, Support models and Admin pages are placeholders today.
- **OCET and support model tabs** show "What this module shows" placeholders: coming in M6/M7.
- **Run reminder engine now** (Orion drafts page) is disabled until M8.
- **Something looks stuck or wrong**: reload the page; if data is messy, reset (delete `backend/orion.db`, restart the API) and log in again.
- **Permissions**: a disabled button always has a reason on hover (for example only the IRM can confirm a tier, only the current approver can act on a chain step).
- **Teams card**: preview only; actions are disabled in the outbox. Real approval in Teams arrives with the Teams bot.
- **Excel/PPT exports**: not in this build (M6/M7).
