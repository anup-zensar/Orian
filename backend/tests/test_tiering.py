"""BR-011 tiering rule, /tiering/propose, tier proposal / confirmation and AI profile (AC-04, FR-021)."""

from __future__ import annotations

import pytest

from app.rules.tiering import propose_tier

API = "/api/v1"


def _create(client, headers, user="U01", **overrides):
    body = {
        "name": "Tier test agent",
        "project_type": "Agentic AI",
        "portfolio": "GCC",
        "region": "Global",
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
        "or_focal_user_id": "U01",
    }
    body.update(overrides)
    res = client.post(f"{API}/transitions", json=body, headers=headers(user))
    assert res.status_code == 201, res.text
    return res.json()


# --- pure rule ---------------------------------------------------------------------------------


def test_internal_no_writes_non_sensitive_tq4_is_tier_2():
    result = propose_tier("Internal department", "No", "No", {"TQ4": True})
    assert result.tier == 2
    assert "Internal audience" in result.rationale
    assert "No write actions" in result.rationale
    assert "TQ4 = yes -> Tier 2" in result.rationale


@pytest.mark.parametrize("key", ["TQ2", "TQ3"])
def test_tq2_or_tq3_is_tier_4_regardless_of_audience(key):
    result = propose_tier("Internal department", "No", "No", {key: True, "TQ4": True})
    assert result.tier == 4
    assert f"{key} = yes -> Tier 4" in result.rationale


def test_sox_mc_is_tier_4():
    assert propose_tier("Internal department", "No", "SOX / MC", {"TQ4": True}).tier == 4


def test_external_audience_is_tier_3():
    assert propose_tier("External", "No", "No", {"TQ4": True}).tier == 3


@pytest.mark.parametrize(
    ("audience", "writes", "sensitive", "answers"),
    [
        ("Internal department", "No", "Personal sensitive", {}),
        ("Internal department", "Yes", "No", {}),
        ("Internal department", "No", "No", {"TQ1": True}),
    ],
)
def test_tier_3_triggers(audience, writes, sensitive, answers):
    assert propose_tier(audience, writes, sensitive, answers).tier == 3


def test_tq5_is_tier_1_and_beats_tq4():
    assert propose_tier("Internal department", "No", "No", {"TQ5": True, "TQ4": True}).tier == 1


def test_tier_3_beats_tq5():
    assert propose_tier("External", "No", "No", {"TQ5": True}).tier == 3


def test_default_is_tier_3():
    result = propose_tier("Internal department", "No", "No", {})
    assert result.tier == 3
    assert any("conservative default" in line for line in result.rationale)
    # the safe-looking intake answers explain how to reach Tier 2 instead of contradicting Tier 3
    assert "TQ4" in result.rationale[-1]
    assert propose_tier("Enterprise", "No", "No", {}).rationale[-1].startswith("No rule matched")


def test_missing_intake_values_are_tolerated():
    assert propose_tier(None, None, None, {"TQ4": True}).tier == 2


# --- /tiering/propose ----------------------------------------------------------------------------


def test_propose_endpoint_tier_2_with_card_and_dimensions(client, headers):
    res = client.post(
        f"{API}/tiering/propose",
        json={
            "audience": "Internal department",
            "write_actions": "No",
            "sensitive_data": "No",
            "answers": {"TQ4": True},
        },
        headers=headers("U10"),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["proposed_tier"] == 2
    assert data["tier"]["tier"] == 2 and data["tier"]["builder_persona"]
    assert len(data["dimensions"]) == 3
    assert "TQ4 = yes -> Tier 2" in data["rationale"]


def test_propose_endpoint_tier_4_when_tq2_yes(client, headers):
    res = client.post(
        f"{API}/tiering/propose",
        json={"audience": "Internal department", "answers": {"TQ2": True}},
        headers=headers(),
    )
    assert res.json()["proposed_tier"] == 4


def test_propose_endpoint_validation(client, headers):
    bad_key = client.post(
        f"{API}/tiering/propose", json={"answers": {"TQ9": True}}, headers=headers()
    )
    assert bad_key.status_code == 422
    assert any("TQ9" in r for r in bad_key.json()["reasons"])
    bad_option = client.post(
        f"{API}/tiering/propose", json={"audience": "Nobody"}, headers=headers()
    )
    assert bad_option.status_code == 422


def test_propose_requires_sign_in(client):
    assert client.post(f"{API}/tiering/propose", json={}).status_code == 401


# --- tier on a transition (AC-04) -----------------------------------------------------------------


def test_put_tier_then_only_irm_confirms(client, headers, fresh_seed):
    tid = _create(client, headers)["id"]
    url = f"{API}/transitions/{tid}/tier"

    denied = client.put(url, json={"answers": {"TQ4": True}}, headers=headers("U10"))
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only the OR focal can propose the tier"

    res = client.put(url, json={"answers": {"TQ4": True}}, headers=headers("U01"))
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["proposed_tier"] == 2 and data["status"] == "Proposed"
    assert data["proposed_by"]["id"] == "U01"
    assert data["tier"]["tier"] == 2

    detail = client.get(f"{API}/transitions/{tid}", headers=headers()).json()
    assert detail["risk_tier"] == 2 and detail["tier_status"] == "Proposed"

    for user in ("U01", "U16", "U10"):
        res = client.post(f"{url}/confirm", json={"tier": 2}, headers=headers(user))
        assert res.status_code == 403
        assert res.json()["detail"] == "Only IRM can confirm the tier"

    res = client.post(f"{url}/confirm", json={"tier": 2}, headers=headers("U14"))
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "Confirmed" and data["confirmed_tier"] == 2
    assert data["confirmed_by_irm"]["id"] == "U14"
    assert data["confirmed_by_or_focal"]["id"] == "U01"
    assert data["confirmed_at"] and data["change_reason"] is None
    detail = client.get(f"{API}/transitions/{tid}", headers=headers()).json()
    assert detail["tier_status"] == "Confirmed"

    # The OR focal may not overwrite a confirmed tier.
    again = client.put(url, json={"answers": {}}, headers=headers("U01"))
    assert again.status_code == 409
    assert "IRM must change it" in again.json()["detail"]


def test_tier_4_when_tq2_yes_via_api(client, headers, fresh_seed):
    tid = _create(client, headers)["id"]
    res = client.put(
        f"{API}/transitions/{tid}/tier",
        json={"answers": {"TQ2": True, "TQ4": True}},
        headers=headers(),
    )
    assert res.json()["proposed_tier"] == 4


def test_server_ignores_client_supplied_tier(client, headers, fresh_seed):
    tid = _create(client, headers)["id"]
    res = client.put(
        f"{API}/transitions/{tid}/tier",
        json={"answers": {"TQ4": True}, "proposed_tier": 1},
        headers=headers(),
    )
    assert res.json()["proposed_tier"] == 2


def test_change_tier_needs_reason(client, headers, fresh_seed):
    tid = _create(client, headers)["id"]
    client.put(f"{API}/transitions/{tid}/tier", json={"answers": {"TQ4": True}}, headers=headers())
    url = f"{API}/transitions/{tid}/tier/confirm"
    blank = client.post(url, json={"tier": 3, "reason": "  "}, headers=headers("U14"))
    assert blank.status_code == 422
    assert blank.json()["detail"] == "Reason required to change the tier"
    ok = client.post(url, json={"tier": 3, "reason": "Handles ticket data"}, headers=headers("U14"))
    assert ok.status_code == 200
    assert ok.json()["confirmed_tier"] == 3 and ok.json()["change_reason"] == "Handles ticket data"
    assert ok.json()["proposed_tier"] == 2


def test_tier_events_are_audited(client, headers, db, fresh_seed):
    from sqlalchemy import select

    from app.models import AuditEvent

    tid = _create(client, headers)["id"]
    client.put(f"{API}/transitions/{tid}/tier", json={"answers": {"TQ4": True}}, headers=headers())
    client.post(
        f"{API}/transitions/{tid}/tier/confirm",
        json={"tier": 3, "reason": "Handles ticket data"},
        headers=headers("U14"),
    )
    events = db.scalars(select(AuditEvent).where(AuditEvent.transition_id == tid)).all()
    by_action = {e.action: e for e in events}
    assert {"Transition created", "Tier proposed", "Tier changed"} <= set(by_action)
    assert all(e.actor_type == "Human" for e in events)
    assert "Handles ticket data" in by_action["Tier changed"].note


def test_confirm_without_proposal_is_409(client, headers, fresh_seed):
    tid = _create(client, headers)["id"]
    res = client.post(
        f"{API}/transitions/{tid}/tier/confirm", json={"tier": 2}, headers=headers("U14")
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "No tier proposed yet"


def test_tiering_is_for_ai_types_only(client, headers, fresh_seed):
    tid = _create(
        client,
        headers,
        project_type="Normal",
        audience=None,
        write_actions=None,
        sensitive_data=None,
    )["id"]
    res = client.put(f"{API}/transitions/{tid}/tier", json={"answers": {}}, headers=headers())
    assert res.status_code == 409
    assert res.json()["detail"] == "Tiering applies to AI project types only"
    assert client.get(f"{API}/transitions/{tid}/ai-profile", headers=headers()).status_code == 409


def test_unknown_transition_is_404(client, headers):
    put = client.put(f"{API}/transitions/TR-9999/tier", json={"answers": {}}, headers=headers())
    assert put.status_code == 404
    assert client.get(f"{API}/transitions/TR-9999/ai-profile", headers=headers()).status_code == 404


def test_ai_profile_roundtrip(client, headers, fresh_seed):
    tid = _create(client, headers)["id"]
    url = f"{API}/transitions/{tid}/ai-profile"
    empty = client.get(url, headers=headers()).json()
    assert empty["transition_id"] == tid and empty["hosting"] == "" and empty["updated_at"] is None

    body = {
        "infrastructure_solution": "Azure AI Foundry",
        "agentic_framework": "LangGraph",
        "multi_agent_orchestration": True,
        "number_of_users": "200",
        "agentic_workflows": "Triage then answer",
        "models_used": "gpt-4.1",
        "data_sources": "Confluence",
        "hosting": "Azure West Europe",
        "write_actions_detail": "None",
    }
    assert client.put(url, json=body, headers=headers("U01")).status_code == 200
    got = client.get(url, headers=headers("U14")).json()
    assert got["agentic_framework"] == "LangGraph" and got["multi_agent_orchestration"] is True
    assert got["updated_at"]

    assert client.put(url, json=body, headers=headers("U14")).status_code == 403


def test_seeded_flagship_profile_is_readable(client, headers):
    res = client.get(f"{API}/transitions/TR-0001/ai-profile", headers=headers())
    assert res.status_code == 200
