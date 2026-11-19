"""CR-01 admin "People": add, edit and deactivate users (with reassignment in one audited action) and
rename the eight roles. The login list shows active people only; names Orion / agent / bot / AI are
refused (BR-050)."""

from __future__ import annotations

from app.models import AuditEvent, Transition

API = "/api/v1"
ADMIN = "U16"
NEW = {"name": "Sam Secure", "email": "sam.secure@example.com", "role": "PM"}


def _admin_users(client, headers) -> dict[str, dict]:
    r = client.get(f"{API}/admin/users", headers=headers(ADMIN))
    assert r.status_code == 200, r.text
    return {u["id"]: u for u in r.json()}


def _create(client, headers, **overrides):
    return client.post(f"{API}/admin/users", json={**NEW, **overrides}, headers=headers(ADMIN))


def test_create_user_gets_the_next_id(client, headers, fresh_seed) -> None:
    first = _create(client, headers)
    assert first.status_code == 201, first.text
    out = first.json()
    assert out["id"] == "U17" and out["role_label"] == "Project manager" and out["active"] is True
    second = _create(client, headers, name="Tina Tester", email="tina@example.com", role="OLM")
    assert second.json()["id"] == "U18"
    login = client.get(f"{API}/users").json()
    assert {"U17", "U18"} <= {u["id"] for u in login}
    me = client.get(f"{API}/me", headers=headers("U17")).json()
    assert me["user"]["name"] == "Sam Secure" and "view" in me["permissions"]


def test_create_user_validation(client, headers, fresh_seed) -> None:
    for name in ("Orion", "Mail Bot", "AI Helper", "Agent Smith"):
        r = _create(client, headers, name=name, email=f"{name[:3].lower()}@example.com")
        assert r.status_code == 422 and "reserved word" in r.json()["reasons"][0], name
    assert _create(client, headers, email="not-an-email").status_code == 422
    assert _create(client, headers, role="WIZARD").status_code == 422
    assert _create(client, headers, role="ORION").status_code == 422
    assert _create(client, headers).status_code == 201
    dup = _create(client, headers, name="Other Sam", email="SAM.SECURE@example.com")
    assert dup.status_code == 422 and "already used" in dup.json()["reasons"][0]
    assert _create(client, headers, name="  ").status_code == 422  # stripped, then too short


def test_edit_user_and_role_rules(client, headers, fresh_seed) -> None:
    h = headers(ADMIN)
    r = client.patch(
        f"{API}/admin/users/U10", json={"name": "Priya Patel", "title": "Lead PM"}, headers=h
    )
    assert (
        r.status_code == 200
        and r.json()["name"] == "Priya Patel"
        and r.json()["title"] == "Lead PM"
    )
    # a person with open transitions cannot change role; one without can
    assert (
        client.patch(f"{API}/admin/users/U10", json={"role": "ARCHITECT"}, headers=h).status_code
        == 422
    )
    new = client.post(
        f"{API}/admin/users",
        json={"name": "Nina Roy", "email": "nina.roy@example.com", "role": "PM"},
        headers=h,
    ).json()
    assert (
        client.patch(
            f"{API}/admin/users/{new['id']}", json={"role": "ARCHITECT"}, headers=h
        ).json()["role"]
        == "ARCHITECT"
    )
    assert (
        client.patch(f"{API}/admin/users/U10", json={"role": "WIZARD"}, headers=h).status_code
        == 422
    )
    assert (
        client.patch(f"{API}/admin/users/U10", json={"name": "Bot"}, headers=h).status_code == 422
    )
    # e-mail of somebody else
    other = _admin_users(client, headers)["U01"]["email"]
    assert (
        client.patch(f"{API}/admin/users/U10", json={"email": other}, headers=h).status_code == 422
    )
    # an Admin cannot move away from Admin (that is the only Admin: self and last at once)
    r = client.patch(f"{API}/admin/users/{ADMIN}", json={"role": "PM"}, headers=h)
    assert r.status_code == 422 and "own role" in r.json()["reasons"][0]
    assert client.patch(f"{API}/admin/users/U99", json={"name": "X"}, headers=h).status_code == 404


def test_deactivate_with_reassignment_in_one_audited_action(
    client, headers, fresh_seed, db
) -> None:
    users = _admin_users(client, headers)
    owner = max(
        (u for u in users.values() if u["role"] == "OR_FOCAL"),
        key=lambda u: u["assigned_transitions"],
    )
    assert owner["assigned_transitions"] > 0
    heir = next(
        u["id"] for u in users.values() if u["role"] == "OR_FOCAL" and u["id"] != owner["id"]
    )
    r = client.post(
        f"{API}/admin/users/{owner['id']}/deactivate",
        json={"reassign_to": heir},
        headers=headers(ADMIN),
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["assigned_transitions"] == owner["assigned_transitions"] == out["reassigned"]
    assert out["user"]["active"] is False and out["warnings"] == []
    assert (
        db.query(Transition)
        .filter(Transition.or_focal_user_id == owner["id"], Transition.status != "Closed")
        .count()
        == 0
    )
    events = db.query(AuditEvent).filter(AuditEvent.action == "reassigned").all()
    assert len(events) == out["reassigned"]
    assert all(
        e.entity == "Transition"
        and e.actor_type == "Human"
        and e.after == {"or_focal_user_id": heir}
        for e in events
    )
    summary = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity == "config:users", AuditEvent.action == "deactivated")
        .one()
    )
    assert summary.entity_id == owner["id"] and summary.after["reassigned"] == out["reassigned"]
    # login list: active people only; the old record still resolves the name
    assert owner["id"] not in {u["id"] for u in client.get(f"{API}/users").json()}
    assert _admin_users(client, headers)[owner["id"]]["name"] == owner["name"]
    # a deactivated person cannot keep working with a stale login
    assert client.get(f"{API}/me", headers=headers(owner["id"])).status_code == 401
    # and can come back
    back = client.patch(
        f"{API}/admin/users/{owner['id']}", json={"active": True}, headers=headers(ADMIN)
    )
    assert back.status_code == 200 and back.json()["active"] is True
    assert client.get(f"{API}/me", headers=headers(owner["id"])).status_code == 200


def test_deactivate_needs_a_replacement_when_work_is_open(client, headers, fresh_seed) -> None:
    users = _admin_users(client, headers)
    owner = max(
        (u for u in users.values() if u["role"] == "OR_FOCAL"),
        key=lambda u: u["assigned_transitions"],
    )
    refused = client.post(
        f"{API}/admin/users/{owner['id']}/deactivate", json={}, headers=headers(ADMIN)
    )
    assert refused.status_code == 422 and "pick a replacement" in refused.json()["reasons"][0]
    # somebody without open transitions can be switched off directly
    new = _create(client, headers).json()
    r = client.post(f"{API}/admin/users/{new['id']}/deactivate", json={}, headers=headers(ADMIN))
    assert r.status_code == 200 and r.json()["reassigned"] == 0
    again = client.post(
        f"{API}/admin/users/{new['id']}/deactivate", json={}, headers=headers(ADMIN)
    )
    assert again.status_code == 409


def test_deactivate_guardrails(client, headers, fresh_seed) -> None:
    h = headers(ADMIN)
    me = client.post(f"{API}/admin/users/{ADMIN}/deactivate", json={}, headers=h)
    assert me.status_code == 422 and "yourself" in me.json()["reasons"][0]
    # the replacement must be an active person with the same role
    bad_role = client.post(
        f"{API}/admin/users/U01/deactivate", json={"reassign_to": "U10"}, headers=h
    )
    assert bad_role.status_code == 422 and "same role" in bad_role.json()["reasons"][0]
    assert (
        client.post(
            f"{API}/admin/users/U01/deactivate", json={"reassign_to": "U01"}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/admin/users/U01/deactivate", json={"reassign_to": "U99"}, headers=h
        ).status_code
        == 422
    )
    client.post(f"{API}/admin/users/U03/deactivate", json={"reassign_to": "U04"}, headers=h)
    inactive_target = client.post(
        f"{API}/admin/users/U01/deactivate", json={"reassign_to": "U03"}, headers=h
    )
    assert inactive_target.status_code == 422
    assert client.post(f"{API}/admin/users/U99/deactivate", json={}, headers=h).status_code == 404
    # nothing happened to U01
    assert _admin_users(client, headers)["U01"]["active"] is True
    # a second Admin makes the first one removable, but only by the second one
    client.post(f"{API}/admin/users", json={**NEW, "role": "ADMIN"}, headers=h)
    assert client.post(f"{API}/admin/users/U17/deactivate", json={}, headers=h).status_code == 200


def test_active_false_goes_through_deactivate(client, headers, fresh_seed) -> None:
    r = client.patch(f"{API}/admin/users/U02", json={"active": False}, headers=headers(ADMIN))
    assert r.status_code == 422 and "Deactivate" in r.json()["reasons"][0]


def test_rename_a_role(client, headers, fresh_seed, db) -> None:
    h = headers(ADMIN)
    r = client.patch(
        f"{API}/admin/roles/PM",
        json={
            "label": "Programme manager",
            "phrase_label": "programme manager",
            "description": "Runs it",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    pm = next(x for x in r.json() if x["code"] == "PM")
    assert (
        pm["label"] == "Programme manager"
        and pm["description"] == "Runs it"
        and pm["user_count"] >= 1
    )
    assert pm["code"] == "PM" and len(r.json()) == 8
    ref = client.get(f"{API}/reference").json()
    assert next(x for x in ref["roles"] if x["code"] == "PM")["label"] == "Programme manager"
    assert (
        client.get(f"{API}/me", headers=headers("U10")).json()["user"]["role_label"]
        == "Programme manager"
    )
    # the new wording appears in denial messages built from role labels
    detail = client.get(f"{API}/transitions/TR-0001", headers=headers("U02")).json()
    reasons = " ".join(v for v in detail["access"].values() if v)
    assert "programme manager" in reasons
    row = db.query(AuditEvent).filter(AuditEvent.entity == "config:roles").one()
    assert row.before["label"] == "Project manager" and row.after["label"] == "Programme manager"


def test_role_rules(client, headers, fresh_seed) -> None:
    h = headers(ADMIN)
    for label in ("Orion", "AI lead", "Agent"):
        r = client.patch(f"{API}/admin/roles/PM", json={"label": label}, headers=h)
        assert r.status_code == 422 and "reserved word" in r.json()["reasons"][0]
    assert client.patch(f"{API}/admin/roles/PM", json={"label": " "}, headers=h).status_code == 422
    assert (
        client.patch(f"{API}/admin/roles/NOPE", json={"label": "x"}, headers=h).status_code == 404
    )
    assert (
        client.patch(
            f"{API}/admin/roles/PM", json={"label": "PM"}, headers=headers("U01")
        ).status_code
        == 403
    )
    # codes, slots and permissions cannot be changed here, and no role can be created or deleted
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/api/v1/admin/roles"]) == {"get"}
    assert set(paths["/api/v1/admin/roles/{code}"]) == {"patch"}
    roles = {r["code"]: r for r in client.get(f"{API}/admin/roles", headers=h).json()}
    assert len(roles) == 8 and roles["ADMIN"]["has_transition_slot"] is False
