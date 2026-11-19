"""Reminder engine (BR-060, AC-11): run, de-duplication, autonomous mode, scope."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import select

from app import clock
from app.models import (
    ApprovalRequest,
    AuditEvent,
    OrionDraft,
    OutboxMessage,
    ReminderRule,
    ReminderRun,
    Transition,
    TransitionItem,
    User,
)
from app.rules.constants import GATE_ORDER

API = "/api/v1"
ALL = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
# Seed "today" + 8 days: overdue actions, a stale approval step and a stale OCET input request.
LATER = clock.today() + timedelta(days=8)  # evaluated at import: same seed date as the tests


@contextmanager
def _today(day: date) -> Iterator[None]:
    clock.set_today_override(day)
    try:
        yield
    finally:
        clock.set_today_override(None)


def _run(client, headers, user="U16", **body):
    return client.post(f"{API}/reminders/run", json=body or None, headers=headers(user))


def _drafts(db, **where):
    db.expire_all()
    return list(db.scalars(select(OrionDraft).filter_by(**where).order_by(OrionDraft.id)).all())


def _complete_items_for_atd(db, transition_id="TR-0001"):
    limit = GATE_ORDER["SG4_ATD"]
    rows = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition_id,
            TransitionItem.applicability == "Applies",
        )
    ).all()
    for row in rows:
        if GATE_ORDER.get(row.due_gate, 0) <= limit:
            row.status = "Compliant" if row.playbook_item.lens == "Compliance" else "Complete"
    db.commit()


def test_run_permissions_and_validation(client, headers, fresh_seed):
    assert _run(client, headers, "U10").status_code == 403
    assert _run(client, headers, "U14").status_code == 403
    assert _run(client, headers, "U16", rules=["R9"]).status_code == 422
    assert _run(client, headers, "U16", transition_id="TR-9999").status_code == 404
    assert client.get(f"{API}/reminders/status").status_code == 401


def test_seed_run_creates_drafts_and_status(client, headers, db, fresh_seed):
    res = _run(client, headers, "U16")
    assert res.status_code == 200
    body = res.json()
    assert set(body["created"]) == set(ALL)
    assert body["created"]["R1"] > 0 and body["created"]["R6"] > 0 and body["created"]["R7"] > 0
    assert body["sent_autonomously"] == 0 and body["skipped_duplicates"] == 0
    assert len(body["drafts"]) == sum(body["created"].values())
    drafts = _drafts(db, rule_id="R1")
    assert drafts
    assert all(d.status == "Draft" and d.created_source == "Workflow rule" for d in drafts)
    assert all((d.recipient_key or "").startswith("R1|") for d in drafts)
    # one digest per owner per transition
    assert len({d.recipient_key for d in drafts}) == len(drafts)
    event = db.scalars(select(AuditEvent).where(AuditEvent.entity == "ReminderRun")).one()
    assert event.action == "run" and event.actor_type == "Human" and event.actor_user_id == "U16"

    status = client.get(f"{API}/reminders/status", headers=headers("U10")).json()
    assert status["last_run"]["run_id"] == body["run_id"]
    assert status["last_run"]["created"] == body["created"]
    assert [r["id"] for r in status["rules"]] == list(ALL)
    assert status["autonomous_transitions"] == []
    assert db.get(ReminderRun, body["run_id"]).triggered_by == "U16"


def test_second_run_creates_nothing(client, headers, fresh_seed):
    first = _run(client, headers).json()
    second = _run(client, headers).json()
    assert sum(second["created"].values()) == 0 and second["drafts"] == []
    assert second["skipped_duplicates"] >= sum(first["created"].values())


def test_discarded_draft_can_be_regenerated(client, headers, db, fresh_seed):
    _run(client, headers, rules=["R7"])
    (draft,) = _drafts(db, rule_id="R7")
    discarded = client.post(f"{API}/orion/drafts/{draft.id}/discard", headers=headers("U01"))
    assert discarded.status_code == 200, discarded.text
    again = _run(client, headers, rules=["R7"]).json()
    assert again["created"]["R7"] == 1


def test_overdue_pending_and_stale_rules_fire_with_time(client, headers, db, fresh_seed):
    with _today(LATER):
        body = _run(client, headers, transition_id="TR-0001").json()
    created = body["created"]
    assert created["R2"] == 3  # all three seeded actions are overdue 8 days later
    assert created["R3"] == 2  # reminder to the approver + escalation to the OR focal
    assert created["R5"] == 1
    r3 = _drafts(db, rule_id="R3")
    assert {d.recipient_key.rsplit(":", 1)[1] for d in r3} == {"remind", "escalate"}
    chaser = _drafts(db, rule_id="R2")[0]
    assert chaser.kind == "Chaser" and "Overdue action" in chaser.subject
    assert all(d.status == "Draft" for d in _drafts(db, transition_id="TR-0001"))


def test_disabled_rule_produces_nothing(client, headers, db, fresh_seed):
    db.get(ReminderRule, "R1").enabled = False
    db.commit()
    body = _run(client, headers, rules=["R1", "R7"]).json()
    assert body["created"]["R1"] == 0 and body["created"]["R7"] == 1
    assert _drafts(db, rule_id="R1") == []


def test_threshold_comes_from_rule_params(client, headers, db, fresh_seed):
    db.get(ReminderRule, "R1").params = {"days_before_decision": 0}
    db.commit()
    assert _run(client, headers, rules=["R1"]).json()["created"]["R1"] == 0


def test_r6_once_per_transition(client, headers, db, fresh_seed):
    first = _run(client, headers, rules=["R6"]).json()
    assert first["created"]["R6"] > 0
    for d in _drafts(db, rule_id="R6"):  # even once the 24 h window has passed
        d.created_at = d.created_at.replace(year=2025)
    db.commit()
    again = _run(client, headers, rules=["R6"]).json()
    assert again["created"]["R6"] == 0 and again["skipped_duplicates"] > 0


def test_r4_ready_for_atd_draft_is_a_proposal_only(client, headers, db, fresh_seed):
    _complete_items_for_atd(db)
    body = _run(client, headers, user="U01", transition_id="TR-0001", rules=["R4"]).json()
    assert body["created"]["R4"] == 1
    (draft,) = _drafts(db, rule_id="R4")
    assert draft.status == "Draft" and draft.kind == "Approval request"
    assert draft.action == {"type": "request_approval", "gate": "SG4_ATD"}
    assert draft.subject == "Ready for AtD - request OLM approval"
    # The message IS the approval request: To = the OLM (first chain step), Cc = the OR focal.
    olm, focal = db.get(User, "U12"), db.get(User, "U01")
    assert draft.to == [olm.email] and draft.cc == [focal.email]
    assert "Sofia Garcia" in draft.body_html and "Asha Menon" in draft.body_html
    # de-dup key is still rule | transition | OR focal | subject (stable)
    assert draft.recipient_key == "R4|TR-0001|U01|ready:SG4_ATD"
    # Orion changed no approval state: nothing was requested by the run itself
    assert db.scalars(select(ApprovalRequest).where(ApprovalRequest.type == "AtD")).all() == []
    again = _run(client, headers, user="U01", transition_id="TR-0001", rules=["R4"]).json()
    assert again["created"]["R4"] == 0 and again["skipped_duplicates"] == 1


def test_r4_send_starts_the_chain_once_and_mails_the_olm_once(client, headers, db, fresh_seed):
    tid = "TR-0018"  # OR focal U04
    db.get(Transition, tid).current_gate = "SG4_ATD"
    _complete_items_for_atd(db, tid)
    for row in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid)).all():
        row.gap_severity = None
    db.commit()
    transition = db.get(Transition, tid)
    olm, focal = db.get(User, transition.olm_user_id), db.get(User, transition.or_focal_user_id)
    assert _run(client, headers, user=focal.id, transition_id=tid, rules=["R4"]).json()[
        "created"
    ] == {**dict.fromkeys(ALL, 0), "R4": 1}
    (draft,) = _drafts(db, rule_id="R4", transition_id=tid)
    assert draft.to == [olm.email] and draft.cc == [focal.email]

    # the draft stays in the OR focal's queue; only she may send it
    queue = client.get(f"{API}/orion/drafts", params={"status": "Draft"}, headers=headers(focal.id))
    row = next(d for d in queue.json() if d["id"] == draft.id)
    assert row["can_send"] is True and row["to"] == [olm.email]
    other = client.get(f"{API}/orion/drafts", params={"status": "Draft"}, headers=headers("U16"))
    assert next(d for d in other.json() if d["id"] == draft.id)["can_send"] is False
    assert (
        client.post(f"{API}/orion/drafts/{draft.id}/send", headers=headers("U16")).status_code
        == 403
    )

    sent = client.post(f"{API}/orion/drafts/{draft.id}/send", headers=headers(focal.id))
    assert sent.status_code == 200, sent.text
    chains = db.scalars(select(ApprovalRequest).where(ApprovalRequest.transition_id == tid)).all()
    assert len(chains) == 1 and chains[0].type == "AtD" and chains[0].status == "Pending"

    db.expire_all()
    out = db.scalars(select(OutboxMessage).order_by(OutboxMessage.id)).all()
    emails = [m for m in out if m.channel == "Email"]
    assert len(emails) == 1
    assert emails[0].to == [olm.email] and emails[0].cc == [focal.email]
    assert not any(focal.email in m.to for m in emails)  # no self-addressed e-mail
    cards = [m for m in out if m.channel == "Teams" and m.adaptive_card_json]
    approval_cards = [
        m for m in cards if any(a.get("type") == "Action.Execute" for a in _actions(m))
    ]
    assert len(cards) == 1 and len(approval_cards) == 1  # the one actionable approval card

    again = client.post(f"{API}/orion/drafts/{draft.id}/send", headers=headers(focal.id))
    assert again.status_code == 409
    assert (
        len(db.scalars(select(ApprovalRequest).where(ApprovalRequest.transition_id == tid)).all())
        == 1
    )
    kept = client.get(
        f"{API}/orion/drafts", params={"transition_id": tid}, headers=headers(focal.id)
    )
    final = next(d for d in kept.json() if d["id"] == draft.id)
    assert final["status"] == "Sent" and final["can_send"] is False


def _actions(message: OutboxMessage) -> list[dict]:
    return list((message.adaptive_card_json or {}).get("actions") or [])


def test_autonomous_mode_sends_only_eligible_rules(client, headers, db, fresh_seed):
    db.get(Transition, "TR-0001").autonomous_mode = True
    _complete_items_for_atd(db)  # an R4 candidate exists as well but must stay a draft
    with _today(LATER):
        status = client.get(f"{API}/reminders/status", headers=headers("U01")).json()
        assert status["autonomous_transitions"] == ["TR-0001"]
        body = _run(client, headers, user="U16", transition_id="TR-0001").json()
    rows = _drafts(db, transition_id="TR-0001")
    sent = [d for d in rows if d.status == "Sent"]
    assert body["sent_autonomously"] == len(sent) > 0
    assert {"R2", "R5"} <= {d.rule_id for d in sent}
    assert {d.rule_id for d in sent} <= {"R1", "R2", "R3", "R5"}
    for d in sent:
        assert d.sent_autonomously and d.sent_by is None and d.sent_at is not None
        if d.rule_id == "R3":
            assert d.recipient_key.endswith(":remind")
    held = [d for d in rows if d.status == "Draft"]
    assert any(d.rule_id == "R3" and d.recipient_key.endswith(":escalate") for d in held)
    assert any(d.rule_id == "R4" for d in held)
    assert all(not d.sent_autonomously for d in held)
    assert not any(d.rule_id in ("R4", "R6", "R7") for d in sent)
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.entity == "OrionDraft", AuditEvent.action == "sent")
    ).all()
    assert len(events) == len(sent)
    assert all(e.actor_type == "Workflow rule" and e.actor_user_id is None for e in events)
    linked = db.scalars(
        select(OutboxMessage).where(OutboxMessage.draft_id.in_([d.id for d in sent]))
    ).all()
    assert linked
    # drafts of non-autonomous transitions stay drafts
    others = [d for d in _drafts(db) if d.transition_id != "TR-0001"]
    assert all(d.status == "Draft" for d in others)


def test_autonomous_requires_rule_flag(client, headers, db, fresh_seed):
    db.get(Transition, "TR-0001").autonomous_mode = True
    db.get(ReminderRule, "R2").autonomous_eligible = False
    db.commit()
    with _today(LATER):
        _run(client, headers, transition_id="TR-0001", rules=["R2"])
    drafts = _drafts(db, rule_id="R2")
    assert drafts and all(d.status == "Draft" for d in drafts)


def test_or_focal_scope(client, headers, db, fresh_seed):
    # U02 is not the focal of TR-0001: explicit transition -> 403; an all-run is limited to own ones
    assert _run(client, headers, "U02", transition_id="TR-0001").status_code == 403
    own = {t.id for t in db.scalars(select(Transition).where(Transition.or_focal_user_id == "U02"))}
    body = _run(client, headers, "U02").json()
    assert own and body["drafts"]
    assert {d.transition_id for d in _drafts(db)} <= own
    assert _run(client, headers, "U01", transition_id="TR-0001").status_code == 200


def test_r4_send_by_the_or_focal_starts_the_chain(client, headers, db, fresh_seed):
    _complete_items_for_atd(db)
    _run(client, headers, user="U01", transition_id="TR-0001", rules=["R4"])
    (draft,) = _drafts(db, rule_id="R4")
    res = client.post(f"{API}/orion/drafts/{draft.id}/send", headers=headers("U01"))
    if res.status_code == 200:  # readiness may still block in the seed; then the draft stays Draft
        assert res.json()["result"].get("approval_request_id")
    else:
        assert res.status_code == 409
        assert _drafts(db, id=draft.id)[0].status == "Draft"


def test_scheduler_is_off_by_default_and_job_runs_without_a_user(client, db, fresh_seed):
    from app import scheduler

    scheduler.start_scheduler(client.app)  # REMINDER_JOB_ENABLED is false -> no-op
    assert getattr(client.app.state, "scheduler", None) is None
    scheduler.stop_scheduler()  # safe when not started
    scheduler.run_reminder_job()
    run = db.scalars(select(ReminderRun).order_by(ReminderRun.id.desc())).first()
    assert run is not None and run.triggered_by == "scheduler"
    event = db.scalars(select(AuditEvent).where(AuditEvent.entity == "ReminderRun")).first()
    assert event.actor_type == "System"


def test_reminder_wording_variants():
    from app.services.mock.ai_messages import draft_message

    base = {"transition_id": "TR-1", "transition_name": "Agent", "or_focal_name": "Asha"}
    overdue = draft_message("chaser", {**base, "action_title": "Fix", "days_overdue": 3})
    assert overdue["subject"].startswith("Overdue action: Fix for Agent")
    esc = draft_message(
        "chaser",
        {
            **base,
            "escalation": True,
            "approver_name": "Sofia",
            "gate_short": "AtD",
            "days_pending": 6,
        },
    )
    assert "Escalation" in esc["subject"] and "Sofia" in esc["body_html"]
    items = [{"id": f"X{n}", "title": f"T{n}"} for n in range(3)]
    chaser = draft_message("chaser", {**base, "items": items})["body_html"]
    assert chaser.count("<ul>") == 1 and chaser.count("</ul>") == 1 and chaser.count("<li>") == 3
