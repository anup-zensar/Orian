# Orion demo script – full build

Audience: client demo for the S&T team. Duration: **about 27–29 minutes** of clicking (20–25 if you shorten step 3) plus questions. This script follows the storyline in `docs/REQUIREMENTS.md` section 13. It extends the earlier `docs/DEMO_SCRIPT_M5.md` (steps 1–5 are the same flow, shortened) with Orion, OCET, support model, fast-forward, leadership update and audit.

"(check label)" marks a label or behaviour that was not confirmed in the code. Check it once in rehearsal.

## Timing

| Step | What | Minutes |
|---|---|---|
| 1 | Login and dashboard | 2 |
| 2 | Control tower | 2 |
| 3 | New transition from plain words, tiering, scope, launch | 5 |
| 4 | Flagship workspace | 2 |
| 5 | "Are we ready for AtD?" and a chaser | 3 |
| 6 | OCET | 3 |
| 7 | Support model and PPT | 3 |
| 8 | Exception and condition | 2 |
| 9 | Fast-forward, reminder engine, AtD approval chain, decision | 4 |
| 10 | Leadership update and audit trail | 3 |
| | Total | about 29 (drop the tiering detail in step 3 to save 2 minutes) |

## 0. Setup and reset before the demo

1. Start the app. Windows: `scripts\dev.ps1 -WebPort 5174` (5173 may be used by another local app). macOS/Linux: `make dev`. Open `http://127.0.0.1:5174` (or 5173).
2. Reset to a clean seed. Either:
   - Stop the API, run `scripts\reset.ps1` (macOS/Linux: `make reset`), restart the API; or
   - With the app running: log in as **Playbook Admin**, open **Admin** in the left navigation, tab **Demo controls**, click **Reset demo data**, confirm **Reset demo data**. Takes a few seconds.
3. For repeatable dates set `SEED_DATE` in `backend/.env` before starting (optional). With the seed date the flagship's AtD decision is in about 3 weeks and **Forecourt POS refresh** shows "decision in 4 days".
4. Check `backend/.env` has `DEMO_MODE=true` (otherwise Demo controls are hidden) and `AI_MODE=mock`, `MAIL_MODE=mock`.
5. Prepare two small files on the desktop for step 7: a transcript `walkthrough.txt` (any text, for example a few lines about hosting and support) and a diagram `landscape.png` (any image).
6. Log in as **Asha Menon** in the main window. Keep a second window ready if you prefer to switch users there. Use **Switch user** in the top-right user menu.
7. The demo changes data (new transition TR-00xx, sent drafts, approvals). Reset again before the next run.

Key messages (say early, repeat at the end):
1. One place for every transition: checklists, gaps, evidence, gates, approvals, history.
2. Two kinds of automation. A **Workflow rule** is deterministic (RAG, readiness, completing linked items). The **Orion agent** (AI badge) drafts and recommends.
3. **Orion recommends and drafts. People decide.** Orion never changes a status or records a decision. A permitted person clicks.
4. Every change is in the audit trail with who or what did it: Human, Workflow rule, Orion agent or System.

Users: **Asha Menon** (OR focal, main), **Fatima Khan** (IRM), **Mei Lin** (Architect), **Tom Becker** (Planner), **Sofia Garcia** (OLM), **Playbook Admin** (Admin). Standby: Daniel Brooks (PM), Laura Evans (Leadership).

Left navigation: Dashboard, Control tower, Transitions, New transition, Approvals, Orion drafts, Outbox, Leadership updates, Support models, Admin (Admin only), Audit trail. The **Orion** button in the top bar opens the Orion panel on the right.

---

## 1. Login and dashboard (2 min)

**Logged in as:** Asha Menon (OR focal). **Page:** `/login`, then `/` (Dashboard).

1. On the login page ("Demo login – pick a user, no password") click **Asha Menon**.
2. Dashboard opens. Point to the KPI tiles (My open items, My pending approvals, Transitions I own, Decisions due in 14 days, Critical gaps), the **My work** card, **Orion insights** (AI badge) and **Recent activity**.
3. Optional: switch to **Laura Evans** (Leadership) to show portfolio tiles instead of My work, then switch back to Asha.

Audience should see: her work, decisions due and Orion's observations, for example the Mobility Knowledge Agent insight "AtD in 21 days, blocked by 1 critical gap (S45-014 ...)".

Talking points:
- "Asha is an operate-readiness focal. This is her day: what is mine, what is due, what Orion noticed."
- "The dashboard, control tower and workspace all read the same data."

## 2. Control tower (2 min)

**Logged in as:** Asha Menon. **Page:** `/control-tower`.

1. Click **Control tower**.
2. Show the KPI tiles, **Heatmap: portfolio by gate** and **Readiness by region**.
3. Click the **Retail Site Systems** row or cell in the heatmap (or use the portfolio filter in the Filters bar). A tag appears under "Active tile filters". **Clear filters** resets.
4. In **Transition register** point to **Forecourt POS refresh**: **Red**, 3 critical gaps, decision in 4 days.
5. Scroll to **Escalation queue** and **Decision calendar (next 45 days)**. Show **Orion: control tower insights**.

Audience should see: a Red transition and the reason, filtered by portfolio.

Talking points:
- "RAG is computed from the checklist, gaps and decision date. Nobody types it in."
- "A director sees in one screen what needs attention and who is waiting."

## 3. New transition from plain words (5 min)

**Logged in as:** Asha Menon, then Fatima Khan, then Asha. **Pages:** Orion panel, `/transitions/new`, `/transitions/<id>/tiering`, `/transitions/<id>/scope`.

**3a. Describe it to Orion (1.5 min)**
1. Click **Orion** in the top bar. The panel opens: "How can Orion help?", seven quick actions (Start a gate review, Assess gate readiness, Track owner actions, Draft owner reminders, Create a leadership update, Create a support model, Create or update OCET) and the footer "Orion recommends and drafts. People decide."
2. In the box "Ask Orion, or describe what you need (Enter to send)" type or paste:
   `New Agentic AI transition for PRJ0052210, Retail Site Systems, UK, go-live 15 March 2027, architect Mei`
   and press Enter. (Alternative: click **Paste an email or description**, paste the text, click **Read this**.)
3. Orion answers with a **proposal card** titled "Start transition: ..." with a table of fields (Solution / transition name, ServiceNow project ID, Project type, Portfolio, Region, Market, Architect and others). Each found value has a source tag (ServiceNow, Your text, Inferred) and a confidence dot. Missing values say "Needs your input"; unclear ones say "Which one? You choose". The go-live date may show as "Next decision date" or as missing (check label).
4. Say: "Orion read the words, looked up PRJ0052210 in ServiceNow and proposed the form. Nothing exists yet." Click **Open pre-filled form**. (Also available: **Dismiss**.)

**3b. Check and create (1 min)**
1. The form `/transitions/new` opens with the banner "Pre-filled by Orion from your description - check and create". Fields filled by Orion carry an AI marker; editing a field removes it.
2. Check: **Solution / transition name** (SMSM Photo Capture), **Project type** (Agentic AI), **Mobility landscape category (portfolio)** (Retail Site Systems), **Market / country** (UK), **Architect** (Mei Lin).
3. Fill what Orion could not find. Under **In-scope sites (Site ID + Site key)** (mandatory for Retail Site Systems): row 1 Site ID `UK-1001`, Site key `KEY-A1`; click **Add site** (check label), row 2 `UK-1002`, `KEY-B2`. For the AI fields set **Audience** = Internal department, **Write actions** = No, **Sensitive data** = No. Confirm **OR focal** is Asha.
4. The "Checklists that will apply" panel shows Framework, AI Playbook, golden set, common. Click **Create transition**. You land on the tiering page.
5. Say: "Orion filled the form, a person checked it and clicked Create."

**3c. Tiering with the IRM (1 min)**
1. Tab **1. Questions**: answer **TQ4 = Yes**, leave the rest No.
2. Tab **2. Proposed tier**: **Proposed tier (live)** shows **Tier 2** with the **Rationale**. Click **Propose tier 2**. Banner: "Tier 2 proposed – waiting for IRM confirmation".
3. User menu -> **Switch user** -> **Fatima Khan** (IRM). Open the same transition's tiering page (Transitions -> the new row), tab **2. Proposed tier**, click **Confirm tier**.
4. Switch user -> **Asha Menon**.
5. Say: "The rule proposes. Only the IRM can confirm."

**3d. Scope and launch (1.5 min)**
1. Click **Continue to scope** (or open the transition's scope page).
2. Show the table: the mandatory Retail site item is locked. Rows marked "To confirm" await applicability.
3. In **Orion agent – recommended applicability** click **Accept all recommendations**. Toast: "Orion recommendations accepted".
4. Click **Launch readiness assessment**. Toast: "Readiness assessment launched".
5. Show the counts: **Framework 72**, **AI Playbook** applicable / excluded (excluded items are Tier 3/4-only, shown as not applicable for Tier 2), golden set, **Common 2**.

Talking points:
- "A 280-item assessment is assembled for this project, tier and portfolio in seconds. Today it is a spreadsheet exercise."
- "Typed words, a pasted email or an uploaded document all work the same way: Orion proposes, a person confirms."

## 4. Flagship workspace (2 min)

**Logged in as:** Asha Menon. **Page:** `/transitions/TR-0001/assessment`.

1. Click **Transitions**, search `Mobility`, open **Mobility Knowledge Agent** (TR-0001; Agentic AI, GCC, Tier 2, current gate AtD).
2. Header: gate stepper, **Overall readiness at AtD**, **Next decision**, OR focal. Tabs: Overview, Assessment, Gaps, Evidence, Conditions, Gates, Hypercare, OCET, Support model, AI playbook, Activity.
3. **Assessment** tab (default gate filter: current gate and earlier). Show the **Lens** filter (Business, Technical, Compliance) and readiness by lens. Expand an item to show evidence. Point at the source badges: **Human**, **Workflow rule**, **System**.
4. **AI playbook** tab: tier, AI profile, **Evaluation metrics**. Click **Import eval results (mock)**. Two metrics fail: hallucination 3.1% (target at most 2%) and prompt-injection resistance 84% (target at least 90%).

Talking points:
- "You can always see whether a person or a rule moved an item."
- "In production the eval import pulls from the evaluation platform."

## 5. "Are we ready for AtD?" and a chaser (3 min)

**Logged in as:** Asha Menon. **Pages:** Orion panel, `/transitions/TR-0001/gates`, `/drafts`, `/outbox`.

1. Open the Orion panel. Click the quick action **Assess gate readiness**. A form card appears: **Transition** and **Gate**. Pick Mobility Knowledge Agent and AtD (it is pre-selected when you are inside the workspace) and click **Assess readiness**.
2. Orion answers with a readiness card: verdict **Not ready for AtD**. (The same verdict is on the **Gates** tab under **Readiness check**.)
3. Walk the sections on the Gates tab: **Blocking items** (S45-014 red-team non-compliant with exception EX-01 pending; FW-008 OCET not approved; FW-035 support model gap), **Critical gaps**, **Open conditions** (CON-001), **Pending exceptions** (EX-01), **Evaluation results** (two metrics below target).
4. Read **Orion assessment** and **Recommended actions**.
5. On Gates tab or **Gaps** tab click **Draft chaser** for S45-014. You land on **Orion drafts**; the draft is open with **Draft preview**.
6. Edit the subject or a line of the body (**Subject**, **Body (text)**), click **Save changes** ("Draft saved"), then **Send**. Toast "Sent via email and Teams" with **View in Outbox**.
7. Click **Outbox**. Show the **Email** row and the **Teams** row. Open the Teams row: **Adaptive Card preview** and the raw JSON.

Talking points:
- "The verdict is a rule. Orion explains it in plain language and proposes the next actions."
- "Orion drafted, Asha reviewed and sent. Nothing leaves without a human click." (Banner shows Assistive mode.)
- "In production this goes through Graph and the Teams bot."

## 6. OCET (3 min)

**Logged in as:** Asha Menon -> Mei Lin -> Asha -> Tom Becker -> Sofia Garcia. **Pages:** `/transitions/TR-0001/ocet`, `/drafts`, `/approvals`.

1. As Asha open the flagship, tab **OCET**. Header shows **Currency**, **Start year**, **Horizon**, **Version** (v2) and **Approval chain**. Show the lines, the yearly columns and the charts: a cloud line of 100k at 10% per year grows to 146.4k in year 5. The status is Inputs pending.
2. Point at the line whose **Base amount** shows **Missing** (monitoring cost, owner Architect). Say: "No number is guessed. Missing stays missing."
3. Click **Request inputs**. Dialog "Request inputs": the missing line is ticked. Click **Request inputs** again. Toast: "Orion prepared 1 draft. Nothing is sent until you review it." Click **Open drafts**, open the draft, click **Send**.
4. User menu -> **Switch user** -> **Mei Lin**. Open the flagship, tab **OCET**. In the monitoring line's **Base amount** field type `10000` and click **Save**.
5. Switch user -> **Asha Menon**. Tab **OCET**, click **Submit for approval**. Toast "Submitted for approval".
6. Switch user -> **Tom Becker** (Planner). Click **Approvals**, tab **Waiting for me**, find the OCET request, click **Approve**, confirm **Approve**.
7. Switch user -> **Sofia Garcia** (OLM). **Approvals**, **Waiting for me**, the same request, **Approve**.
8. Open the flagship OCET tab: status **Approved**. Open the **Assessment** tab and show **FW-008** and **S45-006** now Complete with the badge **Workflow rule**.

Talking points:
- "The projection is arithmetic in a rule, not AI. Orion only explains changes (the Orion explanation card) and drafts the request."
- "Approval completed the two linked checklist items by workflow rule. Nobody ticked them."

## 7. Support model and PPT (3 min)

**Logged in as:** Asha Menon -> Mei Lin -> Sofia Garcia -> Asha. **Pages:** `/transitions/TR-0001/support-model`, `/approvals`.

1. As Asha open the flagship, tab **Support model**. Four steps: **1. Inputs**, **2. Generate**, **3. Review and edit**, **4. Export**.
2. **1. Inputs**: in **Confluence / Atlassian link** field **Page URL** paste a link containing "voc", for example `https://example.atlassian.net/wiki/spaces/VOC/pages/1`. (The mock matches the word VOC or Medallia and returns the Medallia VOC landscape. Without it the model is a generic landscape.) Under **Uploads** click **Choose files** for "Walkthrough recording or transcript" and pick `walkthrough.txt`; for "Architecture diagrams" pick `landscape.png`. Click **Save inputs** ("Inputs saved").
3. **2. Generate**: click **Generate support model**. Three simulated progress steps run (Orion agent, AI badge). The page moves to review.
4. **3. Review and edit**: the landscape shows Medallia in the centre and components around it. Click a node; in the side panel change **Name** (rename a node). Scroll to **Open questions** and edit the wording of one question (there is no separate answer field, see notes). Optionally click **Draft question to architect**. Click **Save**.
5. Click **Send for review**. Status becomes In review.
6. Switch user -> **Mei Lin**. **Approvals** -> **Waiting for me** -> support model request -> **Approve**.
7. Switch user -> **Sofia Garcia**. **Approvals** -> same request -> **Approve**. Status **Agreed**.
8. Switch user -> **Asha Menon**. Support model tab, step **4. Export**: click **Generate PPT** ("PowerPoint generated"), then **Download PPT**. Open the file in PowerPoint: 5 slides (title, landscape, support flow, contacts and SLA, open questions and sources), footer "Confidential".
9. Show **Linked items** on the Export step and **FW-035** on the Evidence tab (the PPT is attached as Generated evidence). Support-model items are Complete.

Talking points:
- "Today this is a manual slide after a walkthrough call. Orion drafts it from the recording, the Confluence page and the diagrams. A person reviews every node."
- "The generator is a mock behind an interface. The PPT export is real."

## 8. Exception and condition (2 min)

**Logged in as:** Fatima Khan, then Asha Menon. **Pages:** `/approvals`, `/transitions/TR-0001/conditions`.

1. Switch user -> **Fatima Khan** (IRM). Click **Approvals**, tab **Waiting for me**.
2. Find exception request **EX-01** (S45-014, red-team scope proportionate to Tier 2). The chain is IRM then CISO/BISO. Click **Approve** on the IRM step, optionally add a **Comment (optional)**, confirm.
3. The next step is a mock step: click **Approve as CISO/BISO (mock)**. Say: "The CISO/BISO sign-off is mocked. In production it routes to the real approver."
4. Open the flagship, tab **Conditions**: EX-01 is Approved. On the **Gates** tab S45-014 no longer blocks: it is covered by the approved exception.
5. Switch user -> **Asha Menon**. **Conditions** tab, row **CON-001** (stress test, S3-019), click **Close**. Enter a **Closing note** ("Stress test evidence uploaded") and confirm. CON-001 is Closed. (If **Close** is disabled, hover it for the reason.)

Talking points:
- "A workflow rule re-evaluated readiness the moment the approval landed."
- "Exceptions and conditions are explicit and owned, not an email thread."

## 9. Fast-forward, reminders and the AtD decision (4 min)

**Logged in as:** Playbook Admin -> Asha Menon -> Sofia Garcia -> Fatima Khan -> Asha Menon. **Pages:** `/admin`, `/drafts`, `/approvals`, `/transitions/TR-0001/gates`.

Say first: "This next click is a demo shortcut. It stands in for weeks of routine work."

1. Switch user -> **Playbook Admin**. Click **Admin**, tab **Demo controls**.
2. Card **Fast-forward flagship**: click **Fast-forward flagship**, confirm **Fast-forward**. Message: items completed, items left open (OCET and support model, exception), eval metrics passing, readiness. Click **Open TR-0001 gates tab** (check label: the link reads "Open <id> gates tab").
3. Gates tab, **Readiness check**: verdict **Ready for AtD**.
4. Back in **Admin -> Demo controls**, card **Run reminder engine**: click **Run reminder engine**. The result shows messages created per rule. Rule R4 created a draft. Click **Open drafts**.
5. Switch user -> **Asha Menon**. **Orion drafts**: find the draft with Source **Workflow rule** and subject "Ready for AtD - request OLM approval" (check label). Open it, review, click **Send**. Sending requests the AtD approval and notifies the approver.
6. Switch user -> **Sofia Garcia** (OLM). **Approvals** -> **Waiting for me** -> AtD request -> **Approve**. (The Teams preview page is not built; the Outbox shows the card JSON that Teams will post. See notes.)
7. Switch user -> **Fatima Khan** (IRM). **Approvals** -> same request -> **Approve**.
8. Switch user -> **Asha Menon**. Flagship, **Gates** tab. In the AtD panel (**Gate decision**) click **Approve**. In the dialog click **Record: Approve** (add a **Note** if you like). The gate moves to **SG5_HYPERCARE** (shown as Hypercare in the stepper).

Talking points:
- "Rule R4 noticed the criteria were met and drafted the request. Asha sent it."
- "OLM and IRM approved. Only then could Asha record the decision. Orion could not do any of those clicks."

## 10. Leadership update and audit trail (3 min)

**Logged in as:** Asha Menon. **Pages:** `/leadership-updates`, `/audit`.

1. Click **Leadership updates**. Click **Generate update**. In the dialog set **Scope** = One portfolio, **Portfolio** = GCC, click **Generate**. (Same result from the Orion panel: **Create a leadership update**.)
2. Show the update: the AtD approval, readiness, remaining risks. It is badged as Orion agent. Use **Copy to clipboard** to show it can be pasted anywhere.
3. Click **Send**, keep the **Recipients (comma separated)**, click **Send**. Toast "Leadership update sent via email and Teams" with **View in Outbox**.
4. Click **Audit trail**. Set **Transition** (or search) to TR-0001 and use **Actor type**.
5. Show **Human** entries (tier confirmed, condition closed, approvals, decision), **Workflow rule** (linked items completed, readiness effects), **Orion agent** (drafts created), **System** (seed, fast-forward). Expand a row for the before and after diff.
6. Close with: "Orion drafted, people decided, and you can prove it."

---

## What to say when asked

**"Is the AI real?"**
"Not in this demo. Orion's text and suggestions come from a deterministic mock: templates filled with real data, keyword matching and field extraction against the reference data. The same input always gives the same output. The architecture is ready for Azure OpenAI or AI Foundry behind the same interface, with the facts and numbers still computed by rules. The tiering, readiness, RAG, approvals and OCET maths are plain code with unit tests, not AI. That is by design."

**"Are the integrations real?"**
"No. ServiceNow, Confluence, SharePoint, Microsoft Graph mail, the Teams bot and transcription are mocks behind interfaces. The Outbox shows the email and the Adaptive Card that would be sent. Switching to live changes configuration and one class per service, not the screens or the rules. The mapping and what each live service needs is in the README, section 4. The PPT export is real."

**"Can Orion approve or change a status?"**
"No. It drafts and proposes. A proposal runs only when a permitted person accepts it, and then it runs as that person and is audited as Human."

**"Is the data real?"**
"No. All people, projects and scores are synthetic."

**"How does sign-in work?"**
"Demo login with no password. Production uses Entra ID single sign-on and role-based access."

## Troubleshooting

- **Port 5173 already in use:** run `scripts\dev.ps1 -WebPort 5174` and open `http://127.0.0.1:5174`. If you change the port, also add it to `CORS_ORIGINS` and `APP_BASE_URL` in `backend/.env`.
- **Page is blank or data looks wrong:** reload the browser. If the data is messy, reset (Admin -> Demo controls -> Reset demo data, or `scripts\reset.ps1` with the API stopped) and log in again.
- **A button is disabled:** hover it. The tooltip gives the reason (for example only the IRM can confirm a tier, only the current approver can act on a step, save your changes first).
- **403 "only the assigned person":** you are signed in as a person who is not assigned to that role on that transition. Switch to the user named in the script.
- **Admin has no Demo controls tab:** `DEMO_MODE` is not `true` in `backend/.env`. Restart the API after changing it.
- **Readiness is not "Ready for AtD" after fast-forward:** OCET and the support model are skipped by fast-forward. Complete steps 6 and 7 first, or the exception and condition in step 8.
- **"Run reminder engine" creates no R4 draft:** the flagship must be Ready for AtD first (step 9.2). Duplicates of open drafts are skipped, so run it once.
- **Orion panel answers "I did not understand":** use a quick action button, or rephrase with the project id, for example "New Agentic AI transition for PRJ0052210 ...". Example phrases are listed under "Try saying".
- **Download does not open:** the PPT is downloaded by the browser. Check the downloads folder. It needs PowerPoint or a compatible viewer.
- **Backend not responding:** check the API window; the docs page is `http://127.0.0.1:8000/docs`. Mock delay is 600 ms by default; set `MOCK_DELAY_MS=0` to make it snappier.

## Notes for the presenter (gaps against the storyline)

- Storyline step 3 starts a new transition via the Orion quick action "Start a gate review". That quick action only links to the intake form. The word-based creation in this script uses the message box (or **Paste an email or description**).
- Storyline step 7 says "answer an open question". The UI lets you edit the question text and has **Draft question to architect**; there is no separate answer field.
- Storyline step 9 says Sofia approves the AtD card in the **Teams preview**. The Teams preview is a deferred item (FR-120). She approves in the **Approvals** inbox instead; the card JSON is visible in the Outbox.
- Storyline step 5 "Assess gate readiness (Orion panel)" works in the panel; the same verdict is on the **Gates** tab.
