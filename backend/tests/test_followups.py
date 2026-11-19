"""Regression tests for the review follow-ups (R4 on an unlaunched transition, Admin sites, proposal
privacy, forged proposal payloads, human-readable audit summaries)."""

from __future__ import annotations

from app import clock
from app.domain.audit_text import describe_event
from app.domain.proposals import create_proposal
from app.models import OrionProposal, Transition
from app.rules.constants import GATE_ORDER
from app.rules.reminders import ItemFact, evaluate_r4
from tests.test_rules_reminders import _cfg, _t

API = "/api/v1"


def test_r4_ignores_a_transition_without_applicable_items():
    assert evaluate_r4(_cfg("R4"), [_t()], []) == []
    other = ItemFact(
        transition_id="TR-2",
        item_id="A",
        title="A",
        owner_user_id="U10",
        status="Complete",
        first_due_gate="SG4_ATD",
        gate_index=GATE_ORDER["SG4_ATD"],
        done_or_covered=True,
    )
    assert (
        evaluate_r4(_cfg("R4"), [_t()], [other]) == []
    )  # items of another transition do not count


def test_r4_draft_not_created_for_a_transition_that_is_not_launched(client, headers, fresh_seed):
    body = {
        "name": "Not launched agent",
        "project_type": "Agentic AI",
        "portfolio": "GCC",
        "region": "Global",
        "market": "Multi-market",
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
    }
    created = client.post(f"{API}/transitions", json=body, headers=headers("U01"))
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    run = client.post(f"{API}/reminders/run", json={"transition_id": tid}, headers=headers("U01"))
    assert run.status_code == 200, run.text
    drafts = client.get(f"{API}/orion/drafts?status=Draft", headers=headers("U01")).json()
    assert [d for d in drafts if d["transition_id"] == tid and d.get("rule_id") == "R4"] == []


def test_admin_cannot_change_sites(client, headers, db, fresh_seed):
    t = db.get(Transition, "TR-0007")
    assert t.portfolio == "Retail Site Systems"
    before = list(t.sites or [])
    res = client.patch(
        f"{API}/transitions/TR-0007",
        json={"sites": [{"site_id": "HACK1", "site_key": "HK"}]},
        headers=headers("U16"),
    )
    assert res.status_code == 403, res.text
    db.expire_all()
    assert list(db.get(Transition, "TR-0007").sites or []) == before


def test_focal_can_still_change_sites(client, headers, fresh_seed):
    res = client.patch(
        f"{API}/transitions/TR-0007",
        json={"sites": [{"site_id": "SITE9", "site_key": "S9"}]},
        headers=headers("U05"),
    )
    assert res.status_code == 200, res.text


def _prefill_payload() -> dict:
    return {
        "prefill": {"name": "Private prefill"},
        "fields": [],
        "missing_fields": [],
        "ambiguous_fields": [],
        "source": "text",
    }


def test_create_transition_prefill_is_private_to_its_creator(client, headers, db, fresh_seed):
    row = create_proposal(
        db,
        kind="create_transition",
        title="Start transition",
        payload=_prefill_payload(),
        transition_id=None,
        created_by="U01",
    )
    db.commit()
    assert client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U01")).status_code == 200
    assert client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U02")).status_code == 404
    assert (
        client.post(f"{API}/orion/proposals/{row.id}/dismiss", headers=headers("U02")).status_code
        == 404
    )
    admin = client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U16"))
    assert admin.status_code == 200 and admin.json()["can_accept"] is False  # read-only
    for action in ("dismiss", "accept"):
        res = client.post(f"{API}/orion/proposals/{row.id}/{action}", headers=headers("U16"))
        assert res.status_code == 403, res.text
    db.expire_all()
    assert db.get(OrionProposal, row.id).status == "Open"


def test_unassigned_user_cannot_put_a_proposal_in_another_focals_list(
    client, headers, db, fresh_seed
):
    # U04 is the OR focal of another transition, not of TR-0002 (U02's).
    row = create_proposal(
        db,
        kind="draft_chaser",
        title="Chase FW-016",
        payload={"item_ids": ["FW-016"]},
        transition_id="TR-0002",
        created_by="U04",
    )
    own = create_proposal(
        db,
        kind="draft_chaser",
        title="Chase FW-017",
        payload={"item_ids": ["FW-017"]},
        transition_id="TR-0002",
        created_by="U02",
    )
    db.commit()
    victim = client.get(f"{API}/orion/proposals?transition_id=TR-0002", headers=headers("U02"))
    ids = {p["id"] for p in victim.json()}
    assert own.id in ids and row.id not in ids
    assert client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U02")).status_code == 404
    mine = client.get(f"{API}/orion/proposals/{row.id}", headers=headers("U04"))
    assert mine.status_code == 200 and mine.json()["can_accept"] is False


def test_forged_applicability_payload_is_refused_not_a_500(client, headers, db, fresh_seed):
    try:
        create_proposal(
            db,
            kind="accept_applicability",
            title="x",
            payload={"decisions": [{"item_id": "FW-001", "applies": False}]},
            transition_id="TR-0001",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("a decision with applies=false must be rejected at creation")
    # A row written straight to the DB (no public path does this) must not crash accept.
    raw = OrionProposal(
        transition_id="TR-0001",
        kind="accept_applicability",
        title="forged",
        payload={"decisions": [{"item_id": "FW-001", "applies": False}]},
        status="Open",
        created_at=clock.now(),
    )
    db.add(raw)
    db.commit()
    res = client.post(f"{API}/orion/proposals/{raw.id}/accept", headers=headers("U01"))
    assert res.status_code == 422, res.text


def test_audit_summary_is_human_readable(client, headers, fresh_seed):
    assert describe_event("OrionDraft", "1", "drafted") == "Drafted Orion draft 1"
    assert (
        describe_event("ApprovalRequest", "APR-0001", "step_activated")
        == "Activated step of approval request APR-0001"
    )
    assert describe_event("TransitionItem", "221", "updated") == "Updated checklist item 221"
    dash = client.get(f"{API}/dashboard", headers=headers("U01")).json()
    assert dash["recent_activity"]
    for event in dash["recent_activity"]:
        assert event["summary"] and "TransitionItem" not in event["summary"]
        assert "_" not in event["summary"]
