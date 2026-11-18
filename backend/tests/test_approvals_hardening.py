"""Approval hardening: closed protection, mock step, approvers, separation of duties, exception status
(BE#7, BE#12, EX-status). Seed EX-01 (APR-0001): step 1 IRM U14, step 2 CISO/BISO mock.
"""

from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.models import AuditEvent, Notification, Transition, TransitionItem, User

API = "/api/v1"


def _make_user(db, user_id: str, role: str) -> None:
    db.add(
        User(id=user_id, name=f"Test {role} {user_id}", email=f"{user_id}@test.example", role=role)
    )
    db.commit()


def _compliance_item(db, tid="TR-0001"):
    rows = db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid)).all()
    return next(
        r.playbook_item_id
        for r in rows
        if r.playbook_item.lens == "Compliance" and r.playbook_item_id != "S45-014"
    )


def _approve(client, headers, user, step, rid="APR-0001"):
    return client.post(
        f"{API}/approvals/{rid}/steps/{step}/approve", json={}, headers=headers(user)
    )


def _exceptions(client, headers, tid="TR-0001"):
    return client.get(f"{API}/transitions/{tid}/exceptions", headers=headers("U01")).json()


# --- EX-status ----------------------------------------------------------------------------------


def test_exception_status_follows_the_current_step(client, headers, db, fresh_seed):
    assert _exceptions(client, headers)[0]["status"] == "Pending IRM"  # seed EX-01
    created = client.post(
        f"{API}/transitions/TR-0001/exceptions",
        json={"item_id": _compliance_item(db), "text": "Deviation"},
        headers=headers("U01"),
    ).json()
    assert created["status"] == "Pending IRM"
    assert _approve(client, headers, "U14", 1).status_code == 200
    assert _exceptions(client, headers)[0]["status"] == "Pending CISO/BISO"
    assert _approve(client, headers, "U14", 2).status_code == 200
    assert _exceptions(client, headers)[0]["status"] == "Approved"
    ref = client.get(f"{API}/reference").json()
    assert ref["enums"]["exception_statuses"] == [
        "Draft",
        "Pending IRM",
        "Pending CISO/BISO",
        "Approved",
        "Rejected",
    ]


# --- BE#7: closed subject -----------------------------------------------------------------------


def test_closed_transition_blocks_approve_and_reject(client, headers, db, fresh_seed):
    db.get(Transition, "TR-0001").status = "Closed"
    db.commit()
    assert _approve(client, headers, "U14", 1).status_code == 409
    res = client.post(
        f"{API}/approvals/APR-0001/steps/1/reject", json={"comment": "No"}, headers=headers("U14")
    )
    assert res.status_code == 409 and "closed" in str(res.json()).lower()
    wrong_user = _approve(client, headers, "U12", 1)
    assert wrong_user.status_code == 403  # permission is evaluated before the closed check


# --- mock CISO/BISO step ------------------------------------------------------------------------


def test_mock_step_only_by_the_assigned_irm_in_demo_mode(
    client, headers, db, fresh_seed, monkeypatch
):
    _make_user(db, "U92", "IRM")  # an IRM who is not assigned to TR-0001
    assert _approve(client, headers, "U14", 1).status_code == 200
    other = client.get(f"{API}/approvals/APR-0001", headers=headers("U92")).json()
    assert other["can_act"] is False and "Fatima Khan" in other["act_denied_reason"]
    assert _approve(client, headers, "U92", 2).status_code == 403
    assert _approve(client, headers, "U16", 2).status_code == 403  # no Admin override
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert _approve(client, headers, "U14", 2).status_code == 403
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    assert _approve(client, headers, "U14", 2).status_code == 200


# --- approvers (BE#12) --------------------------------------------------------------------------


def test_approvers_override_is_validated_against_the_step_role(client, headers, db, fresh_seed):
    _make_user(db, "U93", "IRM")
    url = f"{API}/transitions/TR-0001/exceptions"
    item = _compliance_item(db)
    wrong = client.post(
        url, json={"item_id": item, "text": "x", "approvers": {"1": "U12"}}, headers=headers("U01")
    )
    assert wrong.status_code == 422 and "IRM" in str(wrong.json())
    mock = client.post(
        url, json={"item_id": item, "text": "x", "approvers": {"2": "U14"}}, headers=headers("U01")
    )
    assert mock.status_code == 422
    unknown = client.post(
        url, json={"item_id": item, "text": "x", "approvers": {"1": "U99"}}, headers=headers("U01")
    )
    assert unknown.status_code == 422
    ok = client.post(
        url, json={"item_id": item, "text": "x", "approvers": {"1": "U93"}}, headers=headers("U01")
    )
    assert ok.status_code == 201, ok.text
    request = client.get(
        f"{API}/approvals/{ok.json()['approval_request_id']}", headers=headers("U93")
    ).json()
    assert request["steps"][0]["approver"]["id"] == "U93" and request["can_act"] is True
    assert (
        client.get(f"{API}/approvals/{request['id']}", headers=headers("U14")).json()["can_act"]
        is False
    )


def test_step_without_a_resolved_approver_notifies_every_user_of_the_role(
    client, headers, db, fresh_seed
):
    _make_user(db, "U94", "IRM")
    db.get(Transition, "TR-0001").irm_user_id = None
    db.commit()
    res = client.post(
        f"{API}/transitions/TR-0001/exceptions",
        json={"item_id": _compliance_item(db), "text": "x"},
        headers=headers("U01"),
    )
    assert res.status_code == 201, res.text
    request_id = res.json()["approval_request_id"]
    for user_id in ("U14", "U94"):
        found = db.scalars(
            select(Notification).where(
                Notification.user_id == user_id, Notification.link.like(f"%{request_id}")
            )
        ).all()
        assert found, user_id
    assert (
        client.get(f"{API}/approvals/{request_id}", headers=headers("U94")).json()["can_act"]
        is True
    )


# --- separation of duties (BE#12) ---------------------------------------------------------------


def test_irm_requesting_an_exception_for_self_approval(
    client, headers, db, fresh_seed, monkeypatch
):
    url = f"{API}/transitions/TR-0001/exceptions"
    body = {"item_id": _compliance_item(db), "text": "IRM raised"}
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    blocked = client.post(url, json=body, headers=headers("U14"))
    assert blocked.status_code == 409
    assert "cannot approve their own request" in str(blocked.json())
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    created = client.post(url, json=body, headers=headers("U14"))
    assert created.status_code == 201, created.text
    rid = created.json()["approval_request_id"]
    assert _approve(client, headers, "U14", 1, rid).status_code == 200
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "ApprovalStep", AuditEvent.entity_id == f"{rid}/1"
        )
    ).one()
    assert "self-approved" in event.note


def test_non_demo_mode_refuses_self_approval_at_decision_time(
    client, headers, db, fresh_seed, monkeypatch
):
    # a request created by U14 in demo mode cannot be approved by U14 once DEMO_MODE is off
    created = client.post(
        f"{API}/transitions/TR-0001/exceptions",
        json={"item_id": _compliance_item(db), "text": "IRM raised"},
        headers=headers("U14"),
    )
    rid = created.json()["approval_request_id"]
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    res = _approve(client, headers, "U14", 1, rid)
    assert res.status_code == 409
