"""The full demo storyline (spec section 13, steps 1-11) as one API regression test.

One test function walks every step in order on a freshly seeded database, because each step builds on
the previous one (the flagship TR-0001 moves from "Not ready for SG4 (AtD)" to gate SG5_HYPERCARE). Small
helper functions per step keep it readable. Business data is only changed by a permitted human (or by a
workflow rule after a human approval); Orion chat and extract change nothing (BR-050).

Demo users: U01 Asha (OR focal of TR-0001), U02 another OR focal, U10 PM, U11 Architect Mei Lin,
U12 OLM Sofia, U13 Planner Tom, U14 IRM Fatima, U15 Leadership Laura, U16 Admin.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

API = "/api/v1"
TR = "TR-0001"
NEW_TRANSITION_TEXT = (
    "New Agentic AI transition for PRJ0052210, Retail Site Systems, UK, "
    "go-live 15 March 2027, architect Mei"
)


class Walker:
    """Tiny API client: signs in as a demo user per call and checks the expected status code."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def call(
        self,
        method: str,
        path: str,
        user: str,
        expect: int | tuple[int, ...] = (200, 201),
        **kwargs: Any,
    ) -> Any:
        response = self.client.request(method, API + path, headers={"X-Demo-User": user}, **kwargs)
        allowed = (expect,) if isinstance(expect, int) else expect
        assert response.status_code in allowed, (
            f"{user} {method} {path} -> {response.status_code} (expected {allowed}): "
            f"{response.text[:600]}"
        )
        try:
            return response.json()
        except ValueError:
            return response

    def get(self, path: str, user: str = "U01", **kw: Any) -> Any:
        return self.call("GET", path, user, **kw)

    def post(self, path: str, user: str = "U01", body: Any = None, **kw: Any) -> Any:
        return self.call("POST", path, user, json=body, **kw)

    def forbidden(self, method: str, path: str, user: str, body: Any = None, **kw: Any) -> None:
        """The write is refused with 403 and a human-readable reason."""
        data = self.call(method, path, user, expect=403, json=body, **kw)
        detail = data.get("detail") if isinstance(data, dict) else None
        message = detail if isinstance(detail, str) else str((detail or {}).get("message", ""))
        assert len(message.split()) >= 3, f"{user} {method} {path}: no human reason in {data}"


def item_row(w: Walker, item_id: str, tid: str = TR) -> dict[str, Any]:
    rows = w.get(f"/transitions/{tid}/items?all_gates=true&q={item_id}")["items"]
    matching = [r for r in rows if r["item_id"] == item_id]
    assert matching, f"item {item_id} not found on {tid}"
    return matching[0]


def table_counts(db: Session) -> dict[str, int]:
    """Row counts of every table that holds business data (not Orion's own proposal/notice tables)."""
    skip = {"orion_proposals", "notifications"}
    names = [n for n in inspect(db.get_bind()).get_table_names() if n not in skip]
    counts: dict[str, int] = {}
    for name in names:  # table names come from the schema, not from user input
        counts[name] = db.execute(text(f"select count(*) from {name}")).scalar() or 0  # noqa: S608
    return counts


# --------------------------------------------------------------------------------------------------
# Step 2 - control tower
# --------------------------------------------------------------------------------------------------
def step2_control_tower(w: Walker) -> None:
    tower = w.get("/control-tower?portfolio=Retail%20Site%20Systems", "U01")
    assert tower["filters"]["portfolio"] == "Retail Site Systems"
    rows = {t["name"]: t for t in tower["transitions"]}
    assert {t["portfolio"] for t in rows.values()} == {"Retail Site Systems"}
    pos = rows["Forecourt POS refresh"]
    assert pos["rag"] == "Red"
    assert pos["critical_gaps"] == 3
    assert pos["days_to_next_decision"] == 4


# --------------------------------------------------------------------------------------------------
# Step 3 - new transition from plain words
# --------------------------------------------------------------------------------------------------
def step3_new_transition(w: Walker, db: Session) -> str:
    # Orion extract only proposes: no business table changes.
    before = table_counts(db)
    extract = w.call("POST", "/orion/extract", "U01", data={"text": NEW_TRANSITION_TEXT})
    assert table_counts(db) == before
    proposals = [m["proposal"] for m in extract["messages"] if m["type"] == "proposal"]
    assert [p["kind"] for p in proposals] == ["create_transition"]
    proposal = proposals[0]
    assert proposal["status"] == "Open"
    assert proposal["generated_by"] == "Orion agent"

    # The human accepts; the UI then opens the new-transition form with the prefill.
    accepted = w.post(f"/orion/proposals/{proposal['id']}/accept", "U01")
    assert accepted["navigate_to"] == f"/transitions/new?proposal={proposal['id']}"
    full = w.get(f"/orion/proposals/{proposal['id']}", "U01")
    prefill = dict(full["payload"]["prefill"])
    assert prefill["name"] == "SMSM Photo Capture"
    assert prefill["project_type"] == "Agentic AI"
    assert prefill["portfolio"] == "Retail Site Systems"
    assert prefill["market"] == "UK"

    # The human completes what Orion could not find (two sites, audience, write actions, sensitive data).
    body = dict(prefill)
    body["sites"] = [
        {"site_id": "UK-1001", "site_key": "KEY-A1"},
        {"site_id": "UK-1002", "site_key": "KEY-B2"},
    ]
    body.update(audience="Internal department", write_actions="No", sensitive_data="No")
    body.update(irm_user_id="U14", olm_user_id="U12", target_gate="AtD")
    created = w.post("/transitions", "U01", body)
    tid = created["id"]
    assert created["or_focal"]["id"] == "U01"

    # A duplicate for the same ServiceNow project is refused unless the human confirms it.
    duplicate = w.post("/transitions", "U01", body, expect=409)
    assert "PRJ0052210" in str(duplicate) or "duplicate" in str(duplicate).lower()
    again = w.post("/transitions", "U01", {**body, "confirm_duplicate": True})
    assert again["id"] != tid

    # Tiering: the rule proposes Tier 2 (TQ4 = yes) with a rationale; only the IRM confirms.
    proposed = w.call("PUT", f"/transitions/{tid}/tier", "U01", json={"answers": {"TQ4": True}})
    assert proposed["status"] == "Proposed"
    assert proposed["proposed_tier"] == 2
    assert proposed["rationale"]
    w.forbidden("POST", f"/transitions/{tid}/tier/confirm", "U01", {"tier": 2})
    confirmed = w.post(f"/transitions/{tid}/tier/confirm", "U14", {"tier": 2})
    assert confirmed["status"] == "Confirmed" and confirmed["confirmed_tier"] == 2

    # Scope: the mandatory Retail site item is locked; accepting the defaults launches the assessment.
    scope = w.get(f"/transitions/{tid}/scope", "U01")
    site_item = next(r for r in scope["golden_set"] if r["id"] == "RSS-01")
    assert (
        site_item["locked"] and site_item["type"] == "Mandatory" and site_item["applies"] == "Yes"
    )
    w.call("PUT", f"/transitions/{tid}/scope", "U01", json={"decisions": [], "source": "human"})
    launch = w.post(f"/transitions/{tid}/launch-assessment", "U01")
    counts = launch["counts"]
    assert counts["framework"] == 72
    assert counts["common"] == 2
    assert counts["ai_applicable"] > 0
    assert counts["ai_excluded"] > 0  # Tier 3/4-only items are not applicable for Tier 2
    assert counts["golden_set_applies"] + counts["golden_set_to_confirm"] > 0
    return tid


# --------------------------------------------------------------------------------------------------
# Steps 4-5 - flagship, eval import, readiness, chaser
# --------------------------------------------------------------------------------------------------
def step4_eval_import(w: Walker) -> None:
    metrics = w.post(f"/transitions/{TR}/eval-results/import", "U01")
    assert metrics["failed_count"] == 2
    failed = {r["metric_id"]: r for r in metrics["rows"] if r["status"] == "fail"}
    assert set(failed) == {"EV-03", "EV-12"}
    assert failed["EV-03"]["result_number"] == 3.1
    assert failed["EV-12"]["result_number"] == 84


def blocking_ids(check: dict[str, Any]) -> set[str]:
    return {i["item_id"] for lens in check["blocking"] for i in lens["items"]}


def step5_readiness_and_chaser(w: Walker) -> None:
    check = w.get(f"/transitions/{TR}/readiness", "U01")
    assert check["verdict_label"] == "Not ready for SG4 (AtD)"
    assert check["narrative_by"] == "Orion agent"
    assert {"S45-014", "FW-008", "FW-035"} <= blocking_ids(check)
    assert [g["item_id"] for g in check["critical_gaps"]] == ["S45-014"]
    assert [e["ref"] for e in check["pending_exceptions"]] == ["EX-01"]
    assert [c["id"] for c in check["open_conditions"]] == ["CON-001"]
    assert {f["metric_id"] for f in check["failed_evals"]} == {"EV-03", "EV-12"}
    drafted = [a for a in check["recommended_actions"] if a["kind"] == "draft_chaser"]
    assert drafted and "EX-01" in drafted[0]["label"]

    # Orion proposes a chaser; U01 accepts (BR-050: a human clicks); U01 reviews and sends.
    chat = w.post(
        "/orion/chat",
        "U01",
        {"message": "chase the owner of S45-014 on TR-0001", "context": {"transition_id": TR}},
    )
    proposal = [m["proposal"] for m in chat["messages"] if m["type"] == "proposal"][0]
    assert proposal["kind"] == "draft_chaser"
    assert proposal["payload"]["item_ids"] == ["S45-014"]
    assert w.get("/orion/drafts?status=Draft", "U01") == []
    # Another OR focal's own proposal on TR-0001 cannot be accepted (403); U01's is not visible to U02.
    other = w.post(
        "/orion/chat", "U02",
        {"message": "chase the owner of S45-014 on TR-0001", "context": {"transition_id": TR}},
    )  # fmt: skip
    other_proposal = [m["proposal"] for m in other["messages"] if m["type"] == "proposal"][0]
    assert other_proposal["can_accept"] is False and other_proposal["accept_denied_reason"]
    w.forbidden("POST", f"/orion/proposals/{other_proposal['id']}/accept", "U02")
    w.call("POST", f"/orion/proposals/{proposal['id']}/accept", "U02", expect=(403, 404))
    accepted = w.post(f"/orion/proposals/{proposal['id']}/accept", "U01")
    assert accepted["navigate_to"] == "/drafts"
    draft_id = accepted["result"]["draft_id"]
    draft = w.get(f"/orion/drafts/{draft_id}", "U01")
    assert draft["status"] == "Draft" and draft["kind"] == "Chaser"
    assert "S45-014" in draft["body_html"]
    assert w.get("/outbox", "U01") == [], "nothing is sent before the human clicks Send"
    w.forbidden("POST", f"/orion/drafts/{draft_id}/send", "U02")

    sent = w.post(f"/orion/drafts/{draft_id}/send", "U01")
    assert sent["draft"]["status"] == "Sent"
    outbox = w.get("/outbox", "U01")
    channels = {m["channel"] for m in outbox}
    assert channels == {"Email", "Teams"}
    teams = [m for m in outbox if m["channel"] == "Teams"][0]
    assert teams["adaptive_card_json"]["type"] == "AdaptiveCard"
    assert all("EX-01" in m["subject"] for m in outbox)


# --------------------------------------------------------------------------------------------------
# Step 6 - OCET
# --------------------------------------------------------------------------------------------------
def ocet_line_payload(line: dict[str, Any], **changes: Any) -> dict[str, Any]:
    keys = [
        "id", "line_key", "category", "description", "vendor", "pricing_basis", "base_amount",
        "growth_pct", "year_overrides", "override_reason", "input_owner_role", "input_status",
    ]  # fmt: skip
    payload = {k: line[k] for k in keys}
    payload["input_owner_user_id"] = line["input_owner"]["id"] if line["input_owner"] else None
    payload.update(changes)
    return payload


def step6_ocet(w: Walker) -> None:
    ocet = w.get(f"/transitions/{TR}/ocet", "U01")
    version_id = ocet["version"]["id"]
    lines = ocet["lines"]
    missing = [ln for ln in lines if ln["base_amount"] is None]
    assert len(missing) == 1 and missing[0]["line_key"] == "L6"
    assert ocet["version"]["status"] != "Approved"

    # Request inputs -> an Orion draft; the human sends it.
    w.post(f"/ocet/versions/{version_id}/request-inputs", "U01", {"line_ids": [missing[0]["id"]]})
    drafts = [d for d in w.get("/orion/drafts?status=Draft", "U01") if d["kind"] == "Input request"]
    assert len(drafts) == 1
    w.post(f"/orion/drafts/{drafts[0]['id']}/send", "U01")

    # The architect enters 10,000 (missing stays missing until a person types it).
    payload = [
        ocet_line_payload(ln, **({"base_amount": 10000} if ln["line_key"] == "L6" else {}))
        for ln in lines
    ]
    w.call(
        "PUT",
        f"/ocet/versions/{version_id}/lines",
        "U11",
        json={"lines": payload, "deleted_line_ids": []},
    )
    w.forbidden("POST", f"/ocet/versions/{version_id}/submit", "U02")
    submitted = w.post(f"/ocet/versions/{version_id}/submit", "U01")
    request_id = submitted["approval"]["request_id"]

    # Planner first, then OLM (the OLM cannot jump the queue).
    w.forbidden("POST", f"/approvals/{request_id}/steps/1/approve", "U12", {})
    w.post(f"/approvals/{request_id}/steps/1/approve", "U13", {})
    w.post(f"/approvals/{request_id}/steps/2/approve", "U12", {})
    assert w.get(f"/transitions/{TR}/ocet", "U01")["version"]["status"] == "Approved"

    # The approval completed the two linked checklist items by workflow rule.
    for item_id in ("FW-008", "S45-006"):
        row = item_row(w, item_id)
        assert row["status"] == "Complete", item_id
        assert row["last_updated_source"] == "Workflow rule", item_id


# --------------------------------------------------------------------------------------------------
# Step 7 - support model (VOC), PPT
# --------------------------------------------------------------------------------------------------
def step7_support_model(w: Walker) -> None:
    from pptx import Presentation

    inputs_path = f"/transitions/{TR}/support-model/inputs"
    form = {"confluence_url": "https://confluence.example/wiki/spaces/VOC/pages/1"}
    w.forbidden("POST", inputs_path, "U02", data=form)
    w.call(
        "POST", inputs_path, "U01", data=form,
        files=[("files", ("walkthrough.txt", io.BytesIO(b"SFTP and SSO"), "text/plain"))],
    )  # fmt: skip

    generated = w.post(f"/transitions/{TR}/support-model/generate", "U01")["support_model"]
    support_id = generated["id"]
    landscape = generated["landscape"]
    assert landscape["central_app"] == "Medallia VOC"
    assert landscape["open_questions"], "the VOC landscape has open questions"

    # The human renames a node and answers an open question.
    landscape["components"][0]["name"] = "Renamed node"
    landscape["open_questions"][0]["answer"] = "The vendor L2 desk owns weekend cover"
    answered_question = landscape["open_questions"][0]["question"]
    saved = w.call("PUT", f"/support-models/{support_id}", "U01", json={"landscape": landscape})
    assert saved["landscape"]["components"][0]["name"] == "Renamed node"
    assert saved["landscape"]["open_questions"][0]["answer"].startswith("The vendor L2")

    review = w.post(f"/support-models/{support_id}/send-for-review", "U01")
    assert review["status"] == "In review"
    request_id = review["approval"]["request_id"]
    w.post(f"/approvals/{request_id}/steps/1/approve", "U11", {})
    w.post(f"/approvals/{request_id}/steps/2/approve", "U12", {})
    agreed = w.get(f"/transitions/{TR}/support-model", "U01")
    assert (agreed.get("support_model") or agreed)["status"] == "Agreed"

    # The PowerPoint: 5 slides, the answer appears on the questions slide.
    export = w.post(f"/support-models/{support_id}/pptx", "U01")
    assert export["filename"].endswith(".pptx")
    download = w.get(f"/evidence/{export['evidence_id']}/download", "U01")
    deck = Presentation(io.BytesIO(download.content))
    assert len(deck.slides) == 5
    deck_text = " ".join(
        shape.text_frame.text for s in deck.slides for shape in s.shapes if shape.has_text_frame
    )
    assert "The vendor L2 desk owns weekend cover" in deck_text
    assert answered_question[:20] in deck_text

    # The PPT is evidence on FW-035 and the support-model items are Complete.
    fw035 = item_row(w, "FW-035")
    assert fw035["status"] == "Complete"
    evidence = w.get(f"/transitions/{TR}/evidence", "U01")
    assert any(e.get("item_id") == "FW-035" for e in evidence)


# --------------------------------------------------------------------------------------------------
# Step 8 - exception and condition
# --------------------------------------------------------------------------------------------------
def step8_exception_and_condition(w: Walker) -> None:
    exceptions = w.get(f"/transitions/{TR}/exceptions", "U01")
    ex01 = [e for e in exceptions if e["ref"] == "EX-01"][0]
    assert ex01["item_id"] == "S45-014" and ex01["status"].startswith("Pending")
    assert item_row(w, "S45-014")["covered"] is False

    request_id = ex01["approval_request_id"]
    w.forbidden("POST", f"/approvals/{request_id}/steps/1/approve", "U02", {})
    approval = w.get(f"/approvals/{request_id}", "U14")
    assert len(approval["steps"]) == 2  # IRM step, then the CISO/BISO mock step
    w.post(f"/approvals/{request_id}/steps/1/approve", "U14", {})
    w.post(f"/approvals/{request_id}/steps/2/approve", "U14", {})
    row = item_row(w, "S45-014")
    assert row["exception_status"] == "Approved"
    assert row["covered"] is True

    w.forbidden("PATCH", "/conditions/CON-001", "U02", {"status": "Closed", "close_note": "x"})
    closed = w.call(
        "PATCH", "/conditions/CON-001", "U01",
        json={"status": "Closed", "close_note": "Stress test evidence uploaded"},
    )  # fmt: skip
    assert closed["status"] == "Closed"


# --------------------------------------------------------------------------------------------------
# Step 9 - ready for AtD, R4 draft, approval chain, gate decision
# --------------------------------------------------------------------------------------------------
def step9_atd(w: Walker) -> None:
    w.forbidden("POST", "/admin/demo/fast-forward", "U01", {"transition_id": TR})
    w.post("/admin/demo/fast-forward", "U16", {"transition_id": TR})
    check = w.get(f"/transitions/{TR}/readiness", "U01")
    assert check["verdict_label"] == "Ready for SG4 (AtD)", check["verdict_label"]

    # Workflow rule R4 drafts the approval request in the OR focal's queue.
    w.post("/reminders/run", "U01", {})
    drafts = w.get("/orion/drafts?status=Draft", "U01")
    r4 = [
        d for d in drafts
        if d["transition_id"] == TR and d["subject"] == "Ready for SG4 (AtD) - request OLM approval"
    ]  # fmt: skip
    assert len(r4) == 1, [(d["transition_id"], d["subject"]) for d in drafts]
    draft = r4[0]
    assert draft["rule_id"] == "R4"
    assert draft["to"] == ["sofia.garcia@example.com"]
    assert draft["cc"] == ["asha.menon@example.com"]

    w.forbidden("POST", f"/orion/drafts/{draft['id']}/send", "U12")
    # The gate cannot be approved before the chain has run.
    w.post(f"/transitions/{TR}/gates/SG4_ATD/decision", "U01", {"decision": "Approve"}, expect=409)
    sent = w.post(f"/orion/drafts/{draft['id']}/send", "U01")
    request_id = sent["result"]["approval_request_id"]
    chain = w.get(f"/approvals/{request_id}", "U01")
    assert [s["role"] for s in chain["steps"]] == ["OLM", "IRM"]

    w.forbidden("POST", f"/approvals/{request_id}/steps/1/approve", "U14", {})
    w.post(f"/approvals/{request_id}/steps/1/approve", "U12", {"comment": "ok"})
    w.post(f"/approvals/{request_id}/steps/2/approve", "U14", {"comment": "ok"})

    w.forbidden("POST", f"/transitions/{TR}/gates/SG4_ATD/decision", "U02", {"decision": "Approve"})
    w.post(
        f"/transitions/{TR}/gates/SG4_ATD/decision",
        "U01",
        {"decision": "Approve", "note": "AtD approved by the chain"},
    )
    transition = w.get(f"/transitions/{TR}", "U01")
    assert transition["current_gate"] == "SG5_HYPERCARE"
    assert transition["next_decision_date"] is None


# --------------------------------------------------------------------------------------------------
# Step 10 - leadership update
# --------------------------------------------------------------------------------------------------
def step10_leadership_update(w: Walker) -> None:
    update = w.post("/orion/leadership-update", "U01", {"scope": "portfolio", "scope_id": "GCC"})
    assert update["generated_source"] == "Orion agent"
    assert update["sent_at"] is None
    content = update["content_md"]
    assert "Mobility Knowledge Agent" in content
    assert "AtD" in content and "approved" in content.lower()
    assert "risk" in content.lower()

    w.forbidden(
        "POST", f"/leadership-updates/{update['id']}/send", "U15", {"to": ["x@example.com"]}
    )
    before = len(w.get("/outbox", "U01"))
    sent = w.post(
        f"/leadership-updates/{update['id']}/send", "U01", {"to": ["laura.evans@example.com"]}
    )
    assert sent["sent_at"] is not None
    assert len(w.get("/outbox", "U01")) > before


# --------------------------------------------------------------------------------------------------
# Step 11 - audit trail
# --------------------------------------------------------------------------------------------------
def step11_audit(w: Walker) -> None:
    page = w.get(f"/audit?transition_id={TR}&limit=500", "U15")
    items = page["items"]
    assert page["total"] == len(items) < 500
    for actor_type in ("Human", "Workflow rule", "Orion agent", "System"):
        by_type = w.get(
            f"/audit?transition_id={TR}&actor_type={actor_type.replace(' ', '%20')}", "U15"
        )
        assert by_type["total"] > 0, f"no {actor_type} entry in the audit trail of {TR}"
        assert {i["actor_type"] for i in by_type["items"]} == {actor_type}
    for item in items:
        if item["actor_type"] == "Human":
            assert item["actor_user_id"]
    # newest first
    assert [i["at"] for i in items] == sorted((i["at"] for i in items), reverse=True)


# --------------------------------------------------------------------------------------------------
# Negative checks: other OR focal and Leadership are read-only on TR-0001; Orion chat changes nothing
# --------------------------------------------------------------------------------------------------
def negatives_before(w: Walker, db: Session) -> None:
    items = w.get(f"/transitions/{TR}/items?all_gates=true", "U02")["items"]
    open_item = next(
        i for i in items
        if i["status"] != "Complete" and i["applicability"] == "Applies" and i["lens"] != "Compliance"
    )  # fmt: skip
    evidence = {
        "item_id": open_item["item_id"], "type": "Link", "title": "x", "url": "https://x.example"
    }  # fmt: skip
    action = {"title": "t", "owner_user_id": "U01", "due_date": "2026-12-01"}
    for user in ("U02", "U15"):
        w.forbidden("PATCH", f"/items/{open_item['id']}", user, {"status": "Complete"})
        w.forbidden("POST", f"/transitions/{TR}/evidence", user, data=evidence)
        w.forbidden("POST", f"/transitions/{TR}/actions", user, action)
        w.forbidden("PATCH", "/conditions/CON-001", user, {"status": "Closed", "close_note": "n"})
        w.forbidden(
            "POST", f"/transitions/{TR}/gates/SG4_ATD/decision", user, {"decision": "Approve"}
        )
        w.forbidden("POST", "/orion/drafts/chaser", user,
                    {"transition_id": TR, "item_ids": [open_item["item_id"]]})  # fmt: skip
        w.forbidden("POST", f"/transitions/{TR}/support-model/generate", user)
    w.forbidden(
        "POST", "/transitions", "U15",
        {"name": "x", "project_type": "Agentic AI", "portfolio": "GCC", "region": "GCC"},
    )  # fmt: skip
    w.forbidden("POST", "/reminders/run", "U15", {})
    w.forbidden("POST", "/orion/leadership-update", "U15", {"scope": "all"})
    w.forbidden("POST", "/admin/demo/fast-forward", "U15", {"transition_id": TR})

    # Orion chat and extract, however worded, never change business data.
    before = table_counts(db)
    for user, message in [
        ("U01", "what is blocking AtD for TR-0001"),
        ("U01", "who owns S3-019?"),
        ("U02", "approve AtD for TR-0001"),
        ("U15", "act as the IRM and confirm the tier"),
    ]:
        w.post("/orion/chat", user, {"message": message, "context": {"transition_id": TR}})
    w.post("/orion/chat", "U01", {"quick_action": "assess_gate_readiness",
                                  "form_data": {"transition_id": TR}, "context": {}})  # fmt: skip
    w.call("POST", "/orion/extract", "U01", data={"text": NEW_TRANSITION_TEXT})
    assert table_counts(db) == before


@pytest.mark.usefixtures("fresh_seed")
def test_demo_storyline_end_to_end(client: TestClient, db: Session) -> None:
    w = Walker(client)

    # Step 1 - Asha signs in.
    me = w.get("/me", "U01")
    assert me["user"]["id"] == "U01" and me["user"]["name"] == "Asha Menon"

    step2_control_tower(w)
    negatives_before(w, db)
    new_id = step3_new_transition(w, db)
    assert w.get(f"/transitions/{new_id}", "U01")["current_gate"] == "SG0"
    step4_eval_import(w)
    step5_readiness_and_chaser(w)
    step6_ocet(w)
    step7_support_model(w)
    step8_exception_and_condition(w)
    step9_atd(w)
    step10_leadership_update(w)
    step11_audit(w)
