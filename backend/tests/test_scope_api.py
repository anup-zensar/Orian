"""Scope page, launch (BR-010) and re-assembly via the API (FR-022; AC-03; storyline step 3)."""

from __future__ import annotations

from collections import Counter

import pytest
from sqlalchemy import select

from app.models import AuditEvent, PlaybookItem, TransitionItem

API = "/api/v1"


def _create(client, headers, user="U01", **overrides):
    body = {
        "name": "Scope test",
        "project_type": "Normal",
        "portfolio": "GCC",
        "region": "Global",
        "or_focal_user_id": "U01",
        "pm_user_id": "U10",
        "architect_user_id": "U11",
        "olm_user_id": "U12",
        "irm_user_id": "U14",
    }
    body.update(overrides)
    res = client.post(f"{API}/transitions", json=body, headers=headers(user))
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_ai(client, headers, **overrides):
    fields = {
        "project_type": "Agentic AI",
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
    }
    fields.update(overrides)
    return _create(client, headers, **fields)


def _propose(client, headers, tid, answers=None):
    res = client.put(
        f"{API}/transitions/{tid}/tier",
        json={"answers": answers if answers is not None else {"TQ4": True}},
        headers=headers("U01"),
    )
    assert res.status_code == 200, res.text
    return res.json()


def _scope(client, headers, tid, user="U01"):
    res = client.get(f"{API}/transitions/{tid}/scope", headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _launch(client, headers, tid, user="U01"):
    return client.post(f"{API}/transitions/{tid}/launch-assessment", headers=headers(user))


def _items(db, tid):
    db.expire_all()
    rows = db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid)).all()
    return {r.playbook_item_id: r for r in rows}


def _by_source(db, tid):
    items = _items(db, tid)
    sources = {p.id: p.source for p in db.scalars(select(PlaybookItem))}
    return Counter((sources[i], r.applicability) for i, r in items.items())


# --- scope page ----------------------------------------------------------------------------------


def test_scope_before_launch_normal(client, headers, fresh_seed):
    tid = _create(client, headers)
    s = _scope(client, headers, tid, user="U15")
    assert s["launched"] is False and s["portfolio"] == "GCC"
    assert len(s["focus_areas"]) == 4 and s["tier_banner"] is None
    assert [r["id"] for r in s["golden_set"]] == [f"GCC-0{n}" for n in range(1, 6)]
    row = s["golden_set"][0]
    assert row["type"] == "Portfolio" and row["applies"] == "To confirm" and row["locked"] is False
    assert row["gate_short"] == "SG0–SG2" and row["lens"] == "Technical"
    assert [r["id"] for r in s["common"]] == ["ALL-01", "ALL-02"]
    all01, all02 = s["common"]
    assert all01["type"] == "Common" and all01["applies"] == "Yes" and all01["locked"] is True
    assert all02["applies"] == "To confirm" and all02["locked"] is False
    c = s["counts"]
    assert c["framework"] == 72 and c["ai_applicable"] == 0 and c["ai_excluded"] == 0
    assert c["golden_set_applies"] == 0 and c["golden_set_to_confirm"] == 5 and c["common"] == 2
    assert c["total"] == 72 + 1  # framework + ALL-01
    assert {r["item_id"] for r in s["recommendations"]} == {r["id"] for r in s["golden_set"]} | {
        "ALL-02"
    }
    for rec in s["recommendations"]:
        assert rec["recommendation"] in ("Yes", "No") and rec["reason"]


def test_scope_recommendations_are_deterministic_and_all02_follows_audience(
    client, headers, fresh_seed
):
    internal = _create_ai(client, headers)
    external = _create_ai(client, headers, audience="External")
    rec_internal = {r["item_id"]: r for r in _scope(client, headers, internal)["recommendations"]}
    rec_external = {r["item_id"]: r for r in _scope(client, headers, external)["recommendations"]}
    assert rec_internal["ALL-02"]["recommendation"] == "No"
    assert rec_external["ALL-02"]["recommendation"] == "Yes"
    again = {r["item_id"]: r for r in _scope(client, headers, internal)["recommendations"]}
    assert again == rec_internal


def test_scope_unknown_transition_404(client, headers):
    assert client.get(f"{API}/transitions/TR-9999/scope", headers=headers()).status_code == 404


def test_scope_tier_banner_states(client, headers, fresh_seed):
    tid = _create_ai(client, headers)
    assert _scope(client, headers, tid)["tier_banner"] == {
        "tier": None,
        "status": None,
        "text": "Tier not proposed yet",
    }
    _propose(client, headers, tid)
    s = _scope(client, headers, tid)
    assert (
        s["tier_banner"]["text"] == "Checklist based on proposed Tier 2 — confirm tier to finalise"
    )
    assert s["counts"]["ai_applicable"] == 208 and s["counts"]["ai_excluded"] == 8
    client.post(f"{API}/transitions/{tid}/tier/confirm", json={"tier": 2}, headers=headers("U14"))
    banner = _scope(client, headers, tid)["tier_banner"]
    assert banner == {
        "tier": 2,
        "status": "Confirmed",
        "text": "Checklist based on confirmed Tier 2",
    }


def test_scope_without_tier_all_ai_items_apply(client, headers, fresh_seed):
    tid = _create_ai(client, headers)
    c = _scope(client, headers, tid)["counts"]
    assert c["ai_applicable"] == 216 and c["ai_excluded"] == 0


def test_flagship_scope_after_launch(client, headers):
    s = _scope(client, headers, "TR-0001")
    assert s["launched"] is True
    assert s["counts"]["framework"] == 72
    assert s["counts"]["ai_applicable"] == 208 and s["counts"]["ai_excluded"] == 8
    assert s["tier_banner"]["status"] == "Confirmed"
    assert all(r["applies"] == "Yes" for r in s["golden_set"])  # A-29


# --- decisions -----------------------------------------------------------------------------------


def test_update_scope_before_launch_stores_decisions(client, headers, fresh_seed):
    tid = _create(client, headers)
    url = f"{API}/transitions/{tid}/scope"
    body = {
        "decisions": [
            {"item_id": "GCC-01", "applies": "Yes"},
            {"item_id": "GCC-02", "applies": "No", "reason": "Out of scope"},
            {"item_id": "ALL-02", "applies": "No", "reason": "No customers"},
        ]
    }
    res = client.put(url, json=body, headers=headers("U01"))
    assert res.status_code == 200, res.text
    s = res.json()
    rows = {r["id"]: r for r in s["golden_set"] + s["common"]}
    assert rows["GCC-01"]["applies"] == "Yes"
    assert rows["GCC-02"]["applies"] == "No" and rows["GCC-02"]["reason"] == "Out of scope"
    assert rows["GCC-03"]["applies"] == "To confirm"
    assert s["counts"]["golden_set_applies"] == 1 and s["counts"]["golden_set_to_confirm"] == 3
    assert s["counts"]["total"] == 72 + 1 + 1
    pending = {r["item_id"] for r in s["recommendations"]}
    assert "GCC-01" not in pending and "GCC-03" in pending


def test_update_scope_permissions_and_validation(client, headers, fresh_seed):
    tid = _create(client, headers)
    url = f"{API}/transitions/{tid}/scope"
    ok = {"decisions": [{"item_id": "GCC-01", "applies": "Yes"}]}
    denied = client.put(url, json=ok, headers=headers("U10"))
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only the OR focal can confirm scope and applicability"
    assert (
        client.put(f"{API}/transitions/TR-9999/scope", json=ok, headers=headers()).status_code
        == 404
    )

    unknown = client.put(
        url,
        json={
            "decisions": [
                {"item_id": "EMOB-01", "applies": "Yes"},
                {"item_id": "FW-001", "applies": "No"},
            ]
        },
        headers=headers(),
    )
    assert unknown.status_code == 422 and len(unknown.json()["reasons"]) == 2

    locked = client.put(
        url, json={"decisions": [{"item_id": "ALL-01", "applies": "No"}]}, headers=headers()
    )
    assert locked.status_code == 409
    assert "ALL-01" in locked.json()["reasons"][0]
    assert (
        client.put(
            url, json={"decisions": [{"item_id": "ALL-01", "applies": "Yes"}]}, headers=headers()
        ).status_code
        == 200
    )


def test_retail_mandatory_row_is_locked(client, headers, fresh_seed):
    tid = _create(
        client,
        headers,
        portfolio="Retail Site Systems",
        sites=[{"site_id": "S1", "site_key": "K1"}],
    )
    s = _scope(client, headers, tid)
    rss01 = next(r for r in s["golden_set"] if r["id"] == "RSS-01")
    assert rss01["type"] == "Mandatory" and rss01["locked"] is True and rss01["applies"] == "Yes"
    res = client.put(
        f"{API}/transitions/{tid}/scope",
        json={"decisions": [{"item_id": "RSS-01", "applies": "To confirm"}]},
        headers=headers(),
    )
    assert res.status_code == 409
    assert s["counts"]["golden_set_applies"] == 1


# --- launch --------------------------------------------------------------------------------------


def test_launch_permissions_and_errors(client, headers, fresh_seed):
    tid = _create_ai(client, headers)
    assert _launch(client, headers, tid, user="U10").status_code == 403
    assert _launch(client, headers, "TR-9999").status_code == 404

    no_tier = _launch(client, headers, tid)
    assert no_tier.status_code == 409
    assert "Propose a tier before launching" in no_tier.json()["reasons"]

    _propose(client, headers, tid)
    ok = _launch(client, headers, tid)
    assert ok.status_code == 200, ok.text
    again = _launch(client, headers, tid)
    assert again.status_code == 409
    assert "Assessment already launched" in again.json()["reasons"]


def test_launch_creates_items_with_decisions_owners_and_audit(client, headers, db, fresh_seed):
    tid = _create(client, headers)
    client.put(
        f"{API}/transitions/{tid}/scope",
        json={
            "decisions": [
                {"item_id": "GCC-01", "applies": "Yes"},
                {"item_id": "GCC-02", "applies": "No", "reason": "Out of scope"},
            ]
        },
        headers=headers(),
    )
    res = _launch(client, headers, tid)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["transition_id"] == tid and out["redirect"] == f"/transitions/{tid}/assessment"
    c = out["counts"]
    assert c["framework"] == 72 and c["common"] == 2
    assert c["golden_set_applies"] == 1 and c["golden_set_to_confirm"] == 3
    assert c["total_applicable"] == 72 + 1 + 1 and c["total"] == c["total_applicable"]

    items = _items(db, tid)
    assert len(items) == 72 + 5 + 2
    gcc01, gcc02, gcc03 = items["GCC-01"], items["GCC-02"], items["GCC-03"]
    assert gcc01.applicability == "Applies" and gcc01.status == "Not started"
    assert gcc02.applicability == "Not applicable" and gcc02.na_reason == "Out of scope"
    assert gcc02.excluded_by is None and gcc02.status == "N/A"
    assert gcc03.applicability == "To confirm"
    assert items["ALL-01"].applicability == "Applies"
    assert items["ALL-02"].applicability == "To confirm"
    # owners per BR-010 step 6 (A-11): compliance -> IRM, others PM / Architect / ...
    owners = {i.playbook_item_id: i.owner_user_id for i in items.values()}
    sources = {p.id: p for p in db.scalars(select(PlaybookItem))}
    for item_id, owner in owners.items():
        lens = sources[item_id].lens
        if lens == "Compliance":
            assert owner == "U14", item_id
        else:
            assert owner in {"U01", "U10", "U11", "U12"}, item_id
    assert all(i.due_gate == sources[i.playbook_item_id].gate for i in items.values())

    detail = client.get(f"{API}/transitions/{tid}", headers=headers()).json()
    assert detail["assessment_launched"] is True
    assert detail["item_counts"]["total"] == c["total_applicable"]
    assert detail["item_counts"]["framework"] == 72
    after = _scope(client, headers, tid)
    assert after["launched"] is True and after["counts"]["total"] == c["total_applicable"]
    rows = {r["id"]: r for r in after["golden_set"]}
    assert rows["GCC-02"]["applies"] == "No" and rows["GCC-02"]["reason"] == "Out of scope"

    db.expire_all()
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.action == "Assessment launched"
        )
    ).one()
    assert event.actor_type == "Human" and event.actor_user_id == "U01"
    assert event.after["framework"] == 72


def test_scope_decisions_after_launch_update_items(client, headers, db, fresh_seed):
    tid = _create(client, headers)
    assert _launch(client, headers, tid).status_code == 200
    url = f"{API}/transitions/{tid}/scope"
    res = client.put(
        url,
        json={
            "decisions": [
                {"item_id": "GCC-01", "applies": "Yes"},
                {"item_id": "GCC-02", "applies": "No", "reason": "Not needed"},
            ],
            "source": "orion_recommendation",
        },
        headers=headers(),
    )
    assert res.status_code == 200, res.text
    items = _items(db, tid)
    assert items["GCC-01"].applicability == "Applies"
    assert items["GCC-01"].last_updated_source == "Human"
    assert items["GCC-02"].applicability == "Not applicable"
    assert items["GCC-02"].na_reason == "Not needed" and items["GCC-02"].excluded_by is None
    assert items["GCC-02"].status == "N/A"
    assert res.json()["counts"]["golden_set_applies"] == 1

    # an item with progress may still be set to No (human decision), and back to Yes
    items["GCC-01"].status = "In progress"
    db.commit()
    client.put(
        url,
        json={"decisions": [{"item_id": "GCC-01", "applies": "No", "reason": "Dropped"}]},
        headers=headers(),
    )
    assert _items(db, tid)["GCC-01"].applicability == "Not applicable"
    client.put(
        url, json={"decisions": [{"item_id": "GCC-01", "applies": "Yes"}]}, headers=headers()
    )
    back = _items(db, tid)["GCC-01"]
    assert back.applicability == "Applies" and back.status == "Not started"

    db.expire_all()
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.action == "Scope decisions recorded"
        )
    ).first()
    assert event.note == "Accepted Orion recommendations"


# --- AC-03: item sets per project type ------------------------------------------------------------


@pytest.mark.parametrize("project_type", ["Normal", "Infrastructure"])
def test_ac03_framework_only_types(client, headers, db, fresh_seed, project_type):
    tid = _create(client, headers, project_type=project_type)
    assert _launch(client, headers, tid).status_code == 200
    counts = _by_source(db, tid)
    assert counts[("FRAMEWORK", "Applies")] == 72
    assert not [k for k in counts if k[0] == "AI_PLAYBOOK"]
    assert counts[("PORTFOLIO", "To confirm")] == 5
    assert counts[("COMMON", "Applies")] == 1 and counts[("COMMON", "To confirm")] == 1


@pytest.mark.parametrize("project_type", ["Agentic AI", "Combined"])
def test_ac03_ai_types_tier_2_excludes_tier_3_4_items(
    client, headers, db, fresh_seed, project_type
):
    tid = _create(
        client,
        headers,
        project_type=project_type,
        audience="Internal department",
        write_actions="No",
        sensitive_data="No",
    )
    assert _propose(client, headers, tid)["proposed_tier"] == 2
    assert _launch(client, headers, tid).status_code == 200
    counts = _by_source(db, tid)
    assert counts[("FRAMEWORK", "Applies")] == 72
    assert counts[("AI_PLAYBOOK", "Applies")] == 208
    assert counts[("AI_PLAYBOOK", "Not applicable")] == 8
    items = _items(db, tid)
    sources = {p.id: p for p in db.scalars(select(PlaybookItem))}
    excluded = [i for i in items.values() if i.applicability == "Not applicable"]
    assert len(excluded) == 8
    for item in excluded:
        assert item.excluded_by == "tier" and item.status in ("N/A", "Not applicable")
        assert 2 not in sources[item.playbook_item_id].applicable_tiers


# --- storyline step 3 end to end ------------------------------------------------------------------


def test_storyline_step_3_end_to_end(client, headers, db, fresh_seed):
    sn = client.get(f"{API}/integrations/servicenow/projects/PRJ0052210", headers=headers("U01"))
    assert sn.status_code == 200
    p = sn.json()

    create = client.post(
        f"{API}/transitions",
        json={
            "name": p["name"],
            "servicenow_project_id": p["project_id"],
            "project_type": p["project_type"],
            "portfolio": p["portfolio"],
            "region": p["region"],
            "market": p["market"],
            "description": p["description"],
            "investment_type": p["investment_type"],
            "delivery_method": p["delivery_method"],
            "sites": [
                {"site_id": "NL-1001", "site_key": "AMS-A"},
                {"site_id": "NL-1002", "site_key": "AMS-B"},
            ],
            "audience": "Internal department",
            "write_actions": "No",
            "sensitive_data": "No",
            "or_focal_user_id": "U01",
            "pm_user_id": p["pm_user_id"],
            "architect_user_id": "U11",
            "olm_user_id": "U12",
            "irm_user_id": "U14",
        },
        headers=headers("U01"),
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]
    assert create.json()["requires_tiering"] is True and len(create.json()["sites"]) == 2

    proposed = _propose(client, headers, tid, {"TQ4": True})
    assert proposed["proposed_tier"] == 2
    assert "Internal audience" in proposed["rationale"]
    assert "TQ4 = yes -> Tier 2" in proposed["rationale"]

    confirmed = client.post(
        f"{API}/transitions/{tid}/tier/confirm", json={"tier": 2}, headers=headers("U14")
    )
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "Confirmed"

    scope = _scope(client, headers, tid)
    rss01 = next(r for r in scope["golden_set"] if r["id"] == "RSS-01")
    assert rss01["locked"] is True and rss01["applies"] == "Yes"
    recs = scope["recommendations"]
    assert recs and all(r["item_id"] != "RSS-01" and r["item_id"] != "ALL-01" for r in recs)

    accept = client.put(
        f"{API}/transitions/{tid}/scope",
        json={
            "decisions": [
                {"item_id": r["item_id"], "applies": r["recommendation"], "reason": r["reason"]}
                for r in recs
            ],
            "source": "orion_recommendation",
        },
        headers=headers("U01"),
    )
    assert accept.status_code == 200, accept.text
    accepted = accept.json()
    assert accepted["recommendations"] == []
    assert accepted["counts"]["golden_set_to_confirm"] == 0

    launch = _launch(client, headers, tid)
    assert launch.status_code == 200, launch.text
    counts = launch.json()["counts"]
    assert counts["framework"] == 72
    assert counts["ai_applicable"] == 208 and counts["ai_excluded"] == 8
    assert counts["golden_set_applies"] >= 1 and counts["golden_set_to_confirm"] == 0
    assert counts["common"] == 2
    assert counts["total_applicable"] == (
        72
        + 208
        + counts["golden_set_applies"]
        + sum(1 for r in recs if r["item_id"] == "ALL-02" and r["recommendation"] == "Yes")
        + 1
    )

    detail = client.get(f"{API}/transitions/{tid}", headers=headers("U01")).json()
    assert detail["assessment_launched"] is True and detail["tier_status"] == "Confirmed"
    assert detail["checklist_banner"] is None
    assert detail["item_counts"]["ai_applicable"] == 208


# --- re-assembly ---------------------------------------------------------------------------------


def test_tier_change_after_launch_reassembles_and_keeps_progress(client, headers, db, fresh_seed):
    tid = _create_ai(client, headers)
    _propose(client, headers, tid, {"TQ4": True})
    assert _launch(client, headers, tid).status_code == 200
    detail = client.get(f"{API}/transitions/{tid}", headers=headers()).json()
    assert (
        detail["checklist_banner"]
        == "Checklist based on proposed Tier 2 — confirm tier to finalise"
    )

    items = _items(db, tid)
    framework = next(i for i in items.values() if i.playbook_item_id == "FW-001")
    framework.status = "Complete"
    db.commit()

    res = client.put(
        f"{API}/transitions/{tid}/tier",
        json={"answers": {"TQ2": True, "TQ4": True}},
        headers=headers("U01"),
    )
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["proposed_tier"] == 4
    assert out["reassembly"] is not None
    assert set(out["reassembly"]) == {"added", "excluded", "restored", "unchanged"}
    assert out["reassembly"]["added"] == 0
    assert out["reassembly"]["restored"] > 0 or out["reassembly"]["excluded"] > 0

    after = _items(db, tid)
    assert len(after) == len(items)
    assert after["FW-001"].status == "Complete"

    tier4 = _by_source(db, tid)
    assert tier4[("AI_PLAYBOOK", "Applies")] + tier4[("AI_PLAYBOOK", "Not applicable")] == 216

    # IRM changes the tier back down: re-assembly again, returned in the response
    back = client.post(
        f"{API}/transitions/{tid}/tier/confirm",
        json={"tier": 2, "reason": "Scope reduced"},
        headers=headers("U14"),
    )
    assert back.status_code == 200, back.text
    assert back.json()["reassembly"] is not None
    tier2 = _by_source(db, tid)
    assert tier2[("AI_PLAYBOOK", "Applies")] == 208
    assert tier2[("AI_PLAYBOOK", "Not applicable")] == 8
    assert _items(db, tid)["FW-001"].status == "Complete"

    # confirming the tier that is already applied does not re-assemble
    same = client.post(
        f"{API}/transitions/{tid}/tier/confirm",
        json={"tier": 2, "reason": "Scope reduced"},
        headers=headers("U14"),
    )
    assert same.json()["reassembly"] is None

    db.expire_all()
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.action == "Checklist re-assembled"
        )
    ).all()
    assert len(events) == 2 and all("unchanged" in e.after for e in events)


def test_patch_portfolio_after_launch_reassembles(client, headers, db, fresh_seed):
    tid = _create(client, headers)
    assert _launch(client, headers, tid).status_code == 200
    items = _items(db, tid)
    gcc01 = items["GCC-01"]
    gcc01.applicability, gcc01.status = "Applies", "In progress"
    db.commit()

    res = client.patch(
        f"{API}/transitions/{tid}", json={"portfolio": "eMobility"}, headers=headers("U01")
    )
    assert res.status_code == 200, res.text
    assert res.json()["portfolio"] == "eMobility"

    after = _items(db, tid)
    for n in range(1, 6):
        assert f"EMOB-0{n}" in after
        assert after[f"EMOB-0{n}"].applicability == "To confirm"
    gcc = after["GCC-01"]
    assert gcc.applicability == "Not applicable" and gcc.excluded_by == "portfolio"
    assert gcc.status == "N/A"
    assert all(after[f"GCC-0{n}"].applicability == "Not applicable" for n in range(1, 6))
    assert after["FW-001"].applicability == "Applies"

    detail = res.json()
    assert detail["item_counts"]["golden_set_to_confirm"] == 5
    assert detail["item_counts"]["golden_set_applies"] == 0

    db.expire_all()
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.action == "Checklist re-assembled"
        )
    ).one()
    assert event.after["added"] == 5 and event.after["excluded"] == 5


def test_patch_project_type_after_launch_switches_flavour(client, headers, db, fresh_seed):
    tid = _create_ai(client, headers)
    _propose(client, headers, tid)
    assert _launch(client, headers, tid).status_code == 200

    to_normal = client.patch(
        f"{API}/transitions/{tid}", json={"project_type": "Normal"}, headers=headers()
    )
    assert to_normal.status_code == 200, to_normal.text
    counts = _by_source(db, tid)
    assert counts[("AI_PLAYBOOK", "Applies")] == 0
    assert counts[("AI_PLAYBOOK", "Not applicable")] == 216
    excluded = [i for i in _items(db, tid).values() if i.excluded_by == "project_type"]
    assert len(excluded) == 208

    # back to Combined: the tier assessment is still there, so Tier 2 applies again
    to_combined = client.patch(
        f"{API}/transitions/{tid}", json={"project_type": "Combined"}, headers=headers()
    )
    assert to_combined.status_code == 200
    counts = _by_source(db, tid)
    assert counts[("AI_PLAYBOOK", "Applies")] == 208
    assert counts[("AI_PLAYBOOK", "Not applicable")] == 8


def test_counts_have_an_other_bucket_that_is_empty_without_admin_checklists(
    client, headers, fresh_seed
):
    tid = _create(client, headers)
    scope = _scope(client, headers, tid)
    assert scope["counts"]["other"] == 0
    launched = _launch(client, headers, tid)
    assert launched.status_code == 200
    assert launched.json()["counts"]["other"] == 0
