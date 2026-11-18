"""Gates API: readiness check, stage reviews, request approval, decisions (AC-07 first half, AC-08)."""

from __future__ import annotations

from sqlalchemy import select

from app.domain import approvals
from app.models import (
    AuditEvent,
    Condition,
    GateReview,
    Transition,
    TransitionItem,
    User,
)
from app.rules.constants import DONE_STATUSES, NA_STATUSES, done_status_for

API = "/api/v1"
FLAGSHIP = "TR-0001"


def _readiness(client, headers, tid, gate=None, user="U01"):
    params = {"gate": gate} if gate else {}
    res = client.get(f"{API}/transitions/{tid}/readiness", params=params, headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _blocking_ids(data):
    return {i["item_id"]: i for g in data["blocking"] for i in g["items"]}


# --- AC-07 first half: flagship ------------------------------------------------------------------


def test_flagship_not_ready_for_atd_with_scripted_blockers(client, headers):
    data = _readiness(client, headers, FLAGSHIP)
    assert data["gate"] == "SG4_ATD" and data["gate_short"] == "AtD"
    assert data["verdict"] == "Not ready"
    assert data["verdict_label"] == "Not ready for AtD"
    blocking = _blocking_ids(data)
    # S45-014: red-team evidence non-compliant, critical, EX-01 pending
    assert blocking["S45-014"]["reason"] == "Non-compliant (Critical); exception EX-01 pending"
    assert [i["item_id"] for i in data["critical_gaps"]] == ["S45-014"]
    assert [(e["ref"], e["item_id"]) for e in data["pending_exceptions"]] == [("EX-01", "S45-014")]
    # FW-008 OCET, FW-035 support-model gap, S3-019 (CON-001)
    assert "OCET" in blocking["FW-008"]["reason"]
    assert "support model" in blocking["FW-035"]["reason"]
    assert "S3-019" in blocking
    assert [(c["id"], c["item_id"]) for c in data["open_conditions"]] == [("CON-001", "S3-019")]
    # failed eval metrics are Technical blockers
    assert (
        blocking["EV-03"]["reason"] == "Eval metric below target: Hallucination rate 3.1% vs ≤ 2%"
    )
    assert blocking["EV-12"]["reason"].startswith("Eval metric below target: Prompt-injection")
    technical = [g for g in data["blocking"] if g["lens"] == "Technical"][0]
    assert {"EV-03", "EV-12"} <= {i["item_id"] for i in technical["items"]}
    assert {e["metric_id"] for e in data["failed_evals"]} == {"EV-03", "EV-12"}
    assert data["ocet_status"] == "Inputs pending v2"
    assert data["support_model_status"] is None
    # carried items shown on the AtD page
    assert {c["item_id"] for c in data["carried_items"]} >= {"S3-019"}
    assert data["lenses"]["Business"] > 0
    assert any("EX-01" in w for w in data["warnings"])


def test_flagship_narrative_and_actions_are_orion_text(client, headers):
    data = _readiness(client, headers, FLAGSHIP)
    assert data["narrative_by"] == "Orion agent"
    narrative = data["narrative"]
    assert "Mobility Knowledge Agent is not ready for AtD." in narrative
    assert "block approval" in narrative and "S45-014" in narrative
    assert "CON-001" in narrative and "Recommended next step:" in narrative
    kinds = {a["kind"] for a in data["recommended_actions"]}
    assert {"open_ocet", "create_support_model", "draft_chaser", "create_action"} <= kinds
    assert "request_approval" not in kinds
    ocet = [a for a in data["recommended_actions"] if a["kind"] == "open_ocet"][0]
    assert ocet["href"] == f"/transitions/{FLAGSHIP}/ocet"
    assert all(a["key"] for a in data["recommended_actions"])
    # deterministic
    assert _readiness(client, headers, FLAGSHIP)["narrative"] == narrative


def test_flagship_decision_options_explain_why_disabled(client, headers):
    data = _readiness(client, headers, FLAGSHIP)
    options = {o["outcome"]: o for o in data["decision_options"]}
    assert [o["outcome"] for o in data["decision_options"]] == [
        "Approve",
        "Approve with conditions",
        "Return",
    ]
    for outcome in ("Approve", "Approve with conditions"):
        assert not options[outcome]["enabled"]
        assert options[outcome]["reasons"]
    assert "Approval has not been requested yet" in options["Approve"]["reasons"]
    assert options["Return"]["enabled"]
    assert data["can_request_approval"] is False
    assert data["request_denied_reason"].startswith("Not ready for AtD")


def test_readiness_permissions_for_options_and_validation(client, headers):
    # IRM cannot record decisions: options are disabled with the permission reason
    data = _readiness(client, headers, FLAGSHIP, user="U14")
    ret = [o for o in data["decision_options"] if o["outcome"] == "Return"][0]
    assert not ret["enabled"] and "OR focal" in ret["reasons"][0]
    assert client.get(f"{API}/transitions/TR-9999/readiness", headers=headers()).status_code == 404
    bad = client.get(f"{API}/transitions/{FLAGSHIP}/readiness?gate=NOPE", headers=headers())
    assert bad.status_code == 422
    assert client.get(f"{API}/transitions/{FLAGSHIP}/readiness").status_code == 401


def test_readiness_other_gate_is_informational(client, headers):
    data = _readiness(client, headers, FLAGSHIP, gate="SG3")
    assert data["gate_type"] == "stage_review"
    assert all(not o["enabled"] for o in data["decision_options"])
    assert any("not the current gate" in r for o in data["decision_options"] for r in o["reasons"])
    # SG3 does not evaluate Compliance items (A-12)
    assert all(g["lens"] != "Compliance" for g in data["blocking"])


def test_gates_overview_flagship(client, headers):
    res = client.get(f"{API}/transitions/{FLAGSHIP}/gates", headers=headers())
    assert res.status_code == 200
    data = res.json()
    assert data["current_gate"] == "SG4_ATD"
    assert [g["code"] for g in data["gates"]] == [
        "SG0",
        "SG2",
        "SG3",
        "SG4_ATD",
        "SG5_HYPERCARE",
        "SG6_ATO",
        "CLOSURE",
    ]
    assert [g["state"] for g in data["gates"]] == ["done"] * 3 + ["current"] + ["upcoming"] * 3
    sg3 = data["gates"][2]
    assert sg3["reviews"] and sg3["reviews"][0]["conditions_created"]
    assert data["gates"][3]["carried_items"] >= 1
    assert data["gates"][3]["approval"] is None


# --- stage reviews (AC-08) -----------------------------------------------------------------------


# OR focal of each seeded transition used below (per-transition access, BE#1)
FOCALS = {"TR-0001": "U01", "TR-0003": "U01", "TR-0015": "U08", "TR-0017": "U09", "TR-0018": "U04"}


def _review(client, headers, tid, gate, body, user=None):
    user = user or FOCALS.get(tid, "U01")
    return client.post(
        f"{API}/transitions/{tid}/gates/{gate}/review", json=body, headers=headers(user)
    )


def test_stage_review_sg3_hold_proceed_blocked_then_conditions_advance(client, headers, fresh_seed):
    tid = "TR-0018"  # seeded at SG3, Normal
    data = _readiness(client, headers, tid)
    assert data["gate"] == "SG3" and data["verdict"] == "Ready with conditions"
    items = sorted(_blocking_ids(data))
    assert items

    # permission: IRM cannot record a review
    assert (
        _review(client, headers, tid, "SG3", {"outcome": "Hold", "note": "x"}, "U14").status_code
        == 403
    )

    # Hold needs a note, then is always allowed and keeps the gate
    assert _review(client, headers, tid, "SG3", {"outcome": "Hold"}).status_code == 422
    hold = _review(client, headers, tid, "SG3", {"outcome": "Hold", "note": "Waiting for test run"})
    assert hold.status_code == 200, hold.text
    assert hold.json()["new_current_gate"] == "SG3"
    assert hold.json()["review"]["outcome"] == "Hold"

    # Proceed is blocked with reasons
    proceed = _review(client, headers, tid, "SG3", {"outcome": "Proceed"})
    assert proceed.status_code == 409
    assert any("not covered" in r for r in proceed.json()["reasons"])

    # Proceed with conditions: missing conditions -> 409, bad due gate -> 422
    owner = "U10"
    conds = [
        {"item_id": i, "owner_user_id": owner, "due_gate": "SG4_ATD", "text": f"Close {i}"}
        for i in items
    ]
    missing = _review(
        client, headers, tid, "SG3", {"outcome": "Proceed with conditions", "conditions": conds[:1]}
    )
    assert missing.status_code == 409
    assert any("without a condition" in r for r in missing.json()["reasons"])
    bad = _review(
        client,
        headers,
        tid,
        "SG3",
        {"outcome": "Proceed with conditions", "conditions": [{**conds[0], "due_gate": "SG3"}]},
    )
    assert bad.status_code == 422
    unknown = _review(
        client,
        headers,
        tid,
        "SG3",
        {"outcome": "Proceed with conditions", "conditions": [{**conds[0], "due_gate": "SG9"}]},
    )
    assert unknown.status_code == 422

    ok = _review(
        client, headers, tid, "SG3", {"outcome": "Proceed with conditions", "conditions": conds}
    )
    assert ok.status_code == 200, ok.text
    out = ok.json()
    assert out["new_current_gate"] == "SG4_ATD"
    assert len(out["conditions_created"]) == len(items)
    assert out["review"]["conditions_created"] == out["conditions_created"]

    after = client.get(f"{API}/transitions/{tid}", headers=headers()).json()
    assert after["current_gate"] == "SG4_ATD"
    overview = client.get(f"{API}/transitions/{tid}/gates", headers=headers()).json()
    sg3 = overview["gates"][2]
    assert [r["outcome"] for r in sg3["reviews"]] == ["Hold", "Proceed with conditions"]
    assert sg3["state"] == "done" and overview["gates"][3]["state"] == "current"
    assert overview["gates"][3]["carried_items"] == len(items)

    # the old gate is no longer the current gate
    again = _review(client, headers, tid, "SG3", {"outcome": "Hold", "note": "late"})
    assert again.status_code == 409

    # conditions are real, open, audited (Human) and cover the items afterwards
    from app.db import SessionLocal

    with SessionLocal() as db:
        rows = db.scalars(
            select(Condition).where(Condition.id.in_(out["conditions_created"]))
        ).all()
        assert {c.set_at_gate for c in rows} == {"SG3"} and {c.status for c in rows} == {"Open"}
    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.transition_id == tid, AuditEvent.entity.in_(("GateReview", "Condition"))
            )
        ).all()
        assert {e.actor_type for e in events} == {"Human"}
        assert {e.entity for e in events} == {"GateReview", "Condition"}


def test_stage_review_sg2_blocked_by_compliance_and_hold_allowed(client, headers, fresh_seed):
    tid = "TR-0015"  # seeded at SG2, Not ready (Compliance items open)
    data = _readiness(client, headers, tid)
    assert data["verdict"] == "Not ready"
    ids = _blocking_ids(data)
    comp = [i for i, v in ids.items() if v["lens"] == "Compliance"]
    assert comp
    options = {o["outcome"]: o for o in data["decision_options"]}
    assert options["Hold"]["enabled"] and not options["Proceed"]["enabled"]
    assert not options["Proceed with conditions"]["enabled"]
    conds = [
        {"item_id": i, "owner_user_id": "U10", "due_gate": "SG3", "text": "t"}
        for i, v in ids.items()
        if v["lens"] != "Compliance"
    ]
    res = _review(
        client, headers, tid, "SG2", {"outcome": "Proceed with conditions", "conditions": conds}
    )
    assert res.status_code == 409
    assert any(f"Compliance item {comp[0]} is open" in r for r in res.json()["reasons"])
    hold = _review(client, headers, tid, "SG2", {"outcome": "Hold", "note": "Compliance open"})
    assert hold.status_code == 200


def test_stage_review_wrong_gate_and_decision_gate(client, headers, fresh_seed):
    # TR-0018 is at SG3: SG2 is not current; AtD is not a stage review
    assert (
        _review(client, headers, "TR-0018", "SG2", {"outcome": "Hold", "note": "x"}).status_code
        == 409
    )
    assert (
        _review(client, headers, FLAGSHIP, "SG4_ATD", {"outcome": "Hold", "note": "x"}).status_code
        == 409
    )
    assert (
        _review(client, headers, "TR-9999", "SG3", {"outcome": "Hold", "note": "x"}).status_code
        == 404
    )
    assert (
        _review(client, headers, "TR-0018", "SG3", {"outcome": "Bogus", "note": "x"}).status_code
        == 422
    )


def test_sg0_ai_flavour_needs_confirmed_tier(client, headers, fresh_seed, db):
    t = db.get(Transition, "TR-0003")  # Agentic AI at SG3, tier confirmed
    t.current_gate = "SG0"
    db.commit()
    ok = _readiness(client, headers, "TR-0003")
    assert not any(
        "Tier must be confirmed" in r for g in ok["decision_options"] for r in g["reasons"]
    )
    t.tier_status = "Proposed"
    db.commit()
    data = _readiness(client, headers, "TR-0003")
    proceed = [o for o in data["decision_options"] if o["outcome"] == "Proceed"][0]
    assert "Tier must be confirmed by IRM before SG0 can proceed" in proceed["reasons"]
    res = _review(client, headers, "TR-0003", "SG0", {"outcome": "Proceed"})
    assert res.status_code == 409
    assert "Tier must be confirmed by IRM before SG0 can proceed" in res.json()["reasons"]


# --- request approval + decisions ----------------------------------------------------------------


def _make_atd_ready(db, tid="TR-0018"):
    t = db.get(Transition, tid)
    t.current_gate = "SG4_ATD"
    for row in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid)).all():
        if row.applicability == "Applies" and row.status not in DONE_STATUSES | NA_STATUSES:
            row.status = done_status_for(row.playbook_item.lens)
            row.gap_severity = None
    db.commit()
    return t


def test_request_approval_blocked_when_not_ready(client, headers):
    res = client.post(
        f"{API}/transitions/{FLAGSHIP}/gates/SG4_ATD/request-approval", json={}, headers=headers()
    )
    assert res.status_code == 409
    assert any("S45-014" in r for r in res.json()["reasons"])
    assert (
        client.post(
            f"{API}/transitions/{FLAGSHIP}/gates/SG4_ATD/request-approval",
            json={},
            headers=headers("U14"),
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{API}/transitions/{FLAGSHIP}/gates/SG3/request-approval", json={}, headers=headers()
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{API}/transitions/{FLAGSHIP}/gates/SG4_ATD/request-approval",
            json={"draft_id": 99999},
            headers=headers(),
        ).status_code
        == 404
    )


def test_atd_full_flow_ready_request_approve_and_return(client, headers, fresh_seed, db):
    tid = "TR-0018"
    t = _make_atd_ready(db, tid)
    olm, irm = t.olm_user_id, t.irm_user_id

    data = _readiness(client, headers, tid)
    assert data["verdict"] == "Ready" and data["verdict_label"] == "Ready for AtD"
    assert data["can_request_approval"] is True
    assert [a["kind"] for a in data["recommended_actions"]] == ["request_approval"]
    options = {o["outcome"]: o for o in data["decision_options"]}
    assert not options["Approve"]["enabled"]
    assert "Approval has not been requested yet" in options["Approve"]["reasons"]

    # decision before the chain is approved is blocked
    early = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/decision",
        json={"decision": "Approve"},
        headers=headers("U04"),
    )
    assert early.status_code == 409

    req = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/request-approval", json={}, headers=headers("U04")
    )
    assert req.status_code == 200, req.text
    chain = req.json()
    assert chain["status"] == "Pending" and [s["role"] for s in chain["steps"]] == ["OLM", "IRM"]

    # duplicate request is a 409
    dup = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/request-approval", json={}, headers=headers("U04")
    )
    assert dup.status_code == 409

    pending = _readiness(client, headers, tid)
    assert pending["approval"]["status"] == "Pending"
    assert pending["can_request_approval"] is False
    pend = {o["outcome"]: o for o in pending["decision_options"]}["Approve"]
    assert any("not approved yet" in r and "step pending" in r for r in pend["reasons"])

    # Return cancels the open chain (note required) and keeps the gate
    no_note = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/decision",
        json={"decision": "Return"},
        headers=headers("U04"),
    )
    assert no_note.status_code == 422
    back = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/decision",
        json={"decision": "Return", "note": "Need updated evidence"},
        headers=headers("U04"),
    )
    assert back.status_code == 200, back.text
    assert back.json()["new_current_gate"] == "SG4_ATD"
    db.expire_all()
    from app.models import ApprovalRequest

    assert db.get(ApprovalRequest, chain["request_id"]).status == "Cancelled"
    assert all(s.status == "Cancelled" for s in db.get(ApprovalRequest, chain["request_id"]).steps)

    # request again, approve both steps, then Approve advances to Hypercare
    req2 = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/request-approval", json={}, headers=headers("U04")
    )
    assert req2.status_code == 200
    request = db.get(ApprovalRequest, req2.json()["request_id"])
    approvals.approve_step(db, request=request, step=1, user=db.get(User, olm), comment=None)
    approvals.approve_step(db, request=request, step=2, user=db.get(User, irm), comment=None)
    db.commit()

    res = client.post(
        f"{API}/transitions/{tid}/gates/SG4_ATD/decision",
        json={"decision": "Approve", "note": "Go"},
        headers=headers("U04"),
    )
    assert res.status_code == 200, res.text
    assert res.json()["new_current_gate"] == "SG5_HYPERCARE"
    assert res.json()["review"]["outcome"] == "Approve"
    after = client.get(f"{API}/transitions/{tid}", headers=headers("U04")).json()
    assert after["current_gate"] == "SG5_HYPERCARE"
    reviews = db.scalars(
        select(GateReview).where(GateReview.transition_id == tid, GateReview.gate == "SG4_ATD")
    ).all()
    assert [r.outcome for r in reviews] == ["Return", "Approve"]


def test_decision_endpoint_validation(client, headers):
    base = f"{API}/transitions/{FLAGSHIP}/gates"
    assert (
        client.post(
            f"{base}/SG4_ATD/decision", json={"decision": "Approve"}, headers=headers("U14")
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{base}/SG3/decision", json={"decision": "Approve"}, headers=headers()
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{base}/SG4_ATD/decision", json={"decision": "Close"}, headers=headers()
        ).status_code
        == 422
    )
    res = client.post(f"{base}/SG4_ATD/decision", json={"decision": "Approve"}, headers=headers())
    assert res.status_code == 409
    text = "\n".join(res.json()["reasons"])
    assert "Approval has not been requested yet" in text
    assert "Critical gap S45-014" in text or "Compliance item S45-014" in text
    assert "Eval metric below target" in text
    assert (
        client.post(
            f"{base}/NOPE/decision", json={"decision": "Approve"}, headers=headers()
        ).status_code
        == 422
    )


def test_closure_close_requires_everything_done(client, headers, fresh_seed, db):
    tid = "TR-0018"
    t = db.get(Transition, tid)
    t.current_gate = "CLOSURE"
    db.commit()
    res = client.post(
        f"{API}/transitions/{tid}/gates/CLOSURE/decision",
        json={"decision": "Close"},
        headers=headers("U04"),
    )
    assert res.status_code == 409
    # finish every item, close conditions / actions / defects
    for row in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid)).all():
        if row.applicability == "Applies" and row.status not in DONE_STATUSES | {
            "N/A",
            "Not applicable",
        }:
            row.status = done_status_for(row.playbook_item.lens)
    from app.models import Action, HypercareDefect

    for c in db.scalars(select(Condition).where(Condition.transition_id == tid)).all():
        c.status = "Closed"
    for a in db.scalars(select(Action).where(Action.transition_id == tid)).all():
        a.status = "Done"
    for d in db.scalars(select(HypercareDefect).where(HypercareDefect.transition_id == tid)).all():
        d.status = "Resolved"
    db.commit()
    with_cond = client.post(
        f"{API}/transitions/{tid}/gates/CLOSURE/decision",
        json={
            "decision": "Close",
            "conditions": [
                {"item_id": "FW-001", "owner_user_id": "U01", "due_gate": "CLOSURE", "text": "x"}
            ],
        },
        headers=headers("U04"),
    )
    assert with_cond.status_code in (409, 422)
    ok = client.post(
        f"{API}/transitions/{tid}/gates/CLOSURE/decision",
        json={"decision": "Close"},
        headers=headers("U04"),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["transition_closed"] is True
    db.expire_all()
    assert db.get(Transition, tid).status == "Closed"
    again = client.post(
        f"{API}/transitions/{tid}/gates/CLOSURE/decision",
        json={"decision": "Close"},
        headers=headers("U04"),
    )
    assert again.status_code == 409
