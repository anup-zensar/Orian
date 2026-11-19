"""Orion assistant chat (FR-090): quick actions (form first), free-text keyword intents."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import OrionDraft

API = "/api/v1"
QUICK = (
    "start_gate_review",
    "assess_gate_readiness",
    "track_owner_actions",
    "draft_owner_reminders",
    "create_leadership_update",
    "create_support_model",
    "create_update_ocet",
)


def _post(client, headers, body, user="U01"):
    return client.post(f"{API}/orion/chat", json=body, headers=headers(user))


def _msgs(res):
    assert res.status_code == 200, res.text
    msgs = res.json()["messages"]
    assert msgs and all(m["generated_by"] == "Orion agent" for m in msgs)
    return msgs


def test_requires_login_and_exactly_one_input(client, headers):
    assert client.post(f"{API}/orion/chat", json={"message": "hi"}).status_code == 401
    assert _post(client, headers, {}).status_code == 400
    both = {"message": "hi", "quick_action": "start_gate_review"}
    assert _post(client, headers, both).status_code == 400
    assert _post(client, headers, {"quick_action": "nope"}).status_code == 422


def test_all_quick_actions_answer_form_first(client, headers):
    for qa in QUICK:
        msgs = _msgs(_post(client, headers, {"quick_action": qa}))
        if qa == "start_gate_review":
            assert [m["type"] for m in msgs] == ["text", "link"] and msgs[1][
                "href"
            ] == "/transitions/new"
        else:
            assert msgs[0]["type"] == "form" and msgs[0]["quick_action"] == qa
    form = _msgs(
        _post(
            client,
            headers,
            {"quick_action": "assess_gate_readiness", "context": {"transition_id": "TR-0001"}},
        )
    )[0]
    fields = {f["name"]: f for f in form["fields"]}
    assert fields["transition_id"]["default"] == "TR-0001" and fields["transition_id"]["options"]
    assert fields["gate"]["default"] == "SG4_ATD"
    scope = _msgs(_post(client, headers, {"quick_action": "create_leadership_update"}))[0]
    assert [f["name"] for f in scope["fields"]] == ["scope", "scope_id"]


def test_assess_readiness_card(client, headers):
    body = {
        "quick_action": "assess_gate_readiness",
        "form_data": {"transition_id": "TR-0001", "gate": "SG4_ATD"},
    }
    msgs = _msgs(_post(client, headers, body))
    assert (
        msgs[0]["type"] == "readiness" and msgs[0]["check"]["verdict_label"] == "Not ready for AtD"
    )
    bad = {
        "quick_action": "assess_gate_readiness",
        "form_data": {"transition_id": "TR-0001", "gate": "XX"},
    }
    assert _post(client, headers, bad).status_code == 400
    missing = {"quick_action": "assess_gate_readiness", "form_data": {"transition_id": "TR-9999"}}
    assert _post(client, headers, missing).status_code == 404


def test_track_owner_actions_table(client, headers):
    msgs = _msgs(
        _post(
            client,
            headers,
            {"quick_action": "track_owner_actions", "form_data": {"transition_id": "TR-0001"}},
        )
    )
    table = msgs[0]
    assert table["type"] == "table"
    assert [c["key"] for c in table["columns"]] == [
        "owner",
        "open_actions",
        "open_items",
        "overdue",
        "next_due",
    ]
    overdue = [r["overdue"] for r in table["rows"]]
    assert overdue == sorted(overdue, reverse=True) and table["footnote"]


def test_links_for_support_model_and_ocet(client, headers):
    for qa, href in (("create_support_model", "support-model"), ("create_update_ocet", "ocet")):
        msgs = _msgs(
            _post(client, headers, {"quick_action": qa, "form_data": {"transition_id": "TR-0001"}})
        )
        assert msgs[0]["href"] == f"/transitions/TR-0001/{href}"


def test_draft_owner_reminders_drafts_only_and_permission(client, db, headers, fresh_seed):
    body = {"quick_action": "draft_owner_reminders", "form_data": {"transition_id": "TR-0001"}}
    assert _post(client, headers, body, "U15").status_code == 403
    before = db.scalar(
        select(func.count()).select_from(OrionDraft).where(OrionDraft.status == "Sent")
    )
    msgs = _msgs(_post(client, headers, body))
    assert msgs[0]["type"] in ("drafts", "text")
    if msgs[0]["type"] == "drafts":
        assert msgs[0]["link"] == "/drafts"
    db.expire_all()
    assert (
        db.scalar(select(func.count()).select_from(OrionDraft).where(OrionDraft.status == "Sent"))
        == before
    )


def test_leadership_quick_action(client, headers, fresh_seed):
    body = {
        "quick_action": "create_leadership_update",
        "form_data": {"scope": "portfolio", "scope_id": "GCC"},
    }
    assert _post(client, headers, body, "U15").status_code == 403
    msgs = _msgs(_post(client, headers, body))
    assert msgs[0]["type"] == "leadership" and msgs[0]["update"]["title"].endswith("GCC portfolio")
    bad = {"quick_action": "create_leadership_update", "form_data": {"scope": "portfolio"}}
    assert _post(client, headers, bad).status_code == 400


def test_free_text_intents(client, headers):
    status = _msgs(_post(client, headers, {"message": "status of TR-0001"}))
    assert status[0]["type"] == "readiness" and status[0]["check"]["gate"] == "SG4_ATD"
    by_name = _msgs(_post(client, headers, {"message": "Status of the mobility knowledge agent?"}))
    assert by_name[0]["type"] == "readiness"
    ato = _msgs(_post(client, headers, {"message": "what is blocking AtO for TR-0001"}))
    assert ato[0]["check"]["gate"] == "SG6_ATO"
    owner = _msgs(
        _post(
            client,
            headers,
            {"message": "who owns S45-014", "context": {"transition_id": "TR-0001"}},
        )
    )
    assert "Fatima Khan" in owner[0]["text"] and owner[1]["type"] == "link"
    for term in ("OCET", "AtD", "AtO"):
        text = _msgs(_post(client, headers, {"message": f"what is {term}?"}))[0]
        assert text["type"] == "text" and term in text["text"]
    red = _msgs(_post(client, headers, {"message": "show red transitions"}))[0]
    assert red["type"] == "table" and any(r["id"] == "TR-0008" for r in red["rows"])
    fallback = _msgs(_post(client, headers, {"message": "blah blah"}))[0]
    assert fallback["type"] == "text" and "Assess Gate Readiness" in fallback["text"]
    many = _msgs(_post(client, headers, {"message": "status of nonexistentthing"}))[0]
    assert "could not find" in many["text"]
    ambiguous = _msgs(_post(client, headers, {"message": "status of platform"}))[0]
    assert "Several transitions match" in ambiguous["text"]


def test_chat_is_deterministic(client, headers):
    a = _post(client, headers, {"message": "show red transitions"}).json()
    b = _post(client, headers, {"message": "show red transitions"}).json()
    a_check, b_check = a["messages"], b["messages"]
    assert a_check == b_check


def test_who_owns_reads_as_a_sentence(client, headers):
    one = _msgs(
        _post(
            client,
            headers,
            {"message": "who owns S45-014", "context": {"transition_id": "TR-0001"}},
        )
    )
    assert one[0]["type"] == "text"
    assert one[0]["text"].endswith(
        "is owned by Fatima Khan (IRM) on Mobility Knowledge Agent (TR-0001)"
    )
    assert one[0]["text"].startswith("S45-014 ")
    many = _msgs(_post(client, headers, {"message": "who owns S45-014"}))
    texts = [m["text"] for m in many if m["type"] == "text"]
    assert len(texts) > 1 and all(" is owned by " in t and t.startswith("S45-014 ") for t in texts)


def test_chase_without_a_transition_returns_a_form_with_a_picker(client, headers):
    msgs = _msgs(_post(client, headers, {"message": "chase the owner of S3-019"}))
    assert msgs[0]["type"] == "text" and "S3-019" in msgs[0]["text"]
    form = next(m for m in msgs if m["type"] == "form")
    assert form["quick_action"] == "draft_owner_reminders"
    picker = next(f for f in form["fields"] if f["kind"] == "transition")
    assert picker["options"] and picker["default"] is None
    # with a transition in context the proposal flow is unchanged (no form)
    ctx = _msgs(
        _post(
            client,
            headers,
            {"message": "chase the owner of S3-019", "context": {"transition_id": "TR-0001"}},
        )
    )
    assert not any(m["type"] == "form" for m in ctx)
