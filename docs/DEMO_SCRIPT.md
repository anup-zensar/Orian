# Orion demo script

Presenter's script for the storyline in `docs/REQUIREMENTS.md` section 13. About **25 minutes** of clicking plus questions
(save 2 minutes by skipping the tiering detail in step 3). Every label below was checked in the running app.
"Fallback" is the one-line recovery if something does not show.

| Step | What | Min |
|---|---|---|
| 1 | Login and dashboard | 2 |
| 2 | Control tower | 2 |
| 3 | New transition from plain words, tier, scope, launch | 5 |
| 4 | Flagship workspace | 2 |
| 5 | "Are we ready for AtD?" and a chaser | 3 |
| 6 | OCET | 3 |
| 7 | Support model and PowerPoint | 3 |
| 8 | Exception and condition | 1 |
| 9 | Fast-forward, "Ready for AtD" request, approval chain, decision | 3 |
| 10 | Leadership update and audit trail | 2 |

## 0. Before the demo

1. Start the app (Windows: `scripts\dev.ps1`, then open `http://127.0.0.1:5173`; if 5173 is taken, see Troubleshooting). Use Edge or Chrome, window about **1440 x 900**, zoom 100%.
2. If `backend/.env` exists (copy of `backend/.env.example`), check `DEMO_MODE=true`, `AI_MODE=mock`, `MAIL_MODE=mock`; with no file the defaults are the same. Optional: `MOCK_DELAY_MS=0` for a snappier demo.
3. **Reset to a clean seed:** sign in as **Playbook Admin**, click **Admin** in the left navigation, section **Demo controls** (menu inside Admin), card **Reset demo data**: click **Reset demo data**, then confirm **Reset demo data**. (Or stop the API, run `scripts\reset.ps1`, restart.) Reset again before every run.
4. Two small files on the desktop for step 7: `walkthrough.txt` (a few lines of text) and, optional, `landscape.png` (any image).
5. Sign in as **Asha Menon**. Switch user any time: top-right **user menu -> Switch user -> name**. Users: Asha Menon (OR focal), Fatima Khan (IRM), Mei Lin (Architect), Tom Becker (Planner), Sofia Garcia (OLM), Playbook Admin (Admin). Standby: Daniel Brooks (PM), Laura Evans (Leadership). On the login page the eight other OR focals (U02-U09) sit under a collapsed **Other OR focals** heading.
6. Left navigation: Dashboard, Control tower, Transitions, Approvals, Audit trail, and, only when the signed-in role has the permission, Orion drafts, Outbox, Leadership updates and Admin (Admin only). Roles without the permission do not see those items. There is no separate "New transition" or "Support models" item: start a transition with the button on the **Transitions** page (or from Orion), and open the support model from the transition's **Support model** tab. The **Orion** button in the top bar opens the Orion panel on the right. Leave the **Autonomous mode** switch in a transition header off.

Say early and repeat at the end:
1. One place for every transition: checklists, gaps, evidence, gates, approvals, history.
2. Two kinds of automation: a **Workflow rule** is deterministic (RAG, readiness, completing linked items); the **Orion agent** (AI badge) drafts and recommends.
3. **Orion recommends and drafts. People decide.**
4. Every change is audited: Human, Workflow rule, Orion agent or System.

---

## 1. Login and dashboard (2 min)

**Signed in:** Asha Menon. **Page:** `/login`, then `/`.

1. Login page ("Demo login – pick a user, no password", below the **Sign in with Microsoft** button, which is only a placeholder for single sign-on): click **Asha Menon**.
2. Dashboard: KPI tiles (My open items, My pending approvals, Transitions I own, Decisions due in 14 days, Critical gaps), **My work**, **Orion insights** (AI badge), **Recent activity**.
3. In **Orion insights**, on "Mobility Knowledge Agent: AtD in 21 days, blocked by 1 critical gap ..." click **Draft a chaser**. A toast says "Chaser drafted" with **Open drafts**. Do not send it; you will ignore or discard it later.
4. Optional: switch to **Laura Evans** (Leadership) to show portfolio tiles, then back to Asha.

Notice: her work, decisions due, Orion's observations; **Recent activity** reads as short sentences, newest first.
Fallback: if no insight shows, skip the chaser; step 5 drafts one anyway.

## 2. Control tower (2 min)

**Signed in:** Asha Menon. **Page:** `/control-tower`.

1. Click **Control tower**. Show the KPI tiles, **Heatmap: portfolio by gate**, **Readiness by region**. The page no longer holds the full register: tiles and heatmap cells open **Transitions** with the same filters in the URL.
2. In the heatmap click the red **2 Red** cell in the **Retail Site Systems** row under **AtD**. **Transitions** opens filtered to that portfolio and current gate. (**More filters** on that page holds Region, Status and Project type.) Click **Clear filters** or use the browser Back button to return.
3. In the filtered list: **Forecourt POS refresh** is **Red**, 3 critical gaps, decision in 4 days.
4. Back on **Control tower**, scroll to **Escalation queue**, **Decision calendar (next 45 days)** and **Orion: control tower insights**.

Notice: RAG is computed, nobody types it in. Fallback: open **Transitions** and use the portfolio filter.

## 3. New transition from plain words (5 min)

**Signed in:** Asha Menon, then Fatima Khan, then Asha. **Pages:** Orion panel, `/transitions/new`, `.../tiering`, `.../scope`.

**3a. Orion (1.5 min)**
1. Click **Orion** in the top bar. Panel: "How can Orion help?", seven quick actions (on the welcome screen only; after the first message they collapse into a compact **Quick actions** menu), "Try saying", footer "Orion recommends and drafts. People decide."
2. Optional two lines of Orion Q&A: type `who owns S45-014` (Orion answers in sentences, for example "S45-014 ... is owned by Fatima Khan (IRM) on Mobility Knowledge Agent (TR-0001)", one per transition that has the item). Type `chase the owner of S3-019`: with no transition open, a small card **Draft owner reminders** asks you to pick the **Transition** (then **Draft reminders**). Say: "It asks instead of guessing."
3. In the box "Ask Orion, or describe what you need (Enter to send)" type and press Enter:
   `New Agentic AI transition for PRJ0052210, Retail Site Systems, UK, go-live 15 March 2027, architect Mei`
4. Orion answers "I found 5 of 9 required fields. Review the card, then click Open pre-filled form", with a **Start transition: SMSM Photo Capture** card. Each value has a source tag (ServiceNow, Your text, You (default)); go-live shows as **Next decision date 2027-03-15**. Say: "Nothing exists yet." Click **Open pre-filled form** (or **Dismiss**).

**3b. Check and create (1 min)**
1. `/transitions/new` (also reachable from the **New transition** button on the **Transitions** page) opens with "Pre-filled by Orion from your description - check and create". Close the Orion panel (X) for room. Orion-filled fields carry an AI mark.
2. Check **Solution / transition name** (SMSM Photo Capture), **Project type** (Agentic AI), **Mobility landscape category (portfolio)** (Retail Site Systems), **Market / country** (UK), **Architect** (Mei Lin).
3. Fill what Orion could not find: under **In-scope sites (Site ID + Site key)** row 1 `UK-1001` / `KEY-A1`; **Add site**; row 2 `UK-1002` / `KEY-B2`. **Audience** = Internal department, **Write actions** = No, **Sensitive data** = No.
4. Click **Create transition**. You land on the tiering page.
5. Duplicate guard (optional, 30 s): ask Orion the same sentence again. The card now shows an orange warning "TR-00xx already exists for PRJ0052210 - open it, or confirm to create a second transition". If you fill the form and click **Create transition**, a dialog "A transition already exists for this ServiceNow project" offers **Open TR-00xx**, **Create anyway**, **Cancel**. Click **Cancel**.

**3c. Tier with the IRM (1 min)**
1. The tiering page shows the questions and the proposed tier side by side (no tabs, no Next step). Answer **TQ4 = Yes** and leave the others unanswered (unanswered counts as No).
2. **Proposed tier (live)** shows **Tier 2** with the reasons. Click **Propose tier 2**. Banner: "Tier 2 proposed – waiting for IRM confirmation."
3. **Switch user -> Fatima Khan**, **Transitions** -> open the new row (SMSM Photo Capture) -> click the **Confirm scope and launch** link -> the **Open tiering** link (or type `/transitions/TR-00xx/tiering`) -> click **Confirm tier**. Then **Switch user -> Asha Menon**.
4. Say: "The rule proposes, only the IRM confirms." (Project types without tiering skip this page: the tiering link redirects to scope.)

**3d. Scope and launch (1.5 min)**
1. Click the **Continue to scope** link. Show the locked mandatory Retail site item; "To confirm" rows await a decision.
2. In **Orion agent - recommended applicability** click **Accept all recommendations**, then **Launch readiness assessment**.
3. Counts: **Framework 72**, **AI Playbook 208** (8 excluded by tier), **Golden set 5** (after Accept all; 1 before), **Common 2**, **Total applicable 286**.

Notice: a 286-item assessment is assembled in seconds. Words, a pasted e-mail or an uploaded document all work the same way: Orion proposes, a person confirms.
Fallback: if Orion misreads the sentence, click **Paste an email or description**, paste it, click **Read this**; or fill `/transitions/new` by hand.

## 4. Flagship workspace (2 min)

**Signed in:** Asha Menon. **Page:** `/transitions/TR-0001/assessment`.

1. **Transitions**, search `Mobility`, open **Mobility Knowledge Agent** (TR-0001; Agentic AI, GCC, Tier 2, gate AtD).
2. Header: gate stepper, **Overall readiness at AtD**, **Next decision**, OR focal, **Autonomous mode** switch (leave off), **Ask Orion**. Tabs: Overview, Assessment, Gaps, Evidence, Conditions, Gates, Hypercare, OCET, Support model, AI playbook, Activity (tabs that do not fit are in a **...** menu). **Overview** has one **Needs attention** card (open conditions, pending exceptions, risks), the five latest activity rows and a one-line gate summary.
3. **Assessment**: the table shows ID, Item, Lens, Owner, Status and a row menu. Show the **Lens** filter and readiness by lens (Gate, Source, Owner and **Show excluded items** are behind **More filters**); expand an item to see Source, Design effectiveness, evidence count and last updated, and point at the source badge (all **System** on a clean seed); **Workflow rule** appears after step 6 and **Human** when someone edits an item.
4. **AI playbook** tab: The eval table already holds results (clicking **Import eval results (mock)** only refreshes them). Two metrics fail: hallucination 3.1% (target at most 2%) and prompt-injection resistance 84% (at least 90%).

Fallback: if the eval table is empty, click **Import eval results (mock)** again.

## 5. "Are we ready for AtD?" and a chaser (3 min)

**Signed in:** Asha Menon. **Pages:** Orion panel, `/transitions/TR-0001/gates`, `/drafts`, `/outbox`.

1. Open the Orion panel on the flagship (context chip "TR-0001"). Click **Assess gate readiness**: **Transition** and **Gate** are pre-filled (AtD). Click **Assess readiness**.
2. Orion answers **Not ready for AtD**. Open the **Gates** tab (the current gate is open by default; other gates have **Show** and **Hide** buttons): **Readiness check** says the same.
3. Walk the sections: **Blocking items** (by lens; 61 in total before the fixes: OCET FW-008, support model FW-035, red-team S45-014), **Open conditions** (CON-001), **Pending exceptions** (EX-01), **Evaluation results**. Read **Orion assessment** and its recommended next step and action buttons.
4. Click the recommended action **Ask Fatima Khan (IRM) to approve exception EX-01 for S45-014**. You land on **Orion drafts** with the newest draft open. Ignore the older identical draft from step 1 (or click **Discard** on it).
5. Click **Edit as text**, change the **Subject**, click **Save changes** ("Draft saved"), then **Send**. Toast "Sent via email and Teams" with **View in Outbox**.
6. **Outbox**: one **Email** row and one **Teams** row. Open the Teams row to show the Adaptive Card.

Notice: the verdict is a rule; Orion words it and proposes the next step. Nothing leaves without a human click ("Assistive mode" banner).
Fallback: if that action is missing, on the **Gaps** tab click **Draft chaser** on any gap row (enabled for the OR focal only).

## 6. OCET (3 min)

**Signed in:** Asha Menon -> Mei Lin -> Asha -> Tom Becker -> Sofia Garcia. **Pages:** `/transitions/TR-0001/ocet`, `/approvals`.

1. As Asha open tab **OCET**: **Currency**, **Start year**, **Horizon**, **Version** ("v2 (Inputs pending)"), **Approval chain** Planner -> OLM. Show the lines, the year columns and the charts (cloud 100k at 10% a year: 146.4k in year 5).
2. Point at the **Monitoring tool subscription** line with no base amount: "No number is guessed. Missing stays missing."
3. Click **Request inputs**. Dialog lists the missing line; click **Request inputs (1)**. Toast "Orion prepared 1 draft. Nothing is sent until you review it." Click **Open drafts**, open the draft, click **Send**.
4. **Switch user -> Mei Lin**, flagship, tab **OCET**: in the monitoring line's **Base amount** type `10000`, click **Save**.
5. **Switch user -> Asha Menon**, tab **OCET**, click **Submit for approval**.
6. **Switch user -> Tom Becker**, **Approvals** (opens on the first tab that has items; use tab **Waiting for me**): click **Approve**, confirm **Approve**.
7. **Switch user -> Sofia Garcia**, **Approvals**: **Approve**, confirm. OCET shows **Approved**.
8. Flagship **Assessment** tab: **FW-008** and **S45-006** are Complete with the badge **Workflow rule**.

Notice: the projection is arithmetic in a rule, not AI. Approval completed two checklist items by rule; nobody ticked them.
Fallback: if **Submit for approval** is disabled, hover it; the base amount was not saved.

## 7. Support model and PowerPoint (3 min)

**Signed in:** Asha Menon -> Mei Lin -> Sofia Garcia -> Asha. **Pages:** `/transitions/TR-0001/support-model`, `/approvals`.

1. As Asha open tab **Support model**: one page with four sections headed **1. Inputs**, **2. Generate**, **3. Review and edit**, **4. Export** (no sub-tabs). Once a model exists, Inputs and Generate collapse behind an **Expand** button.
2. **1. Inputs**: in **Confluence / Atlassian link**, **Page URL**, paste `https://example.atlassian.net/wiki/spaces/VOC/pages/1` (the word "voc" selects the Medallia VOC landscape). Under **Uploads** click **Choose files** for "Walkthrough recording or transcript" and pick `walkthrough.txt`. Click **Save inputs**.
3. **2. Generate**: click **Generate support model**. The model appears in section 3 (a Medallia VOC landscape).
4. **Review and edit**: click a node and rename it. Scroll to **Open questions**: the questions have an answer box (accessible name **Answer to question 1**, placeholder "Answer (optional)"). Type an answer into the first one, for example `KPMG runs L2, Medallia runs L3`. The question shows an **Answered** badge; click **Save** (the indicator reads Saved).
5. Click **Send for review**. Status: In review.
6. **Switch user -> Mei Lin**: **Approvals** -> **Waiting for me** -> **Approve** (confirm). **Switch user -> Sofia Garcia**: same. Status **Agreed**.
7. **Switch user -> Asha Menon**, support model tab, **4. Export**: **Generate PPT**, then **Download PPT**. The deck has 5 slides and an **Answered questions** block with the answer you typed. Show **FW-035** on the **Evidence** tab: the PPT is attached; support-model items are Complete.

Notice: today this is a manual slide after a walkthrough call; here Orion drafts it and a person reviews every node. The generator is a mock; the PPT export is real.
Fallback: no PowerPoint on the machine: show the **Linked items** list on the Export step instead.

## 8. Exception and condition (1 min)

**Signed in:** Fatima Khan, then Asha Menon. **Pages:** `/approvals`, `/transitions/TR-0001/conditions`.

1. **Switch user -> Fatima Khan**, **Approvals**, tab **Waiting for me**: exception **EX-01** (red-teaming scope proportionate to Tier 2), chain IRM review then CISO/BISO. Click **Approve** (confirm), then **Approve as CISO/BISO (mock)** and confirm **Approve** again. Say: "In production this routes to the real approver."
2. **Switch user -> Asha Menon**, flagship **Conditions** tab: EX-01 is **Approved**. On the CON-001 row click **Close**, type a **Closing note** ("Stress test evidence uploaded"), click **Close condition**.

Fallback: if **Close** is disabled, hover it for the reason; make sure you are Asha.

## 9. Fast-forward, "Ready for AtD" request, decision (3 min)

**Signed in:** Playbook Admin -> Asha Menon -> Sofia Garcia -> Fatima Khan -> Asha Menon. **Pages:** `/admin`, `/drafts`, `/approvals`, `/transitions/TR-0001/gates`.

Say first: "This click is a demo shortcut for weeks of routine work." It only gives **Ready** after steps 6, 7 and 8: on a clean seed the flagship stays **Not ready** until OCET, the support model and EX-01 are done (A-73, A-87).

1. **Switch user -> Playbook Admin**, **Admin**, section **Demo controls**, card **Fast-forward flagship**: click **Fast-forward flagship**, confirm **Fast-forward**.
2. The green message shows items completed, items left open, eval metrics passing, "Readiness: Ready." and: Orion (rule R4) drafted "Ready for AtD - request OLM approval" with a link **Open Orion drafts**. (Click **Open TR-0001 gates tab** to show **Readiness check: Ready for AtD**.)
3. **Switch user -> Asha Menon**, **Orion drafts** (it opens on **Needs review (Draft)**; Kind and Source are behind **More filters**). The draft (Kind "Approval request", Source "Workflow rule R4") is the approval request itself: **To** Sofia Garcia (the OLM, first approver), **Cc** Asha. Click it, review, click **Send**.
4. **Outbox**: at the top, the **Email** to Sofia (cc Asha) and the Teams card "Agreement to Deploy for Mobility Knowledge Agent needs your approval (step 1)". Older rows are the approval notifications from steps 6 to 8.
5. **Switch user -> Sofia Garcia**, **Approvals** -> **Waiting for me** -> **Approve** (confirm). **Switch user -> Fatima Khan**: same for step 2.
6. **Switch user -> Asha Menon**, flagship **Gates** tab: in the AtD panel click **Approve**, then **Record: Approve** (add a **Note** if you like). The gate moves to Hypercare.
7. In the header **Next decision** now says **Not set** with a **Set date** button (Orion never invents a date; the OR focal sets the next one).

Notice: sending the draft started the chain; the OLM got one e-mail and one actionable card. Orion could not click any approval. Teams preview is not built (Fallback for the card: open the Teams row in the Outbox).
Fallback: if no R4 draft appears, open **Orion drafts** and click **Run reminder engine now** (the single reminder line shows the last run; duplicates are skipped). If fast-forward says "Not ready", finish steps 6 to 8 first.

## 10. Leadership update and audit trail (2 min)

**Signed in:** Asha Menon. **Pages:** `/leadership-updates`, `/audit`.

1. **Leadership updates** (shown to roles with the permission) -> **Generate update**. Dialog: **Scope** = One portfolio, **Portfolio** = GCC, **Generate**.
2. Show the update (Orion agent badge): headline with "AtD approved for Mobility Knowledge Agent", status by portfolio, top risks, wins. **Copy to clipboard** works.
3. Click **Send**, keep the **Recipients**, click **Send**. Toast "Leadership update sent via email and Teams" with **View in Outbox**.
4. **Audit trail**: set **Transition** to TR-0001; use **Actor type** (Entity and From/To are behind **More filters**). Show **Human** (tier, approvals, decision), **Workflow rule** (linked items completed), **Orion agent** (drafts), **System** (seed, fast-forward). Expand a row for before and after.
5. Close: "Orion drafted, people decided, and you can prove it."

Fallback: **Dashboard -> Recent activity** shows the same story as sentences.

---

## When asked

- **Is the AI real?** Not in this demo: a deterministic mock (templates filled with real data, keyword intents, field extraction). Same input, same output. Azure OpenAI or AI Foundry plugs in behind the same interface; tiering, readiness, RAG, approvals and OCET maths stay plain code with tests.
- **Are the integrations real?** No: ServiceNow, Confluence, SharePoint, Graph mail, the Teams bot and transcription are mocks. The Outbox shows the e-mail and card that would go out. Mapping: README section 4. The PPT export is real.
- **Can Orion approve or change a status?** No. It drafts and proposes; a proposal runs only when a permitted person accepts it, as that person, audited as Human.
- **Is the data real?** No, all synthetic. **Sign-in?** Demo login now; Entra ID single sign-on in production.

## Troubleshooting

- **Port 5173 in use:** `scripts\dev.ps1 -WebPort 5174`, open that port, and set `APP_BASE_URL=http://127.0.0.1:5174` in `backend/.env` so links in e-mails and cards match.
- **Blank page or odd data:** reload; if still wrong, reset (step 0.3) and sign in again.
- **Menu item missing:** Orion drafts, Outbox, Leadership updates and Admin are hidden for roles without the permission; switch to a user who has it.
- **Disabled button:** hover it; the tooltip gives the reason (wrong user, not your turn in the chain, unsaved changes).
- **No Demo controls in Admin:** `DEMO_MODE` is not `true`; restart the API after changing it.
- **Orion answers "I can help with: ..." instead of doing what you asked:** use a quick action or include the project id, for example `New Agentic AI transition for PRJ0052210 ...`.
- **Download does not open:** check the browser downloads folder; PowerPoint or a compatible viewer is needed.
- **API not responding:** check its window; docs at `http://127.0.0.1:8000/docs`.

## Where the app and the spec storyline differ

- Spec step 3 starts from the quick action "Start a gate review"; that action only links to the intake form. The word-based start in this script uses the message box.
- Spec step 9 has Sofia approve in a Teams preview; that page is deferred (FR-120). She approves in the **Approvals** inbox and the Outbox shows the card.
- Spec step 9 has Orion draft "Ready for AtD - request OLM approval" after fast-forward; in the app fast-forward itself runs rule R4 (A-77), so the draft is waiting without an extra click.
