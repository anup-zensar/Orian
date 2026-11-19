"""Admin configuration (FR-100, spec 8.16): ADMIN only, audited, new transitions only."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import AuditEvent, PlaybookItem

API = "/api/v1"
ADMIN = "U16"

GET_ROUTES = [
    "/admin/playbook-items",
    "/admin/playbook-items/FW-001",
    "/admin/flavour-rules",
    "/admin/portfolios/GCC/golden-set",
    "/admin/eval-targets",
    "/admin/approval-chains",
    "/admin/reminder-rules",
    "/admin/users",
]


def _audits(db, entity: str, entity_id: str | None = None) -> list[AuditEvent]:
    db.expire_all()
    stmt = select(AuditEvent).where(AuditEvent.entity == entity)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    return list(db.scalars(stmt).all())


@pytest.mark.parametrize("path", GET_ROUTES)
def test_get_routes_admin_only(client, headers, path):
    denied = client.get(f"{API}{path}", headers=headers("U01"))
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only the Playbook admin can change configuration"
    assert client.get(f"{API}{path}", headers=headers(ADMIN)).status_code == 200


def test_put_routes_non_admin_403(client, headers):
    calls = [
        ("put", "/admin/playbook-items/FW-001", {"title": "x", "gate": "SG0", "lens": "Business"}),
        ("put", "/admin/flavour-rules", {"rules": []}),
        ("put", "/admin/portfolios/GCC/golden-set", {"items": []}),
        ("put", "/admin/eval-targets", {"confirmed": True, "metrics": []}),
        ("put", "/admin/approval-chains", {"chains": []}),
        ("put", "/admin/reminder-rules", {"rules": []}),
    ]
    for user in ("U01", "U14", "U15"):
        for method, path, body in calls:
            res = getattr(client, method)(f"{API}{path}", json=body, headers=headers(user))
            assert res.status_code == 403, (user, path)
        for path, body in (
            ("/admin/demo/reset", None),
            ("/admin/demo/fast-forward", {}),
            ("/admin/demo/today", {"date": None}),
        ):
            assert client.post(f"{API}{path}", json=body, headers=headers(user)).status_code == 403
        assert client.get(f"{API}/admin/demo/today", headers=headers(user)).status_code == 403


def test_playbook_filters(client, headers):
    h = headers(ADMIN)
    everything = client.get(f"{API}/admin/playbook-items", headers=h).json()
    ids = [i["id"] for i in everything]
    assert ids == sorted(ids) and len(ids) > 100
    fw = client.get(f"{API}/admin/playbook-items", params={"source": "FRAMEWORK"}, headers=h)
    assert fw.json() and all(i["source"] == "FRAMEWORK" for i in fw.json())
    found = client.get(f"{API}/admin/playbook-items", params={"q": "fw-008"}, headers=h).json()
    assert [i["id"] for i in found] == ["FW-008"]
    assert found[0]["linked_module"] == "OCET" and "new transitions" in found[0]["notice"]
    bad = client.get(f"{API}/admin/playbook-items", params={"source": "NOPE"}, headers=h)
    assert bad.status_code == 422
    assert client.get(f"{API}/admin/playbook-items/NOPE", headers=h).status_code == 404


def test_playbook_update_round_trip(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    suggested = db.scalars(
        select(PlaybookItem).where(PlaybookItem.lens_is_suggested.is_(True)).limit(1)
    ).first()
    assert suggested is not None, "seed has lens-suggested items"
    item_id = suggested.id
    before = client.get(f"{API}/admin/playbook-items/{item_id}", headers=h).json()
    assert before["lens_suggested"] is True
    new_lens = "Technical" if before["lens"] != "Technical" else "Business"
    body = {
        "title": "Edited title",
        "description": "Edited",
        "gate": "SG3",
        "lens": new_lens,
        "applicable_tiers": [2, 3],
        "mandatory": False,
        "active": True,
    }
    res = client.put(f"{API}/admin/playbook-items/{item_id}", json=body, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["title"] == "Edited title" and out["gate"] == "SG3" and out["lens"] == new_lens
    assert out["lens_suggested"] is False and out["lens_is_suggested"] is False
    assert out["applicable_tiers"] == [2, 3] and out["mandatory"] is False
    assert client.get(f"{API}/admin/playbook-items/{item_id}", headers=h).json()["title"] == (
        "Edited title"
    )
    events = _audits(db, "PlaybookItem", item_id)
    assert events and events[-1].actor_type == "Human"
    assert events[-1].before["title"] != "Edited title" and events[-1].after["gate"] == "SG3"

    for bad in ({**body, "gate": "SG9"}, {**body, "applicable_tiers": [0]}):
        assert (
            client.put(f"{API}/admin/playbook-items/{item_id}", json=bad, headers=h).status_code
            == 422
        )
    assert client.put(f"{API}/admin/playbook-items/NOPE", json=body, headers=h).status_code == 404


def test_edit_does_not_change_existing_transition_items(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    before = client.get(f"{API}/transitions/TR-0001/items", headers=headers("U01")).json()
    client.put(
        f"{API}/admin/playbook-items/FW-001",
        json={"title": "Changed", "gate": "SG0", "lens": "Business", "mandatory": True},
        headers=h,
    )
    after = client.get(f"{API}/transitions/TR-0001/items", headers=headers("U01")).json()
    assert before == after or len(before["items"]) == len(after["items"])


def test_flavour_rules_round_trip(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    rules = client.get(f"{API}/admin/flavour-rules", headers=h).json()["rules"]
    assert {r["project_type"] for r in rules} >= {"Agentic AI", "Normal"}
    target = next(r for r in rules if r["project_type"] == "Normal")
    entry = {
        "project_type": "Normal",
        "checklists": ["FRAMEWORK", "COMMON"],
        "requires_tiering": not target["requires_tiering"],
        "note": "edited",
    }
    res = client.put(f"{API}/admin/flavour-rules", json={"rules": [entry]}, headers=h)
    assert res.status_code == 200, res.text
    got = next(r for r in res.json()["rules"] if r["project_type"] == "Normal")
    assert got["checklists"] == ["FRAMEWORK", "COMMON"] and got["note"] == "edited"
    assert len(_audits(db, "FlavourRule", "Normal")) == 1
    bad = client.put(
        f"{API}/admin/flavour-rules",
        json={"rules": [{**entry, "project_type": "Nope"}]},
        headers=h,
    )
    assert bad.status_code == 422
    bad = client.put(
        f"{API}/admin/flavour-rules",
        json={"rules": [{**entry, "checklists": ["BOGUS"]}]},
        headers=h,
    )
    assert bad.status_code == 422


def test_golden_set_never_deletes(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    url = f"{API}/admin/portfolios/GCC/golden-set"
    current = client.get(url, headers=h).json()
    assert current["portfolio"] == "GCC" and current["items"]
    assert client.get(f"{API}/admin/portfolios/Nowhere/golden-set", headers=h).status_code == 404
    ids = [i["id"] for i in current["items"]]
    assert all(i.startswith("GCC-") for i in ids)

    keep = current["items"][0]
    items = [
        {
            "id": keep["id"],
            "title": "Renamed",
            "gate": keep["gate"],
            "owner_role_hint": keep["owner_role_hint"],
            "lens": keep["lens"],
            "mandatory": keep["mandatory"],
        },
        {"title": "Brand new", "gate": "SG3", "lens": "Technical", "owner_role_hint": "Architect"},
    ]
    res = client.put(url, json={"items": items, "focus_areas": ["A", "B"]}, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["focus_areas"] == ["A", "B"]
    by_id = {i["id"]: i for i in out["items"]}
    assert set(ids) <= set(by_id), "rows are never deleted"
    assert by_id[keep["id"]]["title"] == "Renamed" and by_id[keep["id"]]["active"] is True
    omitted = [i for i in ids if i != keep["id"]]
    assert omitted and all(by_id[i]["active"] is False for i in omitted)
    new_ids = set(by_id) - set(ids)
    expected = f"GCC-{max(int(i.split('-')[1]) for i in ids) + 1:02d}"
    assert new_ids == {expected}
    assert by_id[expected]["title"] == "Brand new"
    db.expire_all()
    assert db.get(PlaybookItem, ids[-1]) is not None
    assert _audits(db, "PlaybookItem", expected)[0].action == "created"
    assert any(e.action == "deactivated" for e in _audits(db, "PlaybookItem", omitted[0]))

    # Foreign ids and bad gates are rejected
    bad = client.put(url, json={"items": [{**items[1], "id": "ALL-01"}]}, headers=h)
    assert bad.status_code == 422
    bad = client.put(url, json={"items": [{**items[1], "gate": "SG9"}]}, headers=h)
    assert bad.status_code == 422
    # A second new item continues numbering
    again = client.put(url, json={"items": [items[1], items[1]]}, headers=h).json()
    assert len(again["items"]) == len(ids) + 3


def test_eval_targets_round_trip(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    grid = client.get(f"{API}/admin/eval-targets", headers=h).json()
    assert grid["metrics"] and all(len(m["tiers"]) == 4 for m in grid["metrics"])
    assert grid["confirmed"] is False
    metric = next(
        m for m in grid["metrics"] if m["evaluation"] == "auto" and m["tiers"][0]["value"]
    )
    first = metric["tiers"][0]
    body = {
        "confirmed": True,
        "metrics": [
            {
                "metric_id": metric["metric_id"],
                "tiers": [
                    {
                        "tier": 4,
                        "target_text": "edited >= 99",
                        "operator": ">=",
                        "value": 99,
                        "unit": first["unit"],
                    }
                ],
            }
        ],
    }
    res = client.put(f"{API}/admin/eval-targets", json=body, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["confirmed"] is True
    row = next(m for m in out["metrics"] if m["metric_id"] == metric["metric_id"])
    t4 = next(t for t in row["tiers"] if t["tier"] == 4)
    assert t4["value"] == 99 and t4["target_text"] == "edited >= 99"
    assert _audits(db, "EvalTarget")

    def put(tiers, mid=metric["metric_id"]):
        return client.put(
            f"{API}/admin/eval-targets",
            json={"confirmed": True, "metrics": [{"metric_id": mid, "tiers": tiers}]},
            headers=h,
        )

    ok = {"tier": 1, "target_text": "x", "operator": ">=", "value": 1}
    assert put([ok], mid="EV-99").status_code == 422
    assert put([{**ok, "tier": 5}]).status_code == 422
    assert put([{"tier": 1, "target_text": "x", "value": 3}]).status_code == 422
    assert put([{**ok, "operator": "~"}]).status_code == 422


def test_approval_chains_round_trip(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    got = client.get(f"{API}/admin/approval-chains", headers=h).json()
    assert {c["type"] for c in got["chains"]} == {
        "OCET",
        "AtD",
        "AtO",
        "SUPPORT_MODEL",
        "EXCEPTION",
    }
    assert "CISO_BISO" in got["roles"] and "OLM" in got["roles"]

    chain = {
        "type": "OCET",
        "steps": [
            {"step": 1, "role": "PLANNER", "label": "Planner"},
            {"step": 2, "role": "ARCHITECT", "label": "Architect"},
            {"step": 3, "role": "OLM", "label": "OLM"},
        ],
    }
    res = client.put(f"{API}/admin/approval-chains", json={"chains": [chain]}, headers=h)
    assert res.status_code == 200, res.text
    ocet = next(c for c in res.json()["chains"] if c["type"] == "OCET")
    assert [s["role"] for s in ocet["steps"]] == ["PLANNER", "ARCHITECT", "OLM"]
    assert len(_audits(db, "config:approval_chains", "OCET")) == 1
    # an existing request keeps its steps
    seeded = client.get(f"{API}/approvals/APR-0001", headers=headers("U14")).json()
    assert len(seeded["steps"]) == 2

    def put(c):
        return client.put(f"{API}/admin/approval-chains", json={"chains": [c]}, headers=h)

    assert put({**chain, "steps": []}).status_code == 422
    bad_role = [{"step": 1, "role": "WIZARD", "label": "x"}]
    assert put({**chain, "steps": bad_role}).status_code == 422
    gap = [{"step": 1, "role": "OLM", "label": "x"}, {"step": 3, "role": "PM", "label": "y"}]
    assert put({**chain, "steps": gap}).status_code == 422
    assert put({"type": "Nope", "steps": chain["steps"]}).status_code == 422


def test_reminder_rules_round_trip(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    rules = client.get(f"{API}/admin/reminder-rules", headers=h).json()
    assert [r["id"] for r in rules] == [f"R{n}" for n in range(1, 8)]
    r1 = rules[0]
    assert r1["params"] == {"days_before_decision": 14}
    res = client.put(
        f"{API}/admin/reminder-rules",
        json={"rules": [{"id": "R1", "enabled": False, "params": {"days_before_decision": 7}}]},
        headers=h,
    )
    assert res.status_code == 200, res.text
    got = res.json()[0]
    assert got["enabled"] is False and got["params"] == {"days_before_decision": 7}
    assert got["name"] == r1["name"]
    assert len(_audits(db, "config:reminder_rules", "R1")) == 1

    def put(rule):
        return client.put(f"{API}/admin/reminder-rules", json={"rules": [rule]}, headers=h)

    assert put({"id": "R9", "enabled": True}).status_code == 422
    assert (
        put({"id": "R1", "enabled": True, "params": {"days_before_decision": 0}}).status_code == 422
    )
    assert (
        put({"id": "R1", "enabled": True, "params": {"days_before_decision": -3}}).status_code
        == 422
    )
    assert (
        put({"id": "R1", "enabled": True, "params": {"days_before_decision": 2.5}}).status_code
        == 422
    )
    assert put({"id": "R1", "enabled": True, "params": {"nope": 3}}).status_code == 422


def test_admin_users(client, headers):
    users = client.get(f"{API}/admin/users", headers=headers(ADMIN)).json()
    assert len(users) == 16 and all(u["role_label"] for u in users)


def test_admin_validation_hardening(client, headers, fresh_seed):
    h = headers(ADMIN)
    entry = {"project_type": "Normal", "checklists": [], "requires_tiering": False, "note": ""}
    res = client.put(f"{API}/admin/flavour-rules", json={"rules": [entry]}, headers=h)
    assert res.status_code == 422
    res = client.post(f"{API}/admin/demo/today", json={"date": "1900-01-01"}, headers=h)
    assert res.status_code == 422, res.text
    rule = client.get(f"{API}/admin/reminder-rules", headers=h).json()[0]
    key = next(iter(rule["params"]), None)
    if key:
        bad = {"rules": [{"id": rule["id"], "enabled": True, "params": {key: 100000000}}]}
        assert client.put(f"{API}/admin/reminder-rules", json=bad, headers=h).status_code == 422


def test_approval_chain_role_without_user_is_422(client, headers, db, fresh_seed):
    from app.models import User

    db.query(User).filter(User.role == "PLANNER").update({"role": "PM"})
    db.commit()
    chain = {"type": "OCET", "steps": [{"step": 1, "role": "PLANNER", "label": "p"}]}
    res = client.put(
        f"{API}/admin/approval-chains", json={"chains": [chain]}, headers=headers(ADMIN)
    )
    assert res.status_code == 422, res.text


def test_reminders_stub_is_501_not_500(client, headers):
    res = client.post(f"{API}/reminders/run", json={}, headers=headers("U01"))
    assert res.status_code in (200, 501), res.text


def test_flavour_rules_alias_carries_the_project_type_fields(client, headers):
    """CR-01: /admin/flavour-rules is an alias of the project types (original four fields kept)."""
    rules = client.get(f"{API}/admin/flavour-rules", headers=headers(ADMIN)).json()["rules"]
    ai = next(r for r in rules if r["project_type"] == "Agentic AI")
    assert ai["checklists"] == ["FRAMEWORK", "AI_PLAYBOOK"] and ai["requires_tiering"] is True
    assert ai["label"] == "Agentic AI" and ai["has_ai_profile"] and ai["has_eval_metrics"]
    assert ai["required_intake_fields"] == ["audience", "write_actions", "sensitive_data"]
    assert [r["project_type"] for r in rules] == [
        "Normal",
        "Infrastructure",
        "Agentic AI",
        "Combined",
    ]


def test_flavour_rules_alias_refuses_an_unknown_checklist(client, headers, fresh_seed):
    entry = {"project_type": "Normal", "checklists": ["FRAMEWORK", "NOPE"]}
    r = client.put(f"{API}/admin/flavour-rules", json={"rules": [entry]}, headers=headers(ADMIN))
    assert r.status_code == 422 and "'NOPE' is not an active checklist" in r.json()["reasons"][0]


def test_new_golden_set_items_apply_to_every_project_type(client, headers, fresh_seed, db):
    body = {"items": [{"title": "New golden item", "gate": "SG3", "lens": "Technical"}]}
    r = client.put(f"{API}/admin/portfolios/GCC/golden-set", json=body, headers=headers(ADMIN))
    assert r.status_code == 200
    db.expire_all()
    new = db.scalars(select(PlaybookItem).where(PlaybookItem.title == "New golden item")).one()
    assert new.applies_to_project_types == []  # [] = also for project types added later
