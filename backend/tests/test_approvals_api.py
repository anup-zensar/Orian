"""Approval chains (BR-041), exceptions (FR-035) and their notifications. Seed date 2026-11-16."""

from __future__ import annotations

from sqlalchemy import select

from app.domain.metrics import compute_metrics
from app.models import AuditEvent, Notification, Transition, TransitionItem

API = "/api/v1"


def _approve(client, headers, user, step, rid="APR-0001", comment=None):
    return client.post(
        f"{API}/approvals/{rid}/steps/{step}/approve",
        json={"comment": comment} if comment else {},
        headers=headers(user),
    )


def _outbox(client, headers, **params):
    res = client.get(f"{API}/outbox", params=params, headers=headers("U01"))
    assert res.status_code == 200, res.text
    return res.json()


def _compliance_item(db):
    rows = db.scalars(select(TransitionItem).where(TransitionItem.transition_id == "TR-0001")).all()
    return next(
        r.playbook_item_id
        for r in rows
        if r.playbook_item.lens == "Compliance" and r.playbook_item_id != "S45-014"
    )


def test_seeded_request_shape(client, headers):
    res = client.get(f"{API}/approvals/APR-0001", headers=headers("U14"))
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "EXCEPTION" and body["status"] == "Pending"
    assert body["current_step"] == 1 and body["can_act"] is True
    assert body["link"] == "/transitions/TR-0001/conditions"
    assert [s["status"] for s in body["steps"]] == ["Pending", "Waiting"]
    assert client.get(f"{API}/approvals/APR-9999", headers=headers("U14")).status_code == 404


def test_scopes(client, headers):
    mine = client.get(f"{API}/approvals", headers=headers("U14")).json()
    assert [r["id"] for r in mine] == ["APR-0001"]
    assert client.get(f"{API}/approvals", headers=headers("U12")).json() == []
    req = client.get(f"{API}/approvals", params={"scope": "requested"}, headers=headers("U01"))
    assert [r["id"] for r in req.json()] == ["APR-0001"]
    for user in ("U01", "U16"):
        res = client.get(f"{API}/approvals", params={"scope": "all"}, headers=headers(user))
        assert res.status_code == 200
    denied = client.get(f"{API}/approvals", params={"scope": "all"}, headers=headers("U10"))
    assert denied.status_code == 403
    assert "all approvals" in denied.json()["detail"]


def test_role_and_sequence_checks(client, headers, fresh_seed):
    res = _approve(client, headers, "U12", 1)  # OLM on an IRM step
    assert res.status_code == 403 and "IRM" in res.json()["reasons"][0]
    res = _approve(client, headers, "U14", 2)  # step 2 not active yet
    assert res.status_code == 409 and "sequence" in res.json()["reasons"][0]
    assert _approve(client, headers, "U14", 9).status_code == 404
    assert _approve(client, headers, "U14", 1).status_code == 200
    assert _approve(client, headers, "U14", 1).status_code == 409
    other = client.get(f"{API}/approvals/APR-0001", headers=headers("U12")).json()
    assert other["can_act"] is False and "CISO/BISO" in other["act_denied_reason"]
    assert _approve(client, headers, "U12", 2).status_code == 403


def test_ex01_storyline_step_8(client, headers, db, fresh_seed):
    first = _approve(client, headers, "U14", 1, comment="Looks fine")
    assert first.status_code == 200
    body = first.json()
    assert body["current_step"] == 2 and body["is_mock_step"] is True
    assert body["can_act"] is True
    assert body["steps"][0]["comment"] == "Looks fine"
    assert body["steps"][0]["decided_by"]["id"] == "U14"

    second = _approve(client, headers, "U14", 2)
    assert second.status_code == 200
    assert second.json()["status"] == "Approved" and second.json()["current_step"] is None

    exc = client.get(f"{API}/transitions/TR-0001/exceptions", headers=headers("U01")).json()
    assert exc[0]["ref"] == "EX-01" and exc[0]["status"] == "Approved"
    assert exc[0]["item_id"] == "S45-014"

    transition = db.get(Transition, "TR-0001")
    metrics = compute_metrics(db, [transition])[0]
    row = next(i for i in metrics.items if i.playbook_item_id == "S45-014")
    assert row.covered is True

    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "ExceptionRecord", AuditEvent.entity_id == "EX-01"
        )
    ).first()
    assert event is not None and event.actor_type == "Workflow rule"
    assert db.scalars(
        select(Notification).where(
            Notification.user_id == "U01", Notification.text.like("%approved%")
        )
    ).first()


def test_reject_requires_comment_and_cancels_rest(client, headers, fresh_seed):
    url = f"{API}/approvals/APR-0001/steps/1/reject"
    assert client.post(url, json={"comment": "   "}, headers=headers("U14")).status_code == 422
    assert client.post(url, json={}, headers=headers("U14")).status_code == 422
    assert client.post(url, json={"comment": "No"}, headers=headers("U12")).status_code == 403
    res = client.post(url, json={"comment": "Evidence missing"}, headers=headers("U14"))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "Rejected"
    assert [s["status"] for s in body["steps"]] == ["Rejected", "Cancelled"]
    exc = client.get(f"{API}/transitions/TR-0001/exceptions", headers=headers("U01")).json()
    assert exc[0]["status"] == "Rejected"
    notes = client.get(f"{API}/notifications", headers=headers("U01")).json()
    assert any("rejected" in n["text"] for n in notes["items"])
    assert _approve(client, headers, "U14", 2).status_code == 409


def test_notifications_and_outbox_on_step_change(client, headers, fresh_seed):
    before = _outbox(client, headers, transition_id="TR-0001")
    unread = client.get(f"{API}/notifications", headers=headers("U14")).json()["unread"]
    assert _approve(client, headers, "U14", 1).status_code == 200
    after = _outbox(client, headers, transition_id="TR-0001")
    new = after[: len(after) - len(before)]
    assert {m["channel"] for m in new} == {"Email", "Teams"}
    teams = next(m for m in new if m["channel"] == "Teams")
    actions = {a["title"]: a for a in teams["adaptive_card_json"]["actions"]}
    assert actions["Approve"]["data"] == {"request_id": "APR-0001", "step": 2}
    assert actions["Reject"]["verb"] == "reject"
    assert actions["Open in Orion"]["url"].endswith("/transitions/TR-0001/conditions")
    email = next(m for m in new if m["channel"] == "Email")
    assert "APR-0001" in email["related_ids"] and email["from_address"]
    notes = client.get(f"{API}/notifications", headers=headers("U14")).json()
    assert notes["unread"] == unread + 1
    first = notes["items"][0]
    assert first["link"] == "/approvals?request=APR-0001"
    other = client.post(f"{API}/notifications/{first['id']}/read", headers=headers("U01"))
    assert other.status_code == 404
    mine = client.post(f"{API}/notifications/{first['id']}/read", headers=headers("U14"))
    assert mine.status_code == 200
    assert client.post(f"{API}/notifications/read-all", headers=headers("U14")).status_code == 200
    assert client.get(f"{API}/notifications", headers=headers("U14")).json()["unread"] == 0


def test_create_exception_flow(client, headers, db, fresh_seed):
    item = _compliance_item(db)
    url = f"{API}/transitions/TR-0001/exceptions"
    body = {"item_id": item, "text": "Deviation needed"}
    assert client.post(url, json=body, headers=headers("U10")).status_code == 403
    unknown = {"item_id": "NOPE-1", "text": "x"}
    assert client.post(url, json=unknown, headers=headers("U01")).status_code == 422
    missing = client.post(
        f"{API}/transitions/TR-9999/exceptions", json=body, headers=headers("U01")
    )
    assert missing.status_code == 404
    res = client.post(url, json=body, headers=headers("U01"))
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["ref"] == "EX-02" and created["status"] == "Pending IRM"
    assert created["approval_request_id"] == "APR-0002"
    assert client.post(url, json=body, headers=headers("U01")).status_code == 409
    rows = db.scalars(select(TransitionItem).where(TransitionItem.transition_id == "TR-0001")).all()
    non_c = next(r.playbook_item_id for r in rows if r.playbook_item.lens != "Compliance")
    res = client.post(url, json={"item_id": non_c, "text": "x"}, headers=headers("U01"))
    assert res.status_code == 409
    assert "Compliance items only" in res.json()["detail"]
