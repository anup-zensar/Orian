"""Per-transition access for gates and drafts (BE#1, BE#6, BE#8, BE#12 - access package B).

Seed facts: U01 Asha Menon is the OR focal of every seeded transition (TR-0005 is at SG2); U02 is a
test-only OR focal who owns none. U12 is the OLM and U14 the IRM of every seeded transition.
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain import drafts
from app.models import (
    AuditEvent,
    Condition,
    OrionDraft,
    OutboxMessage,
    Transition,
    TransitionItem,
    User,
)
from app.rules.constants import DONE_STATUSES, NA_STATUSES, done_status_for

API = "/api/v1"
FLAGSHIP = "TR-0001"


def _post(client, headers, url, body, user):
    return client.post(f"{API}{url}", json=body, headers=headers(user))


def _ready_for_atd(db, tid="TR-0005"):
    transition = db.get(Transition, tid)
    transition.current_gate = "SG4_ATD"
    for row in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid)).all():
        if row.applicability == "Applies" and row.status not in DONE_STATUSES | NA_STATUSES:
            row.status = done_status_for(row.playbook_item.lens)
            row.gap_severity = None
    db.commit()
    return transition


def _approval_draft(db, tid="TR-0005", gate="SG4_ATD", kind="Approval request", to=None):
    transition = db.get(Transition, tid)
    olm = db.get(User, transition.olm_user_id)
    draft = drafts.create_draft(
        db,
        kind=kind,
        transition=transition,
        to=to or [olm.email],
        cc=[],
        subject="AtD request",
        body_html="<p>Please approve</p>",
        created_source="Orion agent",
        action={"type": "request_approval", "gate": gate},
        related_ids=[tid],
    )
    db.commit()
    return draft


# --- gates: only the transition's OR focal ------------------------------------------------------


def test_other_or_focal_cannot_decide_review_or_request_approval(client, headers):
    decision = _post(
        client,
        headers,
        f"/transitions/{FLAGSHIP}/gates/SG4_ATD/decision",
        {"decision": "Approve"},
        "U02",
    )
    assert decision.status_code == 403
    assert decision.json()["reasons"] == [
        "Only Asha Menon, the OR focal of TR-0001, can record this decision"
    ]
    review = _post(
        client, headers, "/transitions/TR-0003/gates/SG3/review", {"outcome": "Proceed"}, "U02"
    )
    assert review.status_code == 403 and "Asha Menon" in review.json()["detail"]
    request = _post(
        client, headers, f"/transitions/{FLAGSHIP}/gates/SG4_ATD/request-approval", {}, "U02"
    )
    assert request.status_code == 403 and "Asha Menon" in request.json()["detail"]


def test_assigned_focal_gets_domain_answer_not_403(client, headers):
    res = _post(
        client,
        headers,
        f"/transitions/{FLAGSHIP}/gates/SG4_ATD/decision",
        {"decision": "Approve"},
        "U01",
    )
    assert res.status_code == 409  # rules say not yet, but access is fine


def test_admin_planner_leadership_cannot_decide(client, headers):
    for user in ("U16", "U13", "U15", "U10", "U14"):
        res = _post(
            client,
            headers,
            f"/transitions/{FLAGSHIP}/gates/SG4_ATD/decision",
            {"decision": "Approve"},
            user,
        )
        assert res.status_code == 403, user


# --- drafts -------------------------------------------------------------------------------------


def test_drafts_are_limited_to_the_transitions_focal(client, headers, fresh_seed):
    body = {"transition_id": FLAGSHIP, "item_ids": ["S45-014"]}
    assert _post(client, headers, "/orion/drafts/chaser", body, "U02").status_code == 403
    created = _post(client, headers, "/orion/drafts/chaser", body, "U01")
    assert created.status_code == 201, created.text
    did = created.json()["id"]
    patch = {"to": ["x@example.com"], "cc": [], "subject": "s", "body_html": "<p>x</p>"}
    other_edit = client.patch(f"{API}/orion/drafts/{did}", json=patch, headers=headers("U02"))
    assert other_edit.status_code == 403 and "Asha Menon" in other_edit.json()["detail"]
    assert _post(client, headers, f"/orion/drafts/{did}/send", {}, "U02").status_code == 403
    assert _post(client, headers, f"/orion/drafts/{did}/discard", {}, "U02").status_code == 403
    assert client.get(f"{API}/orion/drafts/{did}", headers=headers("U02")).status_code == 200
    assert (
        client.patch(f"{API}/orion/drafts/{did}", json=patch, headers=headers("U01")).status_code
        == 200
    )
    assert _post(client, headers, f"/orion/drafts/{did}/send", {}, "U01").status_code == 200


def test_approval_request_draft_needs_the_focal(client, headers, fresh_seed):
    res = _post(
        client,
        headers,
        "/orion/drafts/approval-request",
        {"transition_id": FLAGSHIP, "gate": "SG4_ATD"},
        "U02",
    )
    assert res.status_code == 403


# --- BE#6: request-approval draft validation ----------------------------------------------------


def test_request_approval_rejects_foreign_chaser_and_sent_drafts(client, headers, db, fresh_seed):
    _ready_for_atd(db)
    url = "/transitions/TR-0005/gates/SG4_ATD/request-approval"
    foreign = _approval_draft(db, tid="TR-0003")
    assert _post(client, headers, url, {"draft_id": foreign.id}, "U01").status_code == 409
    chaser = drafts.create_draft(
        db,
        kind="Chaser",
        transition=db.get(Transition, "TR-0005"),
        to=["a@example.com"],
        cc=[],
        subject="c",
        body_html="<p>c</p>",
        created_source="Orion agent",
    )
    wrong_gate = _approval_draft(db, gate="SG6_ATO")
    db.commit()
    assert _post(client, headers, url, {"draft_id": chaser.id}, "U01").status_code == 409
    assert _post(client, headers, url, {"draft_id": wrong_gate.id}, "U01").status_code == 409
    sent = _approval_draft(db)
    sent.status = "Sent"
    db.commit()
    assert _post(client, headers, url, {"draft_id": sent.id}, "U01").status_code == 409


def test_request_approval_with_draft_marks_sent_once_and_mails_approver_once(
    client, headers, db, fresh_seed
):
    transition = _ready_for_atd(db)
    olm = db.get(User, transition.olm_user_id)
    draft = _approval_draft(db)
    before = db.scalars(select(OutboxMessage)).all()
    res = _post(
        client,
        headers,
        "/transitions/TR-0005/gates/SG4_ATD/request-approval",
        {"draft_id": draft.id},
        "U01",
    )
    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.get(OrionDraft, draft.id).status == "Sent"
    sent = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "OrionDraft",
            AuditEvent.entity_id == str(draft.id),
            AuditEvent.action == "sent",
        )
    ).all()
    assert len(sent) == 1 and "approval request" in sent[0].note
    new = db.scalars(select(OutboxMessage)).all()[len(before) :]
    emails = [m for m in new if m.channel == "Email" and olm.email in m.to]
    assert len(emails) == 1


def test_send_of_an_approval_draft_mails_the_approver_once(client, headers, db, fresh_seed):
    transition = _ready_for_atd(db)
    olm = db.get(User, transition.olm_user_id)
    draft = _approval_draft(db)
    before = len(db.scalars(select(OutboxMessage)).all())
    res = _post(client, headers, f"/orion/drafts/{draft.id}/send", {}, "U01")
    assert res.status_code == 200, res.text
    assert res.json()["result"]["approval_request_id"]
    db.expire_all()
    new = db.scalars(select(OutboxMessage)).all()[before:]
    assert len([m for m in new if m.channel == "Email" and olm.email in m.to]) == 1
    sent = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "OrionDraft",
            AuditEvent.entity_id == str(draft.id),
            AuditEvent.action == "sent",
        )
    ).all()
    assert len(sent) == 1


def test_reminder_kind_draft_with_request_approval_action_can_be_sent(
    client, headers, db, fresh_seed
):
    _ready_for_atd(db)
    draft = _approval_draft(db, kind="Reminder")
    res = _post(client, headers, f"/orion/drafts/{draft.id}/send", {}, "U01")
    assert res.status_code == 200, res.text


# --- BE#8: re-conditioning ---------------------------------------------------------------------


def test_new_condition_closes_the_older_open_one_of_the_same_item(db, fresh_seed):
    from app.domain.conditions import close_superseded_conditions, create_condition

    transition = db.get(Transition, FLAGSHIP)
    old = db.get(Condition, "CON-001")
    item = db.get(TransitionItem, old.transition_item_id)
    new = create_condition(
        db,
        transition=transition,
        item=item,
        set_at_gate="SG4_ATD",
        due_gate="SG6_ATO",
        owner_user_id="U01",
        text="Still needs the load test",
        actor=db.get(User, "U14"),
        actor_type="Human",
    )
    closed = close_superseded_conditions(
        db,
        transition=transition,
        item=item,
        gate="SG4_ATD",
        new_condition=new,
        actor=db.get(User, "U14"),
        actor_type="Human",
    )
    db.commit()
    assert closed == ["CON-001"]
    db.expire_all()
    assert db.get(Condition, "CON-001").status == "Closed"
    assert db.get(Condition, "CON-001").close_note == f"Re-conditioned at SG4 (AtD) as {new.id}"
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "Condition", AuditEvent.entity_id == "CON-001"
        )
    ).all()
    assert any(e.action == "closed" for e in events)
    open_for_item = db.scalars(
        select(Condition).where(Condition.transition_item_id == item.id, Condition.status == "Open")
    ).all()
    assert [c.id for c in open_for_item] == [new.id]
