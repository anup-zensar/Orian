"""Intake API: create / get / patch, validations (AC-05), ServiceNow lookup, autonomous mode (FR-020)."""

from __future__ import annotations

API = "/api/v1"


def _body(**overrides):
    body = {
        "name": "Intake test agent",
        "project_type": "Agentic AI",
        "portfolio": "GCC",
        "region": "Global",
        "market": "Multi-market",
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
        "or_focal_user_id": "U01",
        "pm_user_id": "U10",
        "architect_user_id": "U11",
        "olm_user_id": "U12",
        "irm_user_id": "U14",
    }
    body.update(overrides)
    return body


def _post(client, headers, user="U01", **overrides):
    return client.post(f"{API}/transitions", json=_body(**overrides), headers=headers(user))


# --- create ---------------------------------------------------------------------------------------


def test_create_returns_full_detail(client, headers, fresh_seed):
    res = _post(client, headers, name="  My agent  ", servicenow_project_id="prj0052210")
    assert res.status_code == 201, res.text
    d = res.json()
    assert d["id"] == "TR-0019"
    assert d["name"] == "My agent" and d["servicenow_project_id"] == "PRJ0052210"
    assert d["current_gate"] == "SG0" and d["status"] == "Active"
    assert d["autonomous_mode"] is False and d["assessment_launched"] is False
    assert d["item_counts"] is None and d["tier"] is None and d["risk_tier"] is None
    assert d["requires_tiering"] is True
    assert d["flavour_label"] == "Agentic AI · GCC · Global"
    assert d["rag"] == "Grey"
    assert d["roles"]["or_focal"] == {"id": "U01", "name": "Asha Menon"}
    assert d["roles"]["irm"]["id"] == "U14"
    assert d["created_by"]["id"] == "U01" and d["created_at"]
    assert [g["code"] for g in d["gates"]][:2] == ["SG0", "SG2"]
    assert [g["state"] for g in d["gates"]][:2] == ["current", "upcoming"]
    assert [lens["lens"] for lens in d["lenses"]] == ["Business", "Technical", "Compliance"]
    # next id continues the sequence
    assert _post(client, headers, name="Second").json()["id"] == "TR-0020"


def test_create_permissions(client, headers, fresh_seed):
    assert _post(client, headers, user="U10").status_code == 201  # PM
    assert _post(client, headers, user="U16").status_code == 201  # Admin
    for user in ("U11", "U12", "U13", "U14", "U15"):
        res = _post(client, headers, user=user)
        assert res.status_code == 403, user
        assert res.json()["detail"] == "Only an OR focal, PM or Admin can create a transition"


def test_create_defaults_roles_when_omitted(client, headers, fresh_seed):
    body = _body()
    for key in ("pm_user_id", "architect_user_id", "olm_user_id", "irm_user_id"):
        del body[key]
    res = client.post(f"{API}/transitions", json=body, headers=headers())
    roles = res.json()["roles"]
    assert (
        roles["pm"]["id"],
        roles["architect"]["id"],
        roles["olm"]["id"],
        roles["irm"]["id"],
    ) == (
        "U10",
        "U11",
        "U12",
        "U14",
    )


def test_create_validation_reasons(client, headers, fresh_seed):
    res = _post(
        client,
        headers,
        name="   ",
        project_type="Hybrid",
        portfolio="Nowhere",
        region="Mars",
        audience=None,
        target_gate="Never",
        pm_user_id="U01",
        irm_user_id="U99",
    )
    assert res.status_code == 422
    body = res.json()
    assert body["detail"] == "Validation failed"
    reasons = " | ".join(body["reasons"])
    for fragment in (
        "name",
        "Project type 'Hybrid'",
        "Portfolio 'Nowhere'",
        "Region 'Mars'",
        "target_gate 'Never'",
        "Project manager",
        "IRM: unknown user",
    ):
        assert fragment.lower() in reasons.lower(), fragment


def test_ai_types_require_intake_answers(client, headers, fresh_seed):
    for project_type in ("Agentic AI", "Combined"):
        res = _post(
            client,
            headers,
            project_type=project_type,
            audience=None,
            write_actions=None,
            sensitive_data=None,
        )
        assert res.status_code == 422
        assert len(res.json()["reasons"]) == 3
    ok = _post(
        client,
        headers,
        project_type="Normal",
        audience=None,
        write_actions=None,
        sensitive_data=None,
    )
    assert ok.status_code == 201


def test_retail_requires_a_complete_site_row_ac05(client, headers, fresh_seed):
    retail = {"portfolio": "Retail Site Systems"}
    none = _post(client, headers, **retail)
    assert none.status_code == 422
    assert any("at least one site" in r for r in none.json()["reasons"])

    blank_only = _post(client, headers, sites=[{"site_id": " ", "site_key": ""}], **retail)
    assert blank_only.status_code == 422

    half = _post(client, headers, sites=[{"site_id": "S1", "site_key": ""}], **retail)
    assert half.status_code == 422
    assert any("Site row 1" in r for r in half.json()["reasons"])

    ok = _post(
        client,
        headers,
        sites=[
            {"site_id": " S1 ", "site_key": " K1 "},
            {"site_id": "", "site_key": ""},
            {"site_id": "S2", "site_key": "K2"},
        ],
        **retail,
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["sites"] == [
        {"site_id": "S1", "site_key": "K1"},
        {"site_id": "S2", "site_key": "K2"},
    ]


def test_sites_ignored_for_other_portfolios(client, headers, fresh_seed):
    res = _post(client, headers, sites=[{"site_id": "S1", "site_key": "K1"}])
    assert res.status_code == 201
    assert res.json()["sites"] == []


# --- get -----------------------------------------------------------------------------------------


def test_get_unknown_is_404(client, headers):
    res = client.get(f"{API}/transitions/TR-9999", headers=headers())
    assert res.status_code == 404
    assert res.json()["detail"] == "Transition not found"


def test_flagship_detail_fields(client, headers):
    res = client.get(f"{API}/transitions/TR-0001", headers=headers("U15"))
    assert res.status_code == 200
    d = res.json()
    assert d["name"] == "Mobility Knowledge Agent" and d["is_flagship"] is True
    assert d["flavour_label"] == "Agentic AI · GCC · Global"
    assert d["requires_tiering"] is True and d["assessment_launched"] is True
    assert d["current_gate"] == "SG4_ATD" and d["current_gate_short"] == "AtD"
    assert d["risk_tier"] == 2 and d["tier_status"] == "Confirmed"
    assert d["tier"]["confirmed_tier"] == 2 and d["tier"]["status"] == "Confirmed"
    assert d["checklist_banner"] is None
    assert d["roles"]["or_focal"]["id"] == "U01"
    assert d["roles"]["pm"]["id"] == "U10" and d["roles"]["architect"]["id"] == "U11"
    assert d["roles"]["olm"]["id"] == "U12" and d["roles"]["irm"]["id"] == "U14"
    counts = d["item_counts"]
    assert counts["framework"] == 72 and counts["ai_applicable"] + counts["ai_excluded"] == 216
    assert counts["total"] > 0
    assert [g["state"] for g in d["gates"]] == [
        "done",
        "done",
        "done",
        "current",
        "upcoming",
        "upcoming",
        "upcoming",
    ]
    assert [g["type"] for g in d["gates"]][3] == "decision"
    lenses = {lens["lens"]: lens for lens in d["lenses"]}
    assert lenses["Compliance"]["owner_label"] == "IRM"
    assert lenses["Business"]["question"]
    assert all(lens["scope"] >= lens["done"] for lens in lenses.values())
    assert d["lens_readiness"]["Compliance"] == lenses["Compliance"]["readiness_pct"]
    assert d["overall_readiness"] > 0


# --- patch ---------------------------------------------------------------------------------------


def test_patch_before_launch_changes_only_fields(client, headers, fresh_seed):
    tid = _post(client, headers).json()["id"]
    res = client.patch(
        f"{API}/transitions/{tid}",
        json={"name": "Renamed", "market": "UK", "description": "Hello", "blocker_note": "Waiting"},
        headers=headers(),
    )
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["name"] == "Renamed" and d["market"] == "UK" and d["blocker_note"] == "Waiting"
    assert d["item_counts"] is None


def test_patch_permissions_and_errors(client, headers, fresh_seed):
    tid = _post(client, headers).json()["id"]
    url = f"{API}/transitions/{tid}"
    assert client.patch(url, json={"name": "x"}, headers=headers("U14")).status_code == 403
    assert client.patch(f"{API}/transitions/TR-9999", json={}, headers=headers()).status_code == 404
    bad = client.patch(url, json={"region": "Mars", "audience": "Everyone"}, headers=headers())
    assert bad.status_code == 422 and len(bad.json()["reasons"]) == 2
    # required fields cannot be nulled; optional fields can be cleared
    assert client.patch(url, json={"portfolio": None}, headers=headers()).status_code == 422
    cleared = client.patch(
        url, json={"next_decision_date": None, "market": None}, headers=headers()
    )
    assert cleared.status_code == 200


def test_patch_retail_requires_sites(client, headers, fresh_seed):
    tid = _post(client, headers).json()["id"]
    url = f"{API}/transitions/{tid}"
    res = client.patch(url, json={"portfolio": "Retail Site Systems"}, headers=headers())
    assert res.status_code == 422
    ok = client.patch(
        url,
        json={"portfolio": "Retail Site Systems", "sites": [{"site_id": "A", "site_key": "B"}]},
        headers=headers(),
    )
    assert ok.status_code == 200 and ok.json()["sites"] == [{"site_id": "A", "site_key": "B"}]
    back = client.patch(url, json={"portfolio": "GCC"}, headers=headers())
    assert back.json()["sites"] == []


def test_patch_closed_transition_is_409(client, headers, db, fresh_seed):
    from app.models import Transition

    tid = _post(client, headers).json()["id"]
    t = db.get(Transition, tid)
    t.status = "Closed"
    db.commit()
    res = client.patch(f"{API}/transitions/{tid}", json={"name": "x"}, headers=headers())
    assert res.status_code == 409
    assert res.json()["detail"] == "Transition is closed"


def test_patch_on_seeded_row_without_intake_answers_is_not_blocked(client, headers, fresh_seed):
    res = client.patch(
        f"{API}/transitions/TR-0002",
        json={"blocker_note": "Waiting for vendor"},
        headers=headers("U02"),
    )
    assert res.status_code == 200, res.text


# --- autonomous mode -----------------------------------------------------------------------------


def test_autonomous_mode_toggle(client, headers, db, fresh_seed):
    from sqlalchemy import select

    from app.models import AuditEvent

    url = f"{API}/transitions/TR-0001/autonomous-mode"
    denied = client.post(url, json={"enabled": True}, headers=headers("U10"))
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only the OR focal can change autonomous mode"
    assert (
        client.post(
            f"{API}/transitions/TR-9999/autonomous-mode", json={"enabled": True}, headers=headers()
        ).status_code
        == 404
    )

    on = client.post(url, json={"enabled": True}, headers=headers("U01"))
    assert on.status_code == 200 and on.json()["autonomous_mode"] is True
    again = client.post(url, json={"enabled": True}, headers=headers("U01"))
    assert again.json()["autonomous_mode"] is True
    off = client.post(url, json={"enabled": False}, headers=headers("U01"))
    assert off.json()["autonomous_mode"] is False

    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == "TR-0001", AuditEvent.action.like("Autonomous mode%")
        )
    ).all()
    assert sorted(e.action for e in events) == ["Autonomous mode off", "Autonomous mode on"]
    assert {e.actor_type for e in events} == {"Human"}


# --- ServiceNow ----------------------------------------------------------------------------------


def test_servicenow_lookup(client, headers):
    res = client.get(f"{API}/integrations/servicenow/projects/ prj0052210 ", headers=headers("U15"))
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["project_id"] == "PRJ0052210" and d["name"] == "SMSM Photo Capture"
    assert d["project_type"] == "Agentic AI" and d["portfolio"] == "Retail Site Systems"
    assert d["region"] == "Europe & South Africa" and d["market"] == "UK"
    assert d["investment_type"] == "Change" and d["delivery_method"] == "AI / Agentic"
    assert d["pm_name"] == "Daniel Brooks" and d["pm_user_id"] == "U10"
    other = client.get(f"{API}/integrations/servicenow/projects/PRJ0049920", headers=headers())
    assert other.json()["project_type"] == "Normal"


def test_servicenow_unknown_project(client, headers):
    res = client.get(f"{API}/integrations/servicenow/projects/PRJ0000000", headers=headers())
    assert res.status_code == 404
    assert res.json()["detail"] == "Not found in ServiceNow (mock) – enter manually"
    assert client.get(f"{API}/integrations/servicenow/projects/PRJ0049920").status_code == 401
