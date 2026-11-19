"""Orion proposals (BR-050): stored cards that only a permitted human executes."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.domain.proposals import create_proposal
from app.models import (
    Action,
    AuditEvent,
    Evidence,
    ExceptionRecord,
    OcetLine,
    OrionDraft,
    OrionProposal,
    Transition,
    TransitionItem,
)

API = "/api/v1"
FOCAL = "U01"  # OR focal of TR-0001
OTHER_FOCAL = "U02"
IRM = "U14"


def _make(db, kind, payload, transition_id="TR-0001", title="Test proposal"):
    row = create_proposal(db, kind=kind, title=title, payload=payload, transition_id=transition_id)
    db.commit()
    return row


def _accept(client, headers, pid, user=FOCAL):
    return client.post(f"{API}/orion/proposals/{pid}/accept", headers=headers(user))


def _action_payload(**over):
    payload = {
        "title": "Finish the DPIA",
        "item_ids": ["S3-019"],
        "owner_user_id": "U13",
        "due_date": "2026-11-20",
        "priority": "Medium",
    }
    return payload | over


def _audit(db, entity_id, action="accepted"):
    return db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "OrionProposal",
            AuditEvent.entity_id == str(entity_id),
            AuditEvent.action == action,
        )
    ).all()


# --- create_proposal -------------------------------------------------------------------------
def test_create_dedupes_open_proposals(db, fresh_seed):
    first = _make(db, "create_action", _action_payload())
    again = _make(db, "create_action", _action_payload())
    other = _make(db, "create_action", _action_payload(title="Another"))
    assert first.id == again.id
    assert other.id != first.id


def test_create_validates_keys_and_ids(db, fresh_seed):
    with pytest.raises(ValueError):
        create_proposal(
            db, kind="create_action", title="x", payload={"title": "x"}, transition_id="TR-0001"
        )
    with pytest.raises(ValueError):
        create_proposal(
            db, kind="create_action", title="x", payload=_action_payload(), transition_id=None
        )
    with pytest.raises(ValueError):
        create_proposal(
            db, kind="create_action", title="x", payload=_action_payload(), transition_id="TR-9999"
        )
    with pytest.raises(ValueError):
        create_proposal(
            db,
            kind="create_action",
            title="x",
            payload=_action_payload(owner_user_id="U99"),
            transition_id="TR-0001",
        )
    with pytest.raises(ValueError):
        create_proposal(
            db, kind="request_approval", title="x", payload={"gate": "SG3"}, transition_id="TR-0001"
        )


def test_payload_whitelist_blocks_smuggled_changes(db, fresh_seed):
    for changes in (
        {"risk_tier": 1},
        {"current_gate": "SG6_ATO"},
        {"status": "Closed"},
        {"tier": 1},
    ):
        with pytest.raises(ValueError):
            create_proposal(
                db,
                kind="update_transition",
                title="x",
                payload={"transition_id": "TR-0001", "changes": changes},
                transition_id="TR-0001",
            )
    for changes in (
        {"design_effectiveness": "Yes"},
        {"applicability": "Not applicable"},
        {"na_reason": "x"},
    ):
        with pytest.raises(ValueError):
            create_proposal(
                db,
                kind="update_item",
                title="x",
                payload={"transition_id": "TR-0001", "item_id": "S3-019", "changes": changes},
                transition_id="TR-0001",
            )
    with pytest.raises(ValueError):  # a Compliance status is never proposed
        create_proposal(
            db,
            kind="update_item",
            title="x",
            payload={
                "transition_id": "TR-0001",
                "item_id": "S45-014",
                "changes": {"status": "Compliant"},
            },
            transition_id="TR-0001",
        )
    with pytest.raises(ValueError):  # unknown payload key
        create_proposal(
            db,
            kind="update_item",
            title="x",
            payload={
                "transition_id": "TR-0001",
                "item_id": "S3-019",
                "changes": {"note": "x"},
                "tier": 1,
            },
            transition_id="TR-0001",
        )
    with pytest.raises(ValueError):
        create_proposal(
            db,
            kind="create_transition",
            title="x",
            payload={
                "prefill": {"risk_tier": 1},
                "fields": [],
                "missing_fields": [],
                "ambiguous_fields": [],
                "source": "chat",
            },
            transition_id=None,
        )


# --- accept: each kind runs the normal domain operation as the human --------------------------
def test_accept_create_action(client, db, headers, fresh_seed):
    row = _make(db, "create_action", _action_payload())
    res = _accept(client, headers, row.id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["proposal"]["status"] == "Accepted"
    assert body["proposal"]["accepted_by"]["id"] == FOCAL
    action = db.get(Action, body["result"]["action_id"])
    assert action.owner_user_id == "U13" and action.origin == "Human"
    assert body["navigate_to"].startswith("/transitions/TR-0001")
    events = _audit(db, row.id)
    assert len(events) == 1
    assert events[0].actor_type == "Human" and events[0].actor_user_id == FOCAL
    assert events[0].note == f"Accepted Orion proposal {row.id}"
    created = db.scalars(
        select(AuditEvent).where(AuditEvent.entity == "Action", AuditEvent.action == "created")
    ).all()
    assert any(f"Accepted Orion proposal {row.id}" in e.note for e in created)


def test_accept_twice_is_409_and_unknown_is_404(client, db, headers, fresh_seed):
    row = _make(db, "create_action", _action_payload())
    assert _accept(client, headers, row.id).status_code == 200
    again = _accept(client, headers, row.id)
    assert again.status_code == 409
    assert (
        db.scalar(select(func.count()).select_from(Action).where(Action.title == "Finish the DPIA"))
        == 1
    )
    assert _accept(client, headers, 99999).status_code == 404
    assert client.post(f"{API}/orion/proposals/0/accept", headers=headers(FOCAL)).status_code == 422


def test_accept_without_permission_is_403_and_stays_open(client, db, headers, fresh_seed):
    row = _make(db, "create_action", _action_payload())
    for user in (OTHER_FOCAL, "U15", "U13"):  # focal of another transition, Leadership, Planner
        res = _accept(client, headers, row.id, user)
        assert res.status_code == 403, (user, res.text)
    db.expire_all()
    assert db.get(OrionProposal, row.id).status == "Open"
    assert (
        db.scalar(select(func.count()).select_from(Action).where(Action.title == "Finish the DPIA"))
        == 0
    )
    assert not _audit(db, row.id)
    listed = client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U15")).json()
    assert listed["can_accept"] is False and listed["accept_denied_reason"]
    mine = client.get(f"{API}/orion/proposals/{row.id}", headers=headers(FOCAL)).json()
    assert mine["can_accept"] is True and mine["accept_denied_reason"] is None


def test_dismiss_same_right_and_409(client, db, headers, fresh_seed):
    row = _make(db, "create_action", _action_payload())
    assert (
        client.post(f"{API}/orion/proposals/{row.id}/dismiss", headers=headers("U15")).status_code
        == 403
    )
    res = client.post(f"{API}/orion/proposals/{row.id}/dismiss", headers=headers(FOCAL))
    assert res.status_code == 200 and res.json()["status"] == "Dismissed"
    assert res.json()["accept_denied_reason"] == "Already dismissed"
    assert (
        client.post(f"{API}/orion/proposals/{row.id}/dismiss", headers=headers(FOCAL)).status_code
        == 409
    )
    assert _accept(client, headers, row.id).status_code == 409
    event = _audit(db, row.id, "dismissed")[0]
    assert event.actor_type == "Human" and event.note == f"Dismissed Orion proposal {row.id}"


def test_accept_draft_chaser_only_drafts(client, db, headers, fresh_seed):
    row = _make(db, "draft_chaser", {"item_ids": ["S3-019"]})
    res = _accept(client, headers, row.id)
    assert res.status_code == 200, res.text
    draft = db.get(OrionDraft, res.json()["result"]["draft_id"])
    assert draft.status == "Draft" and draft.sent_at is None
    assert res.json()["navigate_to"] == "/drafts"
    again = _make(db, "draft_chaser", {"item_ids": ["FW-008"]})
    assert _accept(client, headers, again.id, IRM).status_code == 403


def test_accept_request_approval_creates_draft_or_explains(client, db, headers, fresh_seed):
    row = _make(db, "request_approval", {"gate": "SG4_ATD"})
    res = _accept(client, headers, row.id)
    # TR-0001 is not ready for AtD in the seed: the normal operation refuses (409), nothing changes
    assert res.status_code == 409, res.text
    db.expire_all()
    assert db.get(OrionProposal, row.id).status == "Open"
    assert (
        db.scalar(
            select(func.count())
            .select_from(OrionDraft)
            .where(OrionDraft.kind == "Approval request")
        )
        == 0
    )


def test_accept_request_inputs(client, db, headers, fresh_seed):
    line = db.get(OcetLine, 11)
    line.input_status = "Missing"
    db.commit()
    row = _make(db, "request_inputs", {"version_id": line.version_id, "line_ids": [line.id]})
    res = _accept(client, headers, row.id)
    assert res.status_code == 200, res.text
    assert db.get(OrionDraft, res.json()["result"]["draft_id"]).kind == "Input request"
    db.expire_all()
    assert db.get(OcetLine, 11).input_status == "Requested"


def test_accept_request_exception(client, db, headers, fresh_seed):
    row = _make(db, "request_exception", {"item_id": "FW-016", "text": "Vendor cannot meet it"})
    assert _accept(client, headers, row.id, FOCAL).status_code == 200
    ex = db.scalars(select(ExceptionRecord).order_by(ExceptionRecord.ref.desc())).first()
    assert ex.text == "Vendor cannot meet it" and ex.requested_by == FOCAL
    # a Business item is refused by the normal operation
    bad = _make(db, "request_exception", {"item_id": "S3-019", "text": "x"})
    assert _accept(client, headers, bad.id, FOCAL).status_code == 409


def test_accept_applicability(client, db, headers, fresh_seed):
    from app.models import PlaybookItem

    no_progress = select(TransitionItem.playbook_item_id).where(
        TransitionItem.transition_id == "TR-0001", TransitionItem.status == "Not started"
    )
    golden = db.scalars(
        select(PlaybookItem)
        .where(PlaybookItem.source == "PORTFOLIO", PlaybookItem.portfolio == "GCC")
        .where(PlaybookItem.mandatory.is_(False), PlaybookItem.active.is_(True))
        .where(PlaybookItem.id.in_(no_progress))
        .order_by(PlaybookItem.id)
    ).first()
    assert golden is not None
    row = _make(
        db,
        "accept_applicability",
        {"decisions": [{"item_id": golden.id, "applies": "No", "reason": "No card data"}]},
    )
    assert _accept(client, headers, row.id, IRM).status_code == 403
    res = _accept(client, headers, row.id, FOCAL)
    assert res.status_code == 200, res.text
    assert res.json()["result"] == {"accepted": 1}
    item = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == "TR-0001", TransitionItem.playbook_item_id == golden.id
        )
    ).one()
    db.refresh(item)
    assert item.applicability == "Not applicable" and item.na_reason == "No card data"


def test_accept_update_transition_by_focal_and_admin_not_others(client, db, headers, fresh_seed):
    payload = {"transition_id": "TR-0001", "changes": {"next_decision_date": "2026-12-20"}}
    row = _make(db, "update_transition", payload)
    assert _accept(client, headers, row.id, OTHER_FOCAL).status_code == 403
    res = _accept(client, headers, row.id, FOCAL)
    assert res.status_code == 200, res.text
    assert res.json()["result"]["changed"] == ["next_decision_date"]
    db.expire_all()
    assert str(db.get(Transition, "TR-0001").next_decision_date) == "2026-12-20"
    admin_row = _make(
        db, "update_transition", {"transition_id": "TR-0001", "changes": {"market": "UK"}}
    )
    # R-01: an Admin may only re-assign people, never edit workflow data such as the market
    assert _accept(client, headers, admin_row.id, "U16").status_code == 403
    people_row = _make(
        db, "update_transition", {"transition_id": "TR-0001", "changes": {"pm_user_id": "U10"}}
    )
    assert _accept(client, headers, people_row.id, "U16").status_code == 200
    # tier and gate are untouched by any update_transition
    t = db.get(Transition, "TR-0001")
    assert t.current_gate == "SG4_ATD"


def test_update_item_accept_and_guards(client, db, headers, fresh_seed):
    payload = {
        "transition_id": "TR-0001",
        "item_id": "S3-019",
        "changes": {"owner_user_id": "U13", "note": "Waiting for the vendor"},
        "current": {"owner_user_id": "U10"},
    }
    row = _make(db, "update_item", payload)
    assert _accept(client, headers, row.id, IRM).status_code == 403  # IRM cannot edit B/T items
    assert _accept(client, headers, row.id, OTHER_FOCAL).status_code == 403
    res = _accept(client, headers, row.id, FOCAL)
    assert res.status_code == 200, res.text
    assert set(res.json()["result"]["changed"]) == {"owner_user_id", "note"}
    item = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == "TR-0001", TransitionItem.playbook_item_id == "S3-019"
        )
    ).one()
    db.refresh(item)
    assert item.owner_user_id == "U13" and item.last_updated_source == "Human"
    stale = _make(
        db,
        "update_item",
        {
            "transition_id": "TR-0001",
            "item_id": "S3-019",
            "changes": {"owner_user_id": "U11"},
            "current": {"owner_user_id": "U10"},  # it is U13 now
        },
    )
    res = _accept(client, headers, stale.id, FOCAL)
    assert res.status_code == 409 and "changed" in res.json()["detail"].lower()
    db.expire_all()
    assert db.get(OrionProposal, stale.id).status == "Open"


def test_add_evidence_is_submitted_never_accepted(client, db, headers, fresh_seed):
    text = "Subject: DPIA sign-off\nI approve the DPIA. Regards, Dan"
    row = _make(
        db,
        "add_evidence",
        {
            "transition_id": "TR-0001",
            "item_id": "S3-019",
            "title": "DPIA sign-off",
            "type": "Email sign-off",
            "text": text,
        },
    )
    assert _accept(client, headers, row.id, "U15").status_code == 403
    res = _accept(client, headers, row.id, FOCAL)
    assert res.status_code == 200, res.text
    evidence = db.get(Evidence, res.json()["result"]["evidence_id"])
    assert evidence.status == "Submitted" and evidence.text == text
    assert evidence.reviewed_by is None


def test_create_transition_is_a_handoff(client, db, headers, fresh_seed):
    payload = {
        "prefill": {"name": "Medallia 2", "portfolio": "GCC"},
        "fields": [],
        "missing_fields": ["project_type"],
        "ambiguous_fields": [],
        "source": "chat",
        "source_excerpt": "x",
    }
    row = _make(db, "create_transition", payload, transition_id=None)
    before = db.scalar(select(func.count()).select_from(Transition))
    assert _accept(client, headers, row.id, "U15").status_code == 403
    res = _accept(client, headers, row.id, FOCAL)
    assert res.status_code == 200, res.text
    assert res.json()["navigate_to"] == f"/transitions/new?proposal={row.id}"
    assert res.json()["result"] == {"handoff": True}
    assert db.scalar(select(func.count()).select_from(Transition)) == before
    assert _audit(db, row.id)[0].actor_type == "Human"
    got = client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U15"))
    assert got.status_code == 200 and got.json()["status"] == "Accepted"


def test_get_and_list_proposals(client, db, headers, fresh_seed):
    a = _make(db, "create_action", _action_payload())
    b = _make(db, "draft_chaser", {"item_ids": ["S3-019"]})
    assert client.get(f"{API}/orion/proposals/999999", headers=headers(FOCAL)).status_code == 404
    rows = client.get(f"{API}/orion/proposals", headers=headers(FOCAL)).json()
    assert [r["id"] for r in rows][:2] == [b.id, a.id]
    only = client.get(
        f"{API}/orion/proposals",
        params={"transition_id": "TR-0001", "status": "Open"},
        headers=headers(FOCAL),
    ).json()
    assert {r["id"] for r in only} >= {a.id, b.id}
    assert (
        client.get(
            f"{API}/orion/proposals", params={"status": "Bogus"}, headers=headers(FOCAL)
        ).status_code
        == 422
    )
    assert client.get(f"{API}/orion/proposals").status_code == 401
