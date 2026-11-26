"""Natural-language actions (CR-02, FR-090, BR-050): plain language / documents -> human-confirmed
proposals. Extraction is deterministic and matches only against the database vocabulary."""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import func, select

from app.domain import cfg, nl_intake
from app.models import (
    AuditEvent,
    FlavourRule,
    OrionProposal,
    Portfolio,
    Transition,
    User,
)
from app.services.mock import ai_chat

API = "/api/v1"
FOCAL = "U01"


def _chat(client, headers, message, user=FOCAL, transition_id=None, item_id=None):
    context = {}
    if transition_id:
        context["transition_id"] = transition_id
    if item_id:
        context["item_id"] = item_id
    res = client.post(
        f"{API}/orion/chat",
        json={"message": message, "context": context},
        headers=headers(user),
    )
    assert res.status_code == 200, res.text
    return res.json()["messages"]


def _extract(client, headers, user=FOCAL, text=None, filename=None, content=None, **data):
    form = dict(data)
    if text is not None:
        form["text"] = text
    files = {"file": (filename, content)} if filename else None
    return client.post(f"{API}/orion/extract", data=form, files=files, headers=headers(user))


def _proposals(messages):
    return [m["proposal"] for m in messages if m["type"] == "proposal"]


def _texts(messages):
    return " ".join(m["text"] for m in messages if m["type"] == "text")


def _field(proposal, name):
    return next(f for f in proposal["payload"]["fields"] if f["name"] == name)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


# --- create a transition from words -----------------------------------------------------------
def test_extract_create_transition_flagship_like(client, headers):
    text = (
        "Start a gate review for the SMSM Photo Capture project, PRJ0052210, architect Mei, "
        "OLM Sofia, go live 1 March"
    )
    res = _extract(client, headers, text=text)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["source"] == "text" and out["characters_read"] == len(text)
    (proposal,) = _proposals(out["messages"])
    assert proposal["kind"] == "create_transition" and proposal["transition_id"] is None
    payload = proposal["payload"]
    prefill = payload["prefill"]
    assert payload["servicenow_found"] is True and payload["servicenow_project_id"] == "PRJ0052210"
    assert prefill["architect_user_id"] == "U11" and prefill["olm_user_id"] == "U12"
    assert prefill["pm_user_id"] == "U10"  # from ServiceNow
    assert prefill["name"] == "SMSM Photo Capture"
    assert prefill["project_type"] == "Agentic AI" and prefill["portfolio"] == "Retail Site Systems"
    assert prefill["or_focal_user_id"] == "U01"  # the writer, defaulted from context
    assert _field(proposal, "or_focal_user_id")["source"] == "context"
    assert _field(proposal, "name")["source"] == "servicenow"
    assert _field(proposal, "architect_user_id")["source"] == "text"
    assert prefill["next_decision_date"].endswith("-03-01")
    for name in ("audience", "write_actions", "sensitive_data", "sites"):
        assert name in payload["missing_fields"], name
        assert name not in prefill
    assert out["intents"][0]["intent"] == "create_transition"
    assert proposal["payload"]["source_excerpt"].startswith("Start a gate review")


def test_extract_unknown_prj_is_not_an_error(client, headers):
    res = _extract(
        client, headers, text="New project Orchid for GCC, Normal, region Global, PRJ9999999"
    )
    assert res.status_code == 200, res.text
    (proposal,) = _proposals(res.json()["messages"])
    assert proposal["payload"]["servicenow_found"] is False
    assert proposal["payload"]["prefill"]["portfolio"] == "GCC"
    assert "not found in ServiceNow" in _field(proposal, "servicenow_project_id")["note"]


def test_extract_never_invents(client, headers):
    res = _extract(
        client, headers, text="New transition called Zed for the Unobtanium project in GCC, Global"
    )
    (proposal,) = _proposals(res.json()["messages"])
    assert _field(proposal, "project_type")["state"] == "missing"
    assert "project_type" not in proposal["payload"]["prefill"]
    assert "project_type" in proposal["payload"]["missing_fields"]
    ai = _extract(
        client, headers, text="New transition called Agent Zed, Agentic AI, GCC, region Global"
    )
    (ai_prop,) = _proposals(ai.json()["messages"])
    for name in ("audience", "write_actions", "sensitive_data"):
        assert name in ai_prop["payload"]["missing_fields"]
    normal = _extract(
        client, headers, text="New transition called Plain Zed, Normal, GCC, region Global"
    )
    (plain,) = _proposals(normal.json()["messages"])
    assert "audience" not in plain["payload"]["missing_fields"]
    assert plain["payload"]["missing_fields"] == []


def test_extract_options_from_words(client, headers):
    text = (
        "New transition called Agent Zed, Agentic AI, GCC, region Global, no write actions, "
        "without sensitive data, internal department audience"
    )
    (proposal,) = _proposals(_extract(client, headers, text=text).json()["messages"])
    prefill = proposal["payload"]["prefill"]
    assert prefill["write_actions"] == "No" and prefill["sensitive_data"] == "No"
    assert prefill["audience"] == "Internal department"
    assert proposal["payload"]["missing_fields"] == []


def test_extract_ambiguous_person(client, db, headers, fresh_seed):
    db.add(User(id="U90", name="Asha Rao", role="OR_FOCAL", email="asha.rao@example.com"))
    db.commit()
    text = "New transition called Orchid for GCC, Normal, region Global, OR focal Asha"
    (proposal,) = _proposals(_extract(client, headers, text=text).json()["messages"])
    focal = _field(proposal, "or_focal_user_id")
    assert focal["state"] == "ambiguous" and focal["value"] is None
    assert {c["value"] for c in focal["candidates"]} == {"U01", "U90"}
    assert "or_focal_user_id" not in proposal["payload"]["prefill"]
    assert "or_focal_user_id" in proposal["payload"]["ambiguous_fields"]
    # the full name resolves it
    (named,) = _proposals(
        _extract(client, headers, text=text.replace("Asha", "Asha Rao")).json()["messages"]
    )
    assert named["payload"]["prefill"]["or_focal_user_id"] == "U90"


def test_vocabulary_is_dynamic(client, db, headers, fresh_seed):
    text = "New project Nimbus for the Data Platform project in Quantum Labs, region Global"
    (before,) = _proposals(_extract(client, headers, text=text).json()["messages"])
    assert "project_type" not in before["payload"]["prefill"]
    db.add(
        FlavourRule(project_type="Data Platform", checklists=["FRAMEWORK"], requires_tiering=False)
    )
    db.add(Portfolio(name="Quantum Labs", code="QL", focus_areas=[], intake_extra_fields=[]))
    db.commit()
    cfg.invalidate()  # what every admin save does
    (after,) = _proposals(_extract(client, headers, text=text).json()["messages"])
    prefill = after["payload"]["prefill"]
    assert prefill["project_type"] == "Data Platform" and prefill["portfolio"] == "Quantum Labs"
    assert _field(after, "project_type")["state"] == "found"
    # a synonym typed on the portfolio in Admin is understood too
    db.get(Portfolio, "Quantum Labs").synonyms = ["the lab"]
    db.commit()
    cfg.invalidate()
    (syn,) = _proposals(
        _extract(client, headers, text="New project Zed, Normal, region Global, the lab").json()[
            "messages"
        ]
    )
    assert syn["payload"]["prefill"]["portfolio"] == "Quantum Labs"


def test_admin_flags_and_labels_drive_the_extraction(client, db, headers, fresh_seed):
    """A new project type with its own synonym and required field, a new portfolio that needs sites,
    a renamed label and an additional required field: all read from the configuration."""
    from app.models import IntakeField

    db.add(
        FlavourRule(
            project_type="Security Review",
            label="Security Review",
            checklists=["FRAMEWORK"],
            requires_tiering=True,
            required_intake_fields=["audience", "cf_budget_code"],
            synonyms=["sec review"],
        )
    )
    db.add(
        Portfolio(
            name="Fuels EU", code="FE", focus_areas=[], requires_sites=True, synonyms=["EU fuels"]
        )
    )
    db.add(
        IntakeField(
            key="cf_budget_code",
            label="Budget code",
            builtin=False,
            type="text",
            visible=True,
            required_mode="by_project_type",
            active=True,
            sort_order=99,
            form="intake",
        )
    )
    db.commit()
    cfg.invalidate()
    text = "New project Pump Cam, sec review, EU fuels, region Global. Site id 1234 key AB1."
    (proposal,) = _proposals(_extract(client, headers, text=text).json()["messages"])
    payload = proposal["payload"]
    assert payload["prefill"]["project_type"] == "Security Review"
    assert payload["prefill"]["portfolio"] == "Fuels EU"
    assert payload["prefill"]["sites"] == [
        {"site_id": "1234", "site_key": "AB1"}
    ]  # requires_sites flag
    assert "audience" in payload["missing_fields"]  # required for the type, from its own list
    assert "cf_budget_code" in payload["missing_fields"]  # the additional field is listed too
    assert _field(proposal, "cf_budget_code")["label"] == "Budget code"
    assert _field(proposal, "audience")["required"] is True


def test_renamed_field_label_is_used(client, db, headers, fresh_seed):
    from app.models import IntakeField

    db.get(IntakeField, "region").label = "Sales region"
    db.commit()
    cfg.invalidate()
    text = "New project Nimbus, Normal, GCC, region Global"
    (proposal,) = _proposals(_extract(client, headers, text=text).json()["messages"])
    assert _field(proposal, "region")["label"] == "Sales region"


def test_extract_retail_sites(client, headers):
    retail = (
        "New project Forecourt Cam, Normal, Retail Site Systems, region Global. "
        "Site id 1234 key AB1 and site id 5678 key CD2."
    )
    (proposal,) = _proposals(_extract(client, headers, text=retail).json()["messages"])
    assert proposal["payload"]["prefill"]["sites"] == [
        {"site_id": "1234", "site_key": "AB1"},
        {"site_id": "5678", "site_key": "CD2"},
    ]
    assert "sites" not in proposal["payload"]["missing_fields"]
    other = retail.replace("Retail Site Systems", "GCC")
    (gcc,) = _proposals(_extract(client, headers, text=other).json()["messages"])
    assert "sites" not in gcc["payload"]["prefill"]
    assert "sites" not in gcc["payload"]["missing_fields"]
    bare = "New project Forecourt Cam, Normal, Retail Site Systems, region Global"
    (needs,) = _proposals(_extract(client, headers, text=bare).json()["messages"])
    assert "sites" in needs["payload"]["missing_fields"]


def test_extract_nothing_found_stores_no_proposal(client, db, headers):
    before = _count(db, OrionProposal)
    res = _extract(client, headers, text="blah blah nothing useful here")
    assert res.status_code == 200
    assert _proposals(res.json()["messages"]) == []
    assert "could not find any intake details" in _texts(res.json()["messages"])
    assert _count(db, OrionProposal) == before


def test_extract_document_formats_and_errors(client, headers, db):
    note = "New project Orchid for GCC, Normal, region Global, go live 1 March 2027"
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n" + note + "\n"
    cases = [
        ("brief.txt", note.encode()),
        ("brief.md", ("# Brief\n" + note).encode()),
        ("call.vtt", vtt.encode()),
        ("brief.docx", _docx(note)),
    ]
    for name, content in cases:
        res = _extract(client, headers, filename=name, content=content)
        assert res.status_code == 200, (name, res.text)
        out = res.json()
        assert out["source"] == "document" and out["source_name"] == name
        (proposal,) = _proposals(out["messages"])
        assert proposal["payload"]["prefill"]["portfolio"] == "GCC"
        assert _field(proposal, "portfolio")["source"] == "document"
        assert proposal["payload"]["source_name"] == name
    assert _extract(client, headers, filename="brief.pdf", content=b"%PDF").status_code == 400
    assert _extract(client, headers, filename="empty.txt", content=b"   ").status_code == 400
    assert (
        _extract(
            client, headers, filename="big.txt", content=b"x" * (5 * 1024 * 1024 + 1)
        ).status_code
        == 413
    )
    assert _extract(client, headers, text="x" * 20001).status_code == 422
    assert _extract(client, headers).status_code == 400
    assert (
        _extract(client, headers, text="hello", filename="a.txt", content=b"hi").status_code == 400
    )
    assert _extract(client, headers, text="hello", transition_id="TR-9999").status_code == 404
    long = (
        "New project Orchid for GCC, Normal, region Global. " + "filler words here. " * 2000
    ).encode()
    res = _extract(client, headers, filename="long.txt", content=long)
    assert res.status_code == 200 and res.json()["truncated"] is True
    assert res.json()["characters_read"] == 20000


def test_extract_is_deterministic(client, db, headers, fresh_seed):
    text = "New project Orchid for GCC, Normal, region Global, architect Mei, go live 1 March"
    first = _extract(client, headers, text=text).json()
    second = _extract(client, headers, text=text).json()
    assert first == second
    assert _count(db, OrionProposal) == 1  # the open duplicate is returned, not stored again
    (other,) = _proposals(
        _extract(client, headers, text=text.replace("Orchid", "Violet")).json()["messages"]
    )
    assert other["id"] != _proposals(first["messages"])[0]["id"]


def test_email_source_and_subject_name(client, headers):
    email = (
        "From: dan@example.com\nSubject: Fwd: Loyalty Chatbot go-live\n\n"
        "Hi, please set up a new transition in Global Marketing, Normal, region Americas."
    )
    out = _extract(client, headers, text=email).json()
    assert out["source"] == "email"
    (proposal,) = _proposals(out["messages"])
    assert proposal["payload"]["prefill"]["name"] == "Loyalty Chatbot go-live"
    assert proposal["payload"]["prefill"]["portfolio"] == "Global Marketing"
    assert proposal["payload"]["prefill"]["region"] == "Americas"


def test_chat_new_transition_hand_off(client, db, headers, fresh_seed):
    msgs = _chat(
        client,
        headers,
        "Start a gate review for the Medallia VOC project, PRJ0012345, GCC, go live 1 March",
    )
    (proposal,) = _proposals(msgs)
    assert proposal["kind"] == "create_transition"
    before = _count(db, Transition)
    # a create_transition prefill is private to the person who asked Orion for it
    res = client.post(f"{API}/orion/proposals/{proposal['id']}/accept", headers=headers("U15"))
    assert res.status_code == 404
    # a user without the permission gets 403 on their own proposal
    own = _proposals(
        _chat(
            client,
            headers,
            "Start a gate review for the Medallia VOC project, PRJ0012345, GCC",
            "U15",
        )
    )[0]
    res = client.post(f"{API}/orion/proposals/{own['id']}/accept", headers=headers("U15"))
    assert res.status_code == 403
    res = client.post(f"{API}/orion/proposals/{proposal['id']}/accept", headers=headers(FOCAL))
    assert res.status_code == 200
    assert res.json()["navigate_to"] == f"/transitions/new?proposal={proposal['id']}"
    assert _count(db, Transition) == before
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "OrionProposal", AuditEvent.entity_id == str(proposal["id"])
        )
    ).one()
    assert event.actor_type == "Human" and "Accepted Orion proposal" in event.note
    got = client.get(f"{API}/orion/proposals/{proposal['id']}", headers=headers(FOCAL)).json()
    assert got["status"] == "Accepted" and got["payload"]["prefill"]["portfolio"] == "GCC"


# --- commands --------------------------------------------------------------------------------
def test_commands_create_action(client, headers):
    msgs = _chat(
        client, headers, "ask Tom to finish the DPIA for S3-019 by Friday", transition_id="TR-0001"
    )
    (proposal,) = _proposals(msgs)
    assert proposal["kind"] == "create_action" and proposal["transition_id"] == "TR-0001"
    payload = proposal["payload"]
    assert payload["owner_user_id"] == "U13" and payload["item_ids"] == ["S3-019"]
    assert payload["due_date"] == "2026-11-20"  # the next Friday after the demo date 2026-11-16
    assert payload["title"] == "Finish the DPIA for S3-019"
    assert proposal["can_accept"] is True
    # a user who cannot accept still sees the card, with the reason
    (other,) = _proposals(
        _chat(
            client,
            headers,
            "ask Tom to finish the DPIA for S3-019 by Friday",
            user="U02",
            transition_id="TR-0001",
        )
    )
    assert other["can_accept"] is False and other["accept_denied_reason"]


def test_commands_missing_owner_or_date_asks_in_text(client, db, headers):
    before = _count(db, OrionProposal)
    msgs = _chat(client, headers, "action for Mei: update the diagram", transition_id="TR-0001")
    assert _proposals(msgs) == []
    assert "due date" in _texts(msgs)
    msgs = _chat(
        client, headers, "create an action to update the diagram by Friday", transition_id="TR-0001"
    )
    assert _proposals(msgs) == []
    assert "owner" in _texts(msgs)
    assert _count(db, OrionProposal) == before


def test_commands_by_transition_name_and_unknown(client, headers):
    msgs = _chat(client, headers, "move next decision date of Medallia to 5 Dec", user="U01")
    (proposal,) = _proposals(msgs)
    assert proposal["kind"] == "update_transition" and proposal["transition_id"] == "TR-0014"
    assert proposal["payload"]["changes"] == {"next_decision_date": "2026-12-05"}
    msgs = _chat(client, headers, "move next decision date of TR-9999 to 5 Dec")
    assert _proposals(msgs) == [] and "TR-9999" in _texts(msgs)
    msgs = _chat(client, headers, "ask Tom to finish the DPIA by Friday")
    assert _proposals(msgs) == [] and "Which transition" in _texts(msgs)


def test_commands_multi_and_limit(client, headers, fresh_seed):
    msgs = _chat(
        client,
        headers,
        "ask Tom to finish the DPIA for S3-019 by Friday; ask Mei to update the diagram by 5 Dec",
        transition_id="TR-0001",
    )
    proposals = _proposals(msgs)
    assert [p["payload"]["owner_user_id"] for p in proposals] == ["U13", "U11"]
    assert proposals[1]["payload"]["due_date"] == "2026-12-05"
    six = "\n".join(f"ask Tom to prepare report {n} by Friday" for n in range(1, 7))
    msgs = _chat(client, headers, six, transition_id="TR-0001")
    assert len(_proposals(msgs)) == 5
    assert "first 5" in _texts(msgs)


def test_commands_other_kinds(client, db, headers, fresh_seed):
    (chaser,) = _proposals(_chat(client, headers, "chase Asha on S3-019", transition_id="TR-0001"))
    assert chaser["kind"] == "draft_chaser" and chaser["payload"]["item_ids"] == ["S3-019"]
    (approval,) = _proposals(_chat(client, headers, "request AtD approval for TR-0001"))
    assert approval["kind"] == "request_approval" and approval["payload"]["gate"] == "SG4_ATD"
    (exc,) = _proposals(
        _chat(
            client,
            headers,
            "we need an exception for FW-016 because the vendor cannot meet it",
            transition_id="TR-0001",
        )
    )
    assert exc["kind"] == "request_exception" and exc["payload"]["item_id"] == "FW-016"
    msgs = _chat(
        client, headers, "we need an exception for S3-019 because x", transition_id="TR-0001"
    )
    assert _proposals(msgs) == [] and "Compliance items only" in _texts(msgs)
    (owner,) = _proposals(_chat(client, headers, "assign S3-019 to Tom", transition_id="TR-0001"))
    assert owner["kind"] == "update_item"
    assert owner["payload"]["changes"] == {"owner_user_id": "U13"}
    assert owner["payload"]["current"] == {"owner_user_id": "U10"}
    db.get(Transition, "TR-0005").architect_user_id = None
    db.commit()
    (role,) = _proposals(_chat(client, headers, "make Mei the architect on TR-0005", user="U01"))
    assert role["payload"]["changes"] == {"architect_user_id": "U11"}
    assert role["kind"] == "update_transition"
    (region,) = _proposals(_chat(client, headers, "change the region of TR-0001 to Americas"))
    assert region["payload"]["changes"] == {"region": "Americas"}


def test_update_item_guardrails(client, db, headers, fresh_seed):
    # Compliance item: no status proposal, a text explains
    msgs = _chat(client, headers, "S45-014 is complete", transition_id="TR-0001")
    assert _proposals(msgs) == [] and "Compliance" in _texts(msgs)
    # Gap needs severity and note
    msgs = _chat(client, headers, "S3-019 is a gap", transition_id="TR-0001")
    assert _proposals(msgs) == [] and "gap severity" in _texts(msgs)
    (gap,) = _proposals(
        _chat(
            client,
            headers,
            "S3-019 is a critical gap, no test environment",
            transition_id="TR-0001",
        )
    )
    assert gap["payload"]["changes"] == {
        "status": "Gap",
        "gap_severity": "Critical",
        "note": "no test environment",
    }
    (done,) = _proposals(_chat(client, headers, "S3-019 is complete", transition_id="TR-0001"))
    assert done["payload"]["changes"] == {"status": "Complete"}
    (note,) = _proposals(
        _chat(client, headers, "note on FW-008: waiting for vendor quote", transition_id="TR-0001")
    )
    assert note["payload"]["changes"] == {"note": "waiting for vendor quote"}
    msgs = _chat(client, headers, "S9-999 is complete", transition_id="TR-0001")
    assert _proposals(msgs) == [] and "not an item" in _texts(msgs)
    # accepting as the wrong role is refused, the right role works, and a changed item gives 409
    assert (
        client.post(
            f"{API}/orion/proposals/{done['id']}/accept", headers=headers("U14")
        ).status_code
        == 403
    )
    first = client.post(f"{API}/orion/proposals/{done['id']}/accept", headers=headers(FOCAL))
    assert first.status_code == 200, first.text
    stale = client.post(f"{API}/orion/proposals/{gap['id']}/accept", headers=headers(FOCAL))
    assert stale.status_code in (200, 409)


def test_add_evidence_from_link_and_signoff_email(client, db, headers, fresh_seed):
    (link,) = _proposals(
        _chat(
            client,
            headers,
            "add evidence to S3-019: https://wiki.example/dpia",
            transition_id="TR-0001",
        )
    )
    assert link["kind"] == "add_evidence"
    assert (
        link["payload"]["type"] == "Link" and link["payload"]["url"] == "https://wiki.example/dpia"
    )
    msgs = _chat(client, headers, "add evidence to S3-019", transition_id="TR-0001")
    assert _proposals(msgs) == []
    email = (
        "From: dan@example.com\nSubject: DPIA sign-off S3-019\n\nI approve the DPIA as written. Dan"
    )
    res = _extract(client, headers, text=email, transition_id="TR-0001")
    assert res.status_code == 200, res.text
    (mail,) = _proposals(res.json()["messages"])
    assert mail["kind"] == "add_evidence" and mail["payload"]["type"] == "Email sign-off"
    assert mail["payload"]["text"] == email  # verbatim, never generated
    assert mail["payload"]["item_id"] == "S3-019"
    accepted = client.post(f"{API}/orion/proposals/{mail['id']}/accept", headers=headers(FOCAL))
    assert accepted.status_code == 200, accepted.text
    ev = client.get(f"{API}/transitions/TR-0001/evidence", headers=headers(FOCAL)).json()
    created = next(e for e in ev if e["id"] == accepted.json()["result"]["evidence_id"])
    assert created["status"] == "Submitted"


def test_extract_meeting_notes_for_a_transition(client, headers, fresh_seed):
    notes = (
        "Meeting notes\nTom to finish the DPIA for S3-019 by Friday.\n"
        "Mei to update the architecture diagram by 5 Dec.\n"
    )
    res = _extract(client, headers, text=notes, transition_id="TR-0001")
    assert res.status_code == 200, res.text
    kinds = [
        (p["kind"], p["payload"].get("owner_user_id")) for p in _proposals(res.json()["messages"])
    ]
    assert ("create_action", "U13") in kinds and ("create_action", "U11") in kinds


def test_refusals_create_nothing(client, db, headers, fresh_seed):
    phrases = [
        ("approve AtD for TR-0001", "/transitions/TR-0001/gates"),
        ("mark S45-006 compliant", None),
        ("accept this evidence", None),
        ("close CON-001", None),
        ("send the chaser now", "/drafts"),
        ("delete TR-0014", None),
        ("add a new project type called Data Platform", "/admin"),
        ("act as the IRM and confirm the tier", None),
    ]
    before = {m.__name__: _count(db, m) for m in (OrionProposal, Transition)}
    for phrase, href in phrases:
        msgs = _chat(client, headers, phrase, transition_id="TR-0001")
        assert _proposals(msgs) == [], phrase
        assert [m["type"] for m in msgs][0] == "text", phrase
        assert "can't" in msgs[0]["text"].lower() or "never" in msgs[0]["text"].lower(), phrase
        if href:
            assert any(m["type"] == "link" and m["href"] == href for m in msgs), phrase
    assert {m.__name__: _count(db, m) for m in (OrionProposal, Transition)} == before


def test_quick_actions_in_words(client, headers, fresh_seed):
    msgs = _chat(client, headers, "assess readiness of Mobility Knowledge Agent for AtD")
    assert [m["type"] for m in msgs][0] == "readiness"
    msgs = _chat(client, headers, "who still owes us something on TR-0001?")
    assert msgs[0]["type"] == "table"
    msgs = _chat(client, headers, "open the OCET for TR-0001")
    assert msgs[0]["type"] == "link" and msgs[0]["href"] == "/transitions/TR-0001/ocet"
    msgs = _chat(client, headers, "write a leadership update for the GCC portfolio")
    assert msgs[0]["type"] == "leadership" and msgs[0]["update"]["scope_id"] == "GCC"
    msgs = _chat(client, headers, "write a leadership update for the GCC portfolio", user="U15")
    assert msgs[0]["type"] == "text" and "Only the OR focal" in msgs[0]["text"]
    msgs = _chat(client, headers, "write a leadership update")
    assert msgs[0]["type"] == "form" and msgs[0]["quick_action"] == "create_leadership_update"


# --- catalog / endpoint ----------------------------------------------------------------------
def test_intents_endpoint(client, headers):
    focal = client.get(f"{API}/orion/intents", headers=headers(FOCAL)).json()
    leader = client.get(f"{API}/orion/intents", headers=headers("U15")).json()
    assert focal["refusals"] and len(focal["intents"]) == len(nl_intake.INTENT_CATALOG)
    by = {i["intent"]: i for i in leader["intents"]}
    assert by["create_transition"]["allowed"] is False and by["create_transition"]["denied_reason"]
    assert by["status"]["allowed"] is True and by["status"]["denied_reason"] is None
    assert {i["intent"]: i["allowed"] for i in focal["intents"]}["create_transition"] is True
    assert client.get(f"{API}/openapi.json").status_code in (200, 404)
    assert client.get(f"{API}/orion/intents").status_code == 401


def test_every_catalog_example_parses_to_its_intent(db):
    vocab = nl_intake.build_vocabulary(db)
    skip = {"status", "blocking", "owner", "glossary", "red_transitions", "create_transition"}
    ctx = {"today": "2026-11-16", "transition_id": "TR-0001"}
    for entry in nl_intake.INTENT_CATALOG:
        if entry["intent"] in skip:
            continue
        for example in entry["examples"]:
            if example.startswith("("):
                continue
            commands = ai_chat.parse_command(example, nl_intake.INTENT_CATALOG, vocab, ctx)
            assert commands, example
            assert commands[0]["intent"] == entry["intent"], (example, commands[0]["intent"])


def test_parse_command_never_returns_unknown_intents_and_is_deterministic(db):
    vocab = nl_intake.build_vocabulary(db)
    ctx = {"today": "2026-11-16"}
    text = "ask Tom to finish the DPIA for S3-019 by Friday; blah; chase Asha on S3-019"
    first = ai_chat.parse_command(text, nl_intake.INTENT_CATALOG, vocab, ctx)
    assert first == ai_chat.parse_command(text, nl_intake.INTENT_CATALOG, vocab, ctx)
    known = {e["intent"] for e in nl_intake.INTENT_CATALOG}
    assert {c["intent"] for c in first} <= known
    assert ai_chat.parse_command("zzz qqq", nl_intake.INTENT_CATALOG, vocab, ctx) == []


def test_live_output_is_validated_by_nl_intake(client, db, headers, monkeypatch, fresh_seed):
    """A hostile or hallucinating extractor can not put unknown ids or values into a proposal."""

    class FakeAI:
        def extract_intake(self, text, vocab, servicenow=None):
            def f(value, state="found"):
                return {
                    "value": value,
                    "state": state,
                    "source": "text",
                    "confidence": 1.0,
                    "evidence": None,
                    "candidates": [],
                    "note": None,
                }

            return {
                "fields": {
                    "name": f("Hallucinated"),
                    "project_type": f("Quantum Magic"),
                    "portfolio": f("GCC"),
                    "region": f("Mars"),
                    "audience": f("Everybody"),
                    "architect_user_id": f("U12"),  # an OLM, not an architect
                    "olm_user_id": f("U99"),  # unknown user
                    "next_decision_date": f("not a date"),
                    "sites": f([{"site_id": "1", "site_key": "2"}]),  # GCC does not need sites
                    "risk_tier": f(1),  # not an intake field
                },
                "servicenow_project_id": None,
                "summary": "x",
            }

    monkeypatch.setattr(nl_intake, "get_ai_service", lambda: FakeAI())
    res = _extract(client, headers, text="whatever text")
    assert res.status_code == 200, res.text
    (proposal,) = _proposals(res.json()["messages"])
    assert proposal["payload"]["prefill"] == {
        "name": "Hallucinated",
        "portfolio": "GCC",
        "or_focal_user_id": "U01",
    }
    for name in (
        "project_type",
        "region",
        "audience",
        "architect_user_id",
        "olm_user_id",
        "sites",
        "next_decision_date",
    ):
        assert _field(proposal, name)["state"] == "missing", name

    class HostileCommands:
        def chat(self, message, context):
            return {"intent": "fallback", "entities": {}, "text": "fallback"}

        def parse_command(self, message, catalog, vocab, context):
            return [
                {
                    "intent": "approve_gate",
                    "arguments": {},
                    "missing": [],
                    "ambiguous": {},
                    "confidence": 1,
                    "excerpt": "x",
                },
                {
                    "intent": "create_action",
                    "arguments": {
                        "transition_id": "TR-0001",
                        "owner_user_id": "U99",
                        "due_date": "2026-11-20",
                        "title": "x",
                        "item_ids": [],
                    },
                    "missing": [],
                    "ambiguous": {},
                    "confidence": 1,
                    "excerpt": "x",
                },
            ]

    from app.domain import orion_chat

    monkeypatch.setattr(nl_intake, "get_ai_service", lambda: HostileCommands())
    monkeypatch.setattr(orion_chat, "get_ai_service", lambda: HostileCommands())
    msgs = _chat(client, headers, "do something")
    assert _proposals(msgs) == []


# --- CR-03: project type words ------------------------------------------------------------------
_AI = (
    "New transition called EV charging assistant. Portfolio eMobility. {kind}, Europe, External. "
    "Sensitive data: Personal sensitive. Write actions: Yes. Architect Mei, OLM Sofia, OR focal Asha, "
    "PM Daniel. Go live 15 April 2027."
)
_STD = (
    "New transition called Fleet driver rewards. Portfolio Fleets. {kind}, Europe, External. "
    "Architect Mei, OLM Sofia, OR focal Asha, PM Daniel. Go live 1 June 2027."
)


@pytest.mark.parametrize(
    "template, kind, code, name, portfolio",
    [
        (_AI, "Agentic AI", "Agentic AI", "EV charging assistant", "eMobility"),
        (_AI, "AI Transition", "Agentic AI", "EV charging assistant", "eMobility"),
        (_AI, "Combined", "Agentic AI", "EV charging assistant", "eMobility"),
        (_STD, "Standard transition", "Normal", "Fleet driver rewards", "Fleets"),
        (_STD, "Normal", "Normal", "Fleet driver rewards", "Fleets"),
        (_STD, "Other", "Infrastructure", "Fleet driver rewards", "Fleets"),
    ],
)
def test_extract_project_type_words(client, headers, template, kind, code, name, portfolio):
    res = _extract(client, headers, text=template.format(kind=kind))
    assert res.status_code == 200, res.text
    (proposal,) = _proposals(res.json()["messages"])
    prefill = proposal["payload"]["prefill"]
    assert prefill["project_type"] == code
    assert prefill["name"] == name and prefill["portfolio"] == portfolio
    assert prefill["region"].startswith("Europe")
    assert {
        prefill[k] for k in ("architect_user_id", "olm_user_id", "or_focal_user_id", "pm_user_id")
    } == {
        "U11",
        "U12",
        "U01",
        "U10",
    }
    assert prefill["next_decision_date"].startswith("2027-")
