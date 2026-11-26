"""Regression tests for the integration review fixes (batch 2): reminder scope via chat, docx
robustness, extractor cost, proposal privacy, closed transitions, duplicate project ids, R1 gate
label, stale next decision date, leadership risk list, OCET float noise."""

from __future__ import annotations

import io
import struct
import zipfile

from sqlalchemy import select

from app.domain import proposals
from app.domain.gate_actions import _advance
from app.models import Risk, Transition, User
from app.rules import reminders as rm
from app.rules.ocet import OcetLineInput, project_version
from app.services.mock import ai_chat
from app.services.mock.ai_chat import _title_from
from app.services.mock.transcript import MockTranscriptService

API = "/api/v1"
FOCAL = "U01"  # OR focal of TR-0001
OTHER_FOCAL = "U02"  # OR focal of TR-0002


def _chat(client, headers, user, **body):
    return client.post(f"{API}/orion/chat", json=body, headers=headers(user))


# --- reminders: the chat quick action keeps the OR-focal scope -----------------------------------


def test_chat_reminder_quick_action_is_scoped_to_own_transitions(client, headers, fresh_seed):
    body = {"quick_action": "draft_owner_reminders", "form_data": {"transition_id": "TR-0001"}}
    assert _chat(client, headers, OTHER_FOCAL, **body).status_code == 403
    assert _chat(client, headers, FOCAL, **body).status_code == 200
    free = _chat(client, headers, OTHER_FOCAL, message="draft owner reminders for TR-0001")
    assert free.status_code != 200 or "Reminder drafts" not in free.text


def test_reminders_run_rules_are_bounded(client, headers, fresh_seed):
    too_many = client.post(
        f"{API}/reminders/run", json={"rules": ["R1"] * 8}, headers=headers("U16")
    )
    assert too_many.status_code == 422
    unknown = client.post(f"{API}/reminders/run", json={"rules": ["R9"]}, headers=headers("U16"))
    assert unknown.status_code == 422


# --- docx: encrypted / corrupt archives are "no readable text", not a 500 ---------------------------


def _docx(xml: bytes = b"<w:document/>") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml * 20)
    return buf.getvalue()


def test_encrypted_docx_member_gives_empty_text():
    raw = bytearray(_docx())
    local = raw.index(b"PK\x03\x04")
    central = raw.index(b"PK\x01\x02")
    raw[local + 6] |= 0x01  # general purpose flag bit 0: encrypted
    raw[central + 8] |= 0x01
    assert MockTranscriptService().get_text("t.docx", bytes(raw)) == ""


def test_corrupt_deflate_docx_gives_empty_text():
    raw = bytearray(_docx())
    local = raw.index(b"PK\x03\x04")
    name_len, extra_len = struct.unpack_from("<HH", raw, local + 26)
    start = local + 30 + name_len + extra_len
    for i in range(start, start + 12):
        raw[i] = 0xFF
    assert MockTranscriptService().get_text("t.docx", bytes(raw)) == ""


def test_extract_endpoint_answers_400_for_unreadable_docx(client, headers, fresh_seed):
    raw = bytearray(_docx())
    raw[raw.index(b"PK\x03\x04") + 6] |= 0x01
    raw[raw.index(b"PK\x01\x02") + 8] |= 0x01
    res = client.post(
        f"{API}/orion/extract",
        files={"file": ("a.docx", bytes(raw))},
        headers=headers(FOCAL),
    )
    assert res.status_code == 400, res.text


# --- extractor: a long paste skips the quadratic fuzzy stage --------------------------------------


def test_fuzzy_stage_is_skipped_for_long_texts(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("difflib must not run on a long text")

    monkeypatch.setattr(ai_chat.difflib, "SequenceMatcher", boom)
    tokens = ["alpha"] * (ai_chat.FUZZY_MAX_TOKENS + 1)
    assert ai_chat._score(tokens, ["retail", "systems"]) == (0.0, [])


def test_fuzzy_match_still_works_for_short_texts():
    score, _ = ai_chat._score(["retial", "systems"], ["retail", "systems"])
    assert score == 0.75


# --- proposals are private to their creator --------------------------------------------------------


def _proposal_id(res) -> int:
    assert res.status_code == 200, res.text
    return next(m["proposal"]["id"] for m in res.json()["messages"] if m["type"] == "proposal")


def test_create_transition_proposal_is_private(client, headers, fresh_seed):
    text = "Start a gate review for the Medallia VOC project, PRJ0012345, GCC, go live 1 March"
    pid = _proposal_id(_chat(client, headers, FOCAL, message=text))
    own = client.get(f"{API}/orion/proposals/{pid}", headers=headers(FOCAL))
    assert own.status_code == 200
    assert "_created_by" not in own.json()["payload"]
    assert (
        client.get(f"{API}/orion/proposals/{pid}", headers=headers(OTHER_FOCAL)).status_code == 404
    )
    listed = client.get(f"{API}/orion/proposals", headers=headers(OTHER_FOCAL)).json()
    assert pid not in [p["id"] for p in listed]
    dismiss = client.post(f"{API}/orion/proposals/{pid}/dismiss", headers=headers(OTHER_FOCAL))
    assert dismiss.status_code == 404
    assert client.get(f"{API}/orion/proposals/{pid}", headers=headers("U16")).status_code == 200
    assert (
        client.post(f"{API}/orion/proposals/{pid}/dismiss", headers=headers(FOCAL)).status_code
        == 200
    )


def test_transition_proposal_visible_to_assigned_people(client, db, headers, fresh_seed):
    row = proposals.create_proposal(
        db,
        kind="create_action",
        title="t",
        payload={
            "title": "Follow up",
            "item_ids": [],
            "owner_user_id": "U13",
            "due_date": "2027-01-15",
            "priority": "Medium",
        },
        transition_id="TR-0001",
        created_by=FOCAL,
    )
    db.commit()
    url = f"{API}/orion/proposals/{row.id}"
    assert client.get(url, headers=headers("U10")).status_code == 200  # the PM of TR-0001
    assert client.get(url, headers=headers(OTHER_FOCAL)).status_code == 404


def test_accept_and_dismiss_on_closed_transition_is_409(client, db, headers, fresh_seed):
    row = proposals.create_proposal(
        db,
        kind="update_transition",
        title="t",
        payload={"transition_id": "TR-0001", "changes": {"market": "UK"}},
        transition_id="TR-0001",
        created_by=FOCAL,
    )
    db.get(Transition, "TR-0001").status = "Closed"
    db.commit()
    for action in ("accept", "dismiss"):
        res = client.post(f"{API}/orion/proposals/{row.id}/{action}", headers=headers(FOCAL))
        assert res.status_code == 409, (action, res.text)
    # the card still explains why it cannot be accepted
    card = client.get(f"{API}/orion/proposals/{row.id}", headers=headers(FOCAL)).json()
    assert card["can_accept"] is False and "closed" in card["accept_denied_reason"]


# --- admin: no workflow override through update_transition proposals --------------------------------


def test_admin_cannot_accept_workflow_update_proposal(client, db, headers, fresh_seed):
    row = proposals.create_proposal(
        db,
        kind="update_transition",
        title="t",
        payload={"transition_id": "TR-0001", "changes": {"next_decision_date": "2027-06-01"}},
        transition_id="TR-0001",
        created_by="U16",
    )
    db.commit()
    res = client.post(f"{API}/orion/proposals/{row.id}/accept", headers=headers("U16"))
    assert res.status_code == 403


# --- action title ---------------------------------------------------------------------------------


def test_action_title_drops_the_date_phrase_cleanly():
    clause = "ask Tom to review the OCET by 2027-01-15 on TR-0001"
    at = clause.index("2027")
    title = _title_from(clause, "Tom Becker", [{"start": at, "end": at + 10}])
    assert title == "Review the OCET on TR-0001"


# --- duplicate ServiceNow project id --------------------------------------------------------------


def _create_body(**over):
    body = {
        "name": "Dup test agent",
        "servicenow_project_id": "PRJ0052210",
        "project_type": "Agentic AI",
        "portfolio": "GCC",
        "region": "Global",
        "market": "Multi-market",
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
    }
    body.update(over)
    return body


def test_duplicate_project_id_needs_confirmation(client, headers, fresh_seed):
    first = client.post(f"{API}/transitions", json=_create_body(), headers=headers(FOCAL))
    assert first.status_code == 201, first.text
    second = client.post(f"{API}/transitions", json=_create_body(), headers=headers(FOCAL))
    assert second.status_code == 409
    assert first.json()["id"] in second.text
    forced = client.post(
        f"{API}/transitions", json=_create_body(confirm_duplicate=True), headers=headers(FOCAL)
    )
    assert forced.status_code == 201


def test_extract_warns_about_an_existing_project_id(client, headers, fresh_seed):
    first = client.post(f"{API}/transitions", json=_create_body(), headers=headers(FOCAL)).json()
    res = _chat(
        client,
        headers,
        FOCAL,
        message="New Agentic AI transition for PRJ0052210 SMSM Photo Capture, GCC, Global",
    )
    proposal = next(m["proposal"] for m in res.json()["messages"] if m["type"] == "proposal")
    assert any(first["id"] in w for w in proposal["payload"]["warnings"])


# --- R1 names the gate the date belongs to ---------------------------------------------------------


def test_r1_message_uses_the_stage_gate_not_atd(db, fresh_seed):
    from app.domain.reminders import _message_context

    users = {u.id: u for u in db.scalars(select(User)).all()}
    t = db.get(Transition, "TR-0003")
    assert t.current_gate == "SG3"
    cand = rm.ReminderCandidate(
        rule_id="R1",
        transition_id=t.id,
        recipient_user_id=t.or_focal_user_id,
        cc_user_ids=[],
        kind="Reminder",
        subject_key="digest",
        related_ids=[],
        payload={
            "transition_name": t.name,
            "gate": t.current_gate,
            "decision_gate": "SG4_ATD",
            "decision_date": "2026-12-18",
            "days_to_decision": 8,
            "items": [],
        },
        autonomous_eligible=True,
    )
    assert _message_context(cand, t, users)["gate_short"] == "SG3"
    t.current_gate = "SG4_ATD"
    assert _message_context(cand, t, users)["gate_short"] == "SG4 (AtD)"
    db.rollback()


# --- the next decision date does not outlive its gate ----------------------------------------------


def test_advancing_the_gate_clears_the_next_decision_date(db, fresh_seed):
    t = db.get(Transition, "TR-0001")
    assert t.next_decision_date is not None
    _advance(db, t, db.get(User, FOCAL), "SG5_HYPERCARE", "AtD approved")
    assert t.next_decision_date is None
    db.rollback()


# --- leadership risks are not duplicated ------------------------------------------------------------


def test_leadership_risks_have_one_line_per_wording(db, fresh_seed):
    from app.domain.leadership import collect_scope_data

    t = db.get(Transition, "TR-0003")
    t.blocker_note = "Support model not agreed with SOM"
    db.add(
        Risk(
            id="RSK-900",
            transition_id=t.id,
            title="Support model not agreed with SOM",
            rating="High",
            decision="",
            item_ids=[],
        )
    )
    db.flush()
    data = collect_scope_data(db, "transition", t.id)
    lines = [r["text"] for r in data["risks"] if "Support model not agreed" in r["text"]]
    assert len(lines) == 1, lines
    db.rollback()


# --- OCET projection: no float noise ---------------------------------------------------------------


def test_ocet_totals_add_up_from_the_displayed_years():
    line = OcetLineInput(
        line_key="L1",
        category="AI tokens / inference",
        description="x",
        base_amount=40000.0,
        growth_pct=15.0,
        year_overrides={2027: 30},
    )
    proj = project_version([line], 2026, 5)
    yearly = list(proj.lines[0].yearly.values())
    assert yearly[-1] == 79085.5
    assert proj.lines[0].total == sum(yearly) == proj.category_grand["AI tokens / inference"]
    assert proj.total == proj.lines[0].total
