"""Admin has no workflow override; admin chain edits do not touch open requests; stuck-approval
cancel (BE#1 / M9-ADMIN)."""

from __future__ import annotations

from sqlalchemy import select

from app.models import ApprovalRequest, AuditEvent
from tests.test_ocet_api import _save, _view, _with_l6

API = "/api/v1"
ADMIN = "U16"


def _submit_ocet(client, headers) -> str:
    body = _view(client, headers)
    vid = body["version"]["id"]
    assert _save(client, headers, "U11", vid, _with_l6(body, 10_000)).status_code == 200
    sub = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01"))
    assert sub.status_code == 200, sub.text
    return sub.json()["approval"]["request_id"]


def test_admin_cannot_decide_review_or_edit_items(client, headers, fresh_seed):
    h = headers(ADMIN)
    dec = client.post(
        f"{API}/transitions/TR-0001/gates/SG4_ATD/decision", json={"decision": "Approve"}, headers=h
    )
    assert dec.status_code == 403
    rev = client.post(f"{API}/transitions/TR-0001/gates/SG4_ATD/review", json={}, headers=h)
    assert rev.status_code == 403


def test_admin_cannot_edit_items(client, headers, fresh_seed):
    h = headers(ADMIN)
    items = client.get(f"{API}/transitions/TR-0001/items", headers=h).json()["items"]
    item = next(
        i
        for i in items
        if i["lens"] != "Compliance"
        and i["status"] != "Complete"
        and i["applicability"] == "Applies"
    )
    patch = client.patch(f"{API}/items/{item['id']}", json={"status": "Complete"}, headers=h)
    assert patch.status_code == 403


def test_non_admin_403_on_admin_writes(client, headers, fresh_seed):
    for user in ("U01", "U10", "U14", "U15"):
        h = headers(user)
        put = client.put(f"{API}/admin/approval-chains", json={"chains": []}, headers=h)
        assert put.status_code == 403
        cancel = client.post(
            f"{API}/admin/approvals/APR-0001/cancel", json={"reason": "stuck"}, headers=h
        )
        assert cancel.status_code == 403
        ff = client.post(
            f"{API}/admin/demo/fast-forward", json={"transition_id": "TR-0001"}, headers=h
        )
        assert ff.status_code == 403


def test_fast_forward_still_works_for_admin(client, headers, fresh_seed):
    res = client.post(
        f"{API}/admin/demo/fast-forward", json={"transition_id": "TR-0001"}, headers=headers(ADMIN)
    )
    assert res.status_code == 200, res.text


def test_chain_edit_does_not_change_open_request(client, headers, fresh_seed):
    rid = _submit_ocet(client, headers)
    before = client.get(f"{API}/approvals/{rid}", headers=headers("U13")).json()
    assert len(before["steps"]) == 2
    chain = {"type": "OCET", "steps": [{"step": 1, "role": "PLANNER", "label": "Planner"}]}
    res = client.put(
        f"{API}/admin/approval-chains", json={"chains": [chain]}, headers=headers(ADMIN)
    )
    assert res.status_code == 200, res.text
    after = client.get(f"{API}/approvals/{rid}", headers=headers("U13")).json()
    assert [s["role"] for s in after["steps"]] == [s["role"] for s in before["steps"]]


def test_cancel_stuck_approval(client, headers, db, fresh_seed):
    rid = _submit_ocet(client, headers)
    url = f"{API}/admin/approvals/{rid}/cancel"
    assert client.post(url, json={}, headers=headers(ADMIN)).status_code == 422
    assert client.post(url, json={"reason": "  "}, headers=headers(ADMIN)).status_code == 422
    missing = client.post(
        f"{API}/admin/approvals/APR-9999/cancel", json={"reason": "gone"}, headers=headers(ADMIN)
    )
    assert missing.status_code == 404
    res = client.post(url, json={"reason": "Planner left the company"}, headers=headers(ADMIN))
    assert res.status_code == 200, res.text
    assert res.json() == {"request_id": rid, "status": "Cancelled"}
    assert db.get(ApprovalRequest, rid).status == "Cancelled"
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "ApprovalRequest",
            AuditEvent.entity_id == rid,
            AuditEvent.action == "cancelled",
        )
    ).first()
    assert event is not None and "Planner left" in event.note and event.actor_type == "Human"
    assert client.post(url, json={"reason": "again"}, headers=headers(ADMIN)).status_code == 409
