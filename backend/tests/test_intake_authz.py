"""Per-transition access on intake, tiering, scope and AI profile (review findings BE#1, BE#2, BE#9).

U01 Asha Menon is the OR focal of TR-0001; U02 Rahul Iyer is the OR focal of TR-0002 and must be
refused on TR-0001. A second IRM is created in the test to prove that confirming the tier belongs to
the IRM assigned to the transition, not to any IRM.
"""

from __future__ import annotations

from app.models import Transition, User

API = "/api/v1"
T = "TR-0001"


def _body(**overrides):
    body = {
        "name": "Authz test agent",
        "project_type": "Agentic AI",
        "portfolio": "GCC",
        "region": "Global",
        "market": "Multi-market",
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
    }
    body.update(overrides)
    return body


def _create(client, headers, user="U01", **overrides):
    return client.post(f"{API}/transitions", json=_body(**overrides), headers=headers(user))


def _new_transition(client, headers) -> str:
    res = _create(client, headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _second_irm(db) -> str:
    db.add(User(id="U90", name="Second Irm", email="second.irm@example.test", role="IRM"))
    db.commit()
    return "U90"


# --- create ---------------------------------------------------------------------------------------


def test_or_focal_creating_defaults_to_self(client, headers, fresh_seed):
    res = _create(client, headers)
    assert res.status_code == 201, res.text
    assert res.json()["or_focal"]["id"] == "U01"


def test_or_focal_cannot_create_for_another_focal(client, headers, fresh_seed):
    res = _create(client, headers, or_focal_user_id="U02")
    assert res.status_code == 403
    assert "pick yourself" in res.json()["detail"]


def test_pm_creates_with_a_chosen_focal(client, headers, fresh_seed):
    res = _create(client, headers, user="U10", or_focal_user_id="U02")
    assert res.status_code == 201, res.text
    assert res.json()["or_focal"]["id"] == "U02"


def test_pm_must_pick_a_focal(client, headers, fresh_seed):
    res = _create(client, headers, user="U10")
    assert res.status_code == 422
    assert any("OR focal" in r for r in res.json()["reasons"])


# --- patch ----------------------------------------------------------------------------------------


def test_other_focal_cannot_edit_the_transition(client, headers, fresh_seed):
    res = client.patch(f"{API}/transitions/{T}", json={"blocker_note": "x"}, headers=headers("U02"))
    assert res.status_code == 403
    assert "Asha Menon" in res.json()["detail"]


def test_assigned_focal_can_edit(client, headers, fresh_seed):
    res = client.patch(f"{API}/transitions/{T}", json={"blocker_note": "x"}, headers=headers("U01"))
    assert res.status_code == 200, res.text


def test_pm_of_the_transition_cannot_edit(client, headers, fresh_seed):
    res = client.patch(f"{API}/transitions/{T}", json={"blocker_note": "x"}, headers=headers("U10"))
    assert res.status_code == 403


def test_focal_cannot_reassign_irm_but_admin_can(client, headers, db, fresh_seed):
    new_irm = _second_irm(db)
    url = f"{API}/transitions/{T}"
    denied = client.patch(url, json={"irm_user_id": new_irm}, headers=headers("U01"))
    assert denied.status_code == 403
    assert "Only an Admin" in denied.json()["detail"]
    ok = client.patch(url, json={"irm_user_id": new_irm}, headers=headers("U16"))
    assert ok.status_code == 200, ok.text
    assert ok.json()["roles"]["irm"]["id"] == new_irm


def test_focal_cannot_hand_the_transition_away(client, headers, fresh_seed):
    res = client.patch(
        f"{API}/transitions/{T}", json={"or_focal_user_id": "U02"}, headers=headers("U01")
    )
    assert res.status_code == 403


def test_focal_can_reassign_pm(client, headers, fresh_seed):
    res = client.patch(f"{API}/transitions/{T}", json={"pm_user_id": "U10"}, headers=headers("U01"))
    assert res.status_code == 200, res.text


def test_admin_reassigns_people_but_edits_no_workflow_data(client, headers, fresh_seed):
    """R-01: the Admin re-assigns people and configures; dates, notes, gate target, description and
    the tier inputs belong to the OR focal of the transition."""
    url = f"{API}/transitions/{T}"
    assert client.patch(url, json={"pm_user_id": "U10"}, headers=headers("U16")).status_code == 200
    for body in (
        {"name": "Renamed"},
        {"next_decision_date": "2027-06-01"},
        {"blocker_note": "admin wrote this"},
        {"target_gate": "SG0-SG2"},
        {"market": "X"},
        {"description": "admin"},
        {"audience": "External"},
    ):
        res = client.patch(url, json=body, headers=headers("U16"))
        assert res.status_code == 403, (body, res.text)
    # the OR focal still can
    assert client.patch(url, json={"name": "Renamed"}, headers=headers("U01")).status_code == 200


def test_tier_inputs_are_locked_after_irm_confirmation(client, headers, fresh_seed):
    tid = _new_transition(client, headers)
    url = f"{API}/transitions/{tid}"
    assert (
        client.put(f"{url}/tier", json={"answers": {}}, headers=headers("U01")).status_code == 200
    )
    confirm = client.post(f"{url}/tier/confirm", json={"tier": 3}, headers=headers("U14"))
    assert confirm.status_code == 200, confirm.text
    res = client.patch(url, json={"audience": "External"}, headers=headers("U01"))
    assert res.status_code == 409, res.text
    assert "IRM" in " ".join(res.json()["reasons"])
    # descriptive fields stay editable
    assert client.patch(url, json={"market": "UK"}, headers=headers("U01")).status_code == 200


def test_tier_inputs_before_confirmation_clear_the_proposal(client, headers, fresh_seed):
    tid = _new_transition(client, headers)
    url = f"{API}/transitions/{tid}"
    assert (
        client.put(f"{url}/tier", json={"answers": {}}, headers=headers("U01")).status_code == 200
    )
    res = client.patch(url, json={"audience": "External"}, headers=headers("U01"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tier_status"] is None and body["risk_tier"] is None
    assert body["tier"] is None or body["tier"]["proposed_tier"] is None
    # nothing to confirm until the focal proposes again
    nothing = client.post(f"{url}/tier/confirm", json={"tier": 3}, headers=headers("U14"))
    assert nothing.status_code == 409
    again = client.put(f"{url}/tier", json={"answers": {}}, headers=headers("U01"))
    assert again.status_code == 200 and again.json()["proposed_tier"] == 3


def test_closed_transition_is_409_for_the_focal(client, headers, db, fresh_seed):
    tid = _new_transition(client, headers)
    db.get(Transition, tid).status = "Closed"
    db.commit()
    res = client.patch(f"{API}/transitions/{tid}", json={"name": "x"}, headers=headers("U01"))
    assert res.status_code == 409


def test_patch_text_limit(client, headers, fresh_seed):
    res = client.patch(
        f"{API}/transitions/{T}", json={"blocker_note": "x" * 4001}, headers=headers("U01")
    )
    assert res.status_code == 422


# --- autonomous mode, tier, AI profile, scope -----------------------------------------------------


def test_autonomous_mode_only_by_the_assigned_focal(client, headers, fresh_seed):
    url = f"{API}/transitions/{T}/autonomous-mode"
    assert client.post(url, json={"enabled": True}, headers=headers("U02")).status_code == 403
    assert client.post(url, json={"enabled": True}, headers=headers("U01")).status_code == 200


def test_tier_proposal_only_by_the_assigned_focal(client, headers, fresh_seed):
    tid = _new_transition(client, headers)
    url = f"{API}/transitions/{tid}/tier"
    res = client.put(url, json={"answers": {}}, headers=headers("U02"))
    assert res.status_code == 403
    assert "Asha Menon" in res.json()["detail"]
    assert client.put(url, json={"answers": {}}, headers=headers("U01")).status_code == 200


def test_tier_confirmation_only_by_the_assigned_irm(client, headers, db, fresh_seed):
    tid = _new_transition(client, headers)
    other_irm = _second_irm(db)
    url = f"{API}/transitions/{tid}"
    assert (
        client.put(f"{url}/tier", json={"answers": {}}, headers=headers("U01")).status_code == 200
    )
    denied = client.post(f"{url}/tier/confirm", json={"tier": 3}, headers=headers(other_irm))
    assert denied.status_code == 403
    assert "Fatima Khan" in denied.json()["detail"]
    assert (
        client.post(f"{url}/tier/confirm", json={"tier": 3}, headers=headers("U14")).status_code
        == 200
    )


def test_ai_profile_only_by_assigned_people(client, headers, fresh_seed):
    url = f"{API}/transitions/{T}/ai-profile"
    body = {"hosting": "Azure"}
    assert client.put(url, json=body, headers=headers("U02")).status_code == 403
    assert client.put(url, json=body, headers=headers("U11")).status_code == 200
    assert client.put(url, json=body, headers=headers("U01")).status_code == 200


def test_scope_and_launch_only_by_the_assigned_focal(client, headers, fresh_seed):
    tid = _new_transition(client, headers)
    url = f"{API}/transitions/{tid}"
    assert (
        client.put(f"{url}/tier", json={"answers": {}}, headers=headers("U01")).status_code == 200
    )
    assert (
        client.put(f"{url}/scope", json={"decisions": []}, headers=headers("U02")).status_code
        == 403
    )
    assert client.post(f"{url}/launch-assessment", headers=headers("U02")).status_code == 403
    assert (
        client.put(f"{url}/scope", json={"decisions": []}, headers=headers("U01")).status_code
        == 200
    )
    assert client.post(f"{url}/launch-assessment", headers=headers("U01")).status_code == 200


# --- BE#9: "No" after launch ----------------------------------------------------------------------


def _launched(client, headers) -> tuple[str, dict]:
    tid = _new_transition(client, headers)
    url = f"{API}/transitions/{tid}"
    client.put(f"{url}/tier", json={"answers": {}}, headers=headers("U01"))
    client.post(f"{url}/launch-assessment", headers=headers("U01"))
    scope = client.get(f"{url}/scope", headers=headers("U01")).json()
    return tid, scope


def test_no_after_launch_needs_a_reason_and_audits_each_item(client, headers, db, fresh_seed):
    from sqlalchemy import select

    from app.models import AuditEvent

    tid, scope = _launched(client, headers)
    row = next(r for r in [*scope["golden_set"], *scope["common"]] if not r["locked"])
    url = f"{API}/transitions/{tid}/scope"
    no_reason = client.put(
        url, json={"decisions": [{"item_id": row["id"], "applies": "No"}]}, headers=headers("U01")
    )
    assert no_reason.status_code == 422
    ok = client.put(
        url,
        json={"decisions": [{"item_id": row["id"], "applies": "No", "reason": "Not in scope"}]},
        headers=headers("U01"),
    )
    assert ok.status_code == 200, ok.text
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.entity == "TransitionItem"
        )
    ).all()
    assert events and events[-1].before["applicability"] != events[-1].after["applicability"]


def test_no_after_launch_refused_for_items_with_evidence(client, headers, fresh_seed):
    tid, scope = _launched(client, headers)
    row = next(r for r in [*scope["golden_set"], *scope["common"]] if not r["locked"])
    evidence = client.post(
        f"{API}/transitions/{tid}/evidence",
        data={
            "title": "Link",
            "type": "Link",
            "url": "https://example.com/doc",
            "item_id": row["id"],
        },
        headers=headers("U01"),
    )
    if evidence.status_code != 201:  # the row may not be an applicable item yet (To confirm)
        client.put(
            f"{API}/transitions/{tid}/scope",
            json={"decisions": [{"item_id": row["id"], "applies": "Yes"}]},
            headers=headers("U01"),
        )
        evidence = client.post(
            f"{API}/transitions/{tid}/evidence",
            data={
                "title": "Link",
                "type": "Link",
                "url": "https://example.com/doc",
                "item_id": row["id"],
            },
            headers=headers("U01"),
        )
    assert evidence.status_code == 201, evidence.text
    res = client.put(
        f"{API}/transitions/{tid}/scope",
        json={"decisions": [{"item_id": row["id"], "applies": "No", "reason": "Changed mind"}]},
        headers=headers("U01"),
    )
    assert res.status_code == 409, res.text
    assert row["id"] in " ".join(res.json()["reasons"])
