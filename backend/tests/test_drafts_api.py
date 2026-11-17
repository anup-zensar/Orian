"""Orion drafts queue (BR-050, FR-071) and the chaser template (spec 10.1)."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditEvent, OrionDraft, Transition
from app.services.mock.ai_messages import draft_message

API = "/api/v1"


def _chaser(client, headers, user="U01", items=("S45-014",)):
    return client.post(
        f"{API}/orion/drafts/chaser",
        json={"transition_id": "TR-0001", "item_ids": list(items)},
        headers=headers(user),
    )


def _patch(client, headers, did, **fields):
    body = {"to": ["a@example.com"], "cc": [], "subject": "s", "body_html": "<p>b</p>", **fields}
    return client.patch(f"{API}/orion/drafts/{did}", json=body, headers=headers("U01"))


def test_draft_message_chaser_template():
    ctx = {
        "transition_id": "TR-0001",
        "transition_name": "Mobility Knowledge Agent",
        "gate_short": "AtD",
        "days": 21,
        "or_focal_name": "Asha",
        "items": [{"id": "S45-014", "title": "Red-team <evidence>"}],
    }
    out = draft_message("Chaser", ctx)
    assert out["subject"] == (
        "Action needed: Red-team <evidence> for Mobility Knowledge Agent (AtD in 21 days)"
    )
    assert "Orion, on behalf of Asha" in out["body_html"]
    assert "/transitions/TR-0001/assessment?item=S45-014" in out["body_html"]
    assert "<evidence>" not in out["body_html"]
    assert draft_message("chaser", ctx) == out
    for kind in ("Reminder", "Input request", "Approval request", "Leadership update"):
        assert draft_message(kind, ctx)["subject"]


def test_chaser_requires_permission_and_valid_items(client, headers, fresh_seed):
    assert _chaser(client, headers, "U10").status_code == 403
    assert _chaser(client, headers, items=("NOPE",)).status_code == 422
    res = client.post(
        f"{API}/orion/drafts/chaser",
        json={"transition_id": "TR-9999", "item_ids": ["S45-014"]},
        headers=headers("U01"),
    )
    assert res.status_code == 404


def test_chaser_edit_send_flow(client, headers, db, fresh_seed):
    res = _chaser(client, headers)
    assert res.status_code == 201, res.text
    draft = res.json()
    assert draft["status"] == "Draft" and draft["kind"] == "Chaser"
    assert draft["created_source"] == "Orion agent" and draft["source_label"] == "Orion agent"
    assert draft["related_ids"] == ["TR-0001", "S45-014"]
    assert draft["subject"].startswith("Action needed:") and draft["to"]
    emails = client.get(f"{API}/outbox", params={"channel": "Email"}, headers=headers("U01"))
    assert emails.json() == []  # drafting sends nothing

    did = draft["id"]
    assert _patch(client, headers, did, to=[]).status_code == 422
    assert _patch(client, headers, did, to=["not-an-address"]).status_code == 422
    edited = _patch(
        client,
        headers,
        did,
        to=["a.owner@example.com"],
        subject="Edited subject",
        body_html='<p>Edited</p><script>alert(1)</script><a href="javascript:x">l</a>',
    )
    assert edited.status_code == 200
    html = edited.json()["body_html"]
    assert "script" not in html and "javascript" not in html

    assert client.post(f"{API}/orion/drafts/{did}/send", headers=headers("U10")).status_code == 403
    sent = client.post(f"{API}/orion/drafts/{did}/send", headers=headers("U01"))
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["draft"]["status"] == "Sent" and body["draft"]["sent_by"]["id"] == "U01"
    assert body["draft"]["sent_at"]
    emails = client.get(f"{API}/outbox", params={"channel": "Email"}, headers=headers("U01")).json()
    assert len(emails) == 1
    assert emails[0]["subject"] == "Edited subject" and emails[0]["to"] == ["a.owner@example.com"]
    assert emails[0]["draft_id"] == did and emails[0]["id"] in body["outbox_message_ids"]
    assert client.post(f"{API}/orion/drafts/{did}/send", headers=headers("U01")).status_code == 409
    assert _patch(client, headers, did).status_code == 409

    event = db.scalars(
        select(AuditEvent).where(AuditEvent.entity == "OrionDraft", AuditEvent.action == "sent")
    ).one()
    assert event.actor_type == "Human" and event.note == f"Sent Orion draft {did}"


def test_discard_and_list_filters(client, headers, db, fresh_seed):
    a = _chaser(client, headers).json()["id"]
    b = _chaser(client, headers).json()["id"]
    assert client.post(f"{API}/orion/drafts/{a}/discard", headers=headers("U10")).status_code == 403
    res = client.post(f"{API}/orion/drafts/{a}/discard", headers=headers("U01"))
    assert res.status_code == 200 and res.json()["status"] == "Discarded"
    assert client.post(f"{API}/orion/drafts/{a}/discard", headers=headers("U01")).status_code == 409
    assert client.post(f"{API}/orion/drafts/{a}/send", headers=headers("U01")).status_code == 409
    assert db.get(OrionDraft, a).status == "Discarded"
    drafts = client.get(
        f"{API}/orion/drafts", params={"status": "Draft"}, headers=headers("U10")
    ).json()
    assert [d["id"] for d in drafts] == [b]
    assert client.get(f"{API}/orion/drafts/{b}", headers=headers("U10")).status_code == 200
    assert client.get(f"{API}/orion/drafts/99999", headers=headers("U10")).status_code == 404
    reminders = client.get(
        f"{API}/orion/drafts", params={"kind": "Reminder"}, headers=headers("U01")
    )
    assert reminders.json() == []


def test_send_executes_request_approval_action(client, headers, db, fresh_seed, monkeypatch):
    from app.domain import approvals, drafts, gate_actions

    calls = []

    def fake(db_, *, transition, gate, user, note="", via_draft_id=None):
        calls.append((gate, note, via_draft_id))
        return approvals.create_approval_request(
            db_,
            type="AtD",
            transition=transition,
            created_by=user,
            created_source="Human",
            gate=gate,
            subject_label="Ready",
        )

    monkeypatch.setattr(gate_actions, "request_gate_approval", fake)
    draft = drafts.create_draft(
        db,
        kind="Approval request",
        transition=db.get(Transition, "TR-0001"),
        to=["olm@example.com"],
        cc=[],
        subject="AtD request",
        body_html="<p>Please approve</p>",
        created_source="Orion agent",
        action={"type": "request_approval", "gate": "SG4_ATD"},
        related_ids=["TR-0001"],
    )
    db.commit()
    res = client.post(f"{API}/orion/drafts/{draft.id}/send", headers=headers("U01"))
    assert res.status_code == 200, res.text
    assert res.json()["result"]["approval_request_id"] == "APR-0002"
    assert calls == [("SG4_ATD", f"Sent Orion draft {draft.id}", draft.id)]
    req = client.get(f"{API}/approvals/APR-0002", headers=headers("U12")).json()
    assert req["can_act"] is True and req["link"] == "/transitions/TR-0001/gates"
