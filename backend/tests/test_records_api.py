"""Actions, conditions, risks, hypercare defects (FR-032, FR-035, FR-036, AC-13)."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditEvent

API = "/api/v1"
T = "TR-0001"


def _audit(db, entity, entity_id):
    db.expire_all()
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity == entity, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.id)
        ).all()
    )


def _get(client, headers, path, user="U01"):
    res = client.get(f"{API}{path}", headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


# --- actions --------------------------------------------------------------------------------------
def test_list_actions_sorted(client, headers):
    rows = _get(client, headers, f"/transitions/{T}/actions")
    assert rows
    open_rows = [r for r in rows if r["status"] in ("Open", "In progress")]
    closed = [r for r in rows if r["status"] not in ("Open", "In progress")]
    assert rows == open_rows + closed
    dues = [r["due_date"] or "9999-12-31" for r in open_rows]
    assert dues == sorted(dues)
    for r in open_rows:
        if r["due_date"]:
            assert r["days_until_due"] is not None
            assert r["overdue"] == (r["days_until_due"] < 0)
    assert client.get(f"{API}/transitions/TR-9999/actions", headers=headers()).status_code == 404


def test_action_crud_and_audit(client, headers, db, fresh_seed):
    body = {
        "title": "Run red-team exercise",
        "item_ids": ["S45-014", "S3-019"],
        "owner_user_id": "U11",
        "due_date": "2026-11-20",
        "priority": "High",
    }
    res = client.post(f"{API}/transitions/{T}/actions", json=body, headers=headers("U10"))
    assert res.status_code == 201, res.text
    act = res.json()
    assert act["id"].startswith("ACT-") and act["status"] == "Open" and act["origin"] == "Human"
    assert act["created_by"]["id"] == "U10" and act["owner"]["id"] == "U11"
    assert act["days_until_due"] == 4 and act["overdue"] is False
    assert act["item_ids"] == ["S45-014", "S3-019"]

    res = client.patch(
        f"{API}/actions/{act['id']}",
        json={"status": "In progress", "due_date": "2026-11-10"},
        headers=headers("U11"),
    )
    assert res.status_code == 200
    assert res.json()["overdue"] is True and res.json()["days_until_due"] == -6

    res = client.patch(
        f"{API}/actions/{act['id']}", json={"status": "Done"}, headers=headers("U11")
    )
    assert (
        res.status_code == 200 and res.json()["status"] == "Done" and res.json()["overdue"] is False
    )
    # Done actions only reopen
    res = client.patch(f"{API}/actions/{act['id']}", json={"title": "New"}, headers=headers("U11"))
    assert res.status_code == 409
    res = client.patch(
        f"{API}/actions/{act['id']}", json={"status": "Open"}, headers=headers("U11")
    )
    assert res.status_code == 200 and res.json()["status"] == "Open"

    events = _audit(db, "Action", act["id"])
    assert [e.action for e in events] == ["created", "updated", "closed", "updated"]
    assert all(e.actor_type == "Human" and e.transition_id == T for e in events)
    assert events[2].before["status"] == "In progress" and events[2].after["status"] == "Done"
    assert events[0].after["title"] == "Run red-team exercise"
    # listing: open first
    rows = _get(client, headers, f"/transitions/{T}/actions")
    assert act["id"] in [r["id"] for r in rows]


def test_action_validation_and_permissions(client, headers, fresh_seed):
    base = {"title": "x", "owner_user_id": "U11", "due_date": "2026-11-20"}
    url = f"{API}/transitions/{T}/actions"
    assert (
        client.post(url, json={**base, "owner_user_id": "U99"}, headers=headers()).status_code
        == 422
    )
    assert (
        client.post(url, json={**base, "item_ids": ["NOPE-1"]}, headers=headers()).status_code
        == 422
    )
    assert client.post(url, json={**base, "title": "   "}, headers=headers()).status_code == 422
    res = client.post(url, json=base, headers=headers("U13"))  # Planner
    assert res.status_code == 403
    assert res.json()["detail"] == "Your role cannot create or close actions"
    assert (
        client.post(f"{API}/transitions/TR-9999/actions", json=base, headers=headers()).status_code
        == 404
    )
    assert (
        client.patch(
            f"{API}/actions/ACT-999", json={"status": "Done"}, headers=headers()
        ).status_code
        == 404
    )
    first = _get(client, headers, f"/transitions/{T}/actions")[0]
    assert (
        client.patch(
            f"{API}/actions/{first['id']}", json={"title": "z"}, headers=headers("U13")
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{API}/actions/{first['id']}", json={"owner_user_id": "U99"}, headers=headers()
        ).status_code
        == 422
    )


def test_action_closed_transition(client, headers, db, fresh_seed):
    from app.models import Transition

    db.get(Transition, T).status = "Closed"
    db.commit()
    res = client.post(
        f"{API}/transitions/{T}/actions",
        json={"title": "x", "owner_user_id": "U11", "due_date": "2026-11-20"},
        headers=headers(),
    )
    assert res.status_code == 409


# --- conditions -----------------------------------------------------------------------------------
def test_list_conditions_seed(client, headers):
    rows = _get(client, headers, f"/transitions/{T}/conditions")
    by_id = {r["id"]: r for r in rows}
    assert {"CON-001", "CON-002"} <= set(by_id)
    con1, con2 = by_id["CON-001"], by_id["CON-002"]
    assert (
        con1["item_id"] == "S3-019"
        and con1["due_gate"] == "SG4_ATD"
        and con1["due_gate_short"] == "SG4 (AtD)"
    )
    assert con1["covers_now"] is False  # due at the current gate, not after it
    assert (
        con2["item_id"] == "S02-012"
        and con2["due_gate"] == "CLOSURE"
        and con2["covers_now"] is True
    )
    open_orders = [r["due_gate"] for r in rows if r["status"] == "Open"]
    order = ["SG0", "SG2", "SG3", "SG4_ATD", "SG5_HYPERCARE", "SG6_ATO", "CLOSURE"]
    assert [order.index(g) for g in open_orders] == sorted(order.index(g) for g in open_orders)


def test_condition_create_close_edit(client, headers, db, fresh_seed):
    url = f"{API}/transitions/{T}/conditions"
    body = {
        "item_id": "S3-019",
        "owner_user_id": "U11",
        "due_gate": "SG6_ATO",
        "text": "Fix logging",
    }
    assert client.post(url, json=body, headers=headers("U10")).status_code == 403  # PM
    assert client.post(url, json={**body, "due_gate": "SG2"}, headers=headers()).status_code == 422
    assert client.post(url, json={**body, "due_gate": "SG9"}, headers=headers()).status_code == 422
    assert (
        client.post(url, json={**body, "owner_user_id": "U99"}, headers=headers()).status_code
        == 422
    )
    assert client.post(url, json={**body, "item_id": "NOPE"}, headers=headers()).status_code == 404
    res = client.post(url, json=body, headers=headers())
    assert res.status_code == 201, res.text
    cond = res.json()
    assert cond["id"] == "CON-003" and cond["status"] == "Open" and cond["covers_now"] is True
    assert cond["set_at_gate"] == "SG4_ATD" and cond["item_id"] == "S3-019"

    patch = f"{API}/conditions/{cond['id']}"
    assert client.patch(patch, json={"status": "Closed"}, headers=headers()).status_code == 422
    res = client.patch(
        patch,
        json={"text": "Fix logging and alerts", "due_gate": "CLOSURE"},
        headers=headers("U14"),
    )
    assert res.status_code == 200 and res.json()["due_gate"] == "CLOSURE"
    res = client.patch(patch, json={"due_gate": "SG2"}, headers=headers())
    assert res.status_code == 422
    res = client.patch(
        patch, json={"status": "Closed", "close_note": "Done in sprint 12"}, headers=headers()
    )
    assert res.status_code == 200, res.text
    closed = res.json()
    assert (
        closed["status"] == "Closed" and closed["closed_by"]["id"] == "U01" and closed["closed_at"]
    )
    assert closed["close_note"] == "Done in sprint 12" and closed["covers_now"] is False
    assert client.patch(patch, json={"text": "again"}, headers=headers()).status_code == 409
    assert (
        client.patch(f"{API}/conditions/CON-999", json={"text": "x"}, headers=headers()).status_code
        == 404
    )
    # closed conditions are listed after open ones
    rows = _get(client, headers, f"/transitions/{T}/conditions")
    statuses = [r["status"] for r in rows]
    assert statuses == sorted(statuses, key=lambda s: s != "Open")
    events = _audit(db, "Condition", "CON-003")
    assert [e.action for e in events] == ["created", "updated", "closed"]
    assert all(e.actor_type == "Human" for e in events)
    assert events[2].before["status"] == "Open" and events[2].after["status"] == "Closed"


# --- risks ----------------------------------------------------------------------------------------
def test_risks_list_sorted_and_create(client, headers, db, fresh_seed):
    rows = _get(client, headers, f"/transitions/{T}/risks")
    assert rows
    order = {"High": 0, "Medium": 1, "Low": 2}
    keys = [(order[r["rating"]], r["id"]) for r in rows]
    assert keys == sorted(keys)
    url = f"{API}/transitions/{T}/risks"
    body = {
        "title": "Vendor lock-in",
        "rating": "Medium",
        "decision": "Accept",
        "item_ids": ["S3-019"],
    }
    assert client.post(url, json=body, headers=headers("U10")).status_code == 403
    assert (
        client.post(url, json={**body, "item_ids": ["NOPE"]}, headers=headers()).status_code == 422
    )
    assert client.post(url, json={**body, "title": "  "}, headers=headers()).status_code == 422
    res = client.post(url, json=body, headers=headers("U14"))
    assert res.status_code == 201, res.text
    risk = res.json()
    assert risk["id"].startswith("CR-") and risk["item_ids"] == ["S3-019"]
    events = _audit(db, "Risk", risk["id"])
    assert len(events) == 1 and events[0].actor_type == "Human" and events[0].action == "created"
    assert (
        client.post(f"{API}/transitions/TR-9999/risks", json=body, headers=headers()).status_code
        == 404
    )


# --- hypercare defects ----------------------------------------------------------------------------
def test_defects_crud_confirm_none_and_audit(client, headers, db, fresh_seed):
    hc = _get(client, headers, f"/transitions/{T}/defects")
    assert hc["defects"] == [] and hc["tracker_in_place"] is False and hc["open_p1_p2"] == 0
    url = f"{API}/transitions/{T}/defects"
    # confirm "no defects" on an empty tracker
    res = client.post(f"{url}/confirm-none", json={"confirmed": True}, headers=headers("U14"))
    assert res.status_code == 403
    res = client.post(f"{url}/confirm-none", json={"confirmed": True}, headers=headers())
    assert res.status_code == 200
    assert res.json()["no_defects_confirmed"] is True and res.json()["tracker_in_place"] is True

    # logging a defect resets the confirmation
    res = client.post(
        url,
        json={"title": "Timeouts", "priority": "P1", "owner_user_id": "U11"},
        headers=headers("U12"),
    )
    assert res.status_code == 201, res.text
    d1 = res.json()
    assert d1["id"] == "DEF-001" and d1["status"] == "Open" and d1["owner"]["id"] == "U11"
    d2 = client.post(url, json={"title": "Typo", "priority": "P4"}, headers=headers()).json()
    hc = _get(client, headers, f"/transitions/{T}/defects")
    assert hc["no_defects_confirmed"] is False and hc["tracker_in_place"] is True
    assert hc["open_p1_p2"] == 1
    assert [d["id"] for d in hc["defects"]] == [d1["id"], d2["id"]]
    # confirming with defects is a 409
    res = client.post(f"{url}/confirm-none", json={"confirmed": True}, headers=headers())
    assert res.status_code == 409 and "Resolve or remove defects first" in res.json()["reasons"][0]

    res = client.patch(
        f"{API}/defects/{d1['id']}", json={"status": "Resolved"}, headers=headers("U11")
    )
    assert res.status_code == 200 and res.json()["status"] == "Resolved"
    hc = _get(client, headers, f"/transitions/{T}/defects")
    assert hc["open_p1_p2"] == 0
    assert [d["id"] for d in hc["defects"]] == [d2["id"], d1["id"]]  # Open first
    assert (
        client.patch(
            f"{API}/defects/{d2['id']}", json={"priority": "P2"}, headers=headers("U10")
        ).json()["priority"]
        == "P2"
    )
    assert (
        client.patch(
            f"{API}/defects/{d2['id']}", json={"owner_user_id": "U99"}, headers=headers()
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{API}/defects/{d2['id']}", json={"title": " "}, headers=headers()
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{API}/defects/{d2['id']}", json={"title": "x"}, headers=headers("U13")
        ).status_code
        == 403
    )
    assert (
        client.patch(f"{API}/defects/DEF-999", json={"title": "x"}, headers=headers()).status_code
        == 404
    )

    assert [e.action for e in _audit(db, "HypercareDefect", d1["id"])] == ["created", "resolved"]
    assert [e.action for e in _audit(db, "HypercareDefect", d2["id"])] == ["created", "updated"]
    tev = _audit(db, "Transition", T)
    assert any(
        e.action == "hypercare_no_defects_confirmed"
        and e.after == {"hypercare_no_defects_confirmed": True}
        for e in tev
    )
    assert all(e.actor_type == "Human" for e in tev if e.action == "hypercare_no_defects_confirmed")


def test_untick_always_allowed_and_validation(client, headers, fresh_seed):
    url = f"{API}/transitions/{T}/defects"
    res = client.post(f"{url}/confirm-none", json={"confirmed": False}, headers=headers())
    assert res.status_code == 200 and res.json()["no_defects_confirmed"] is False
    assert (
        client.post(url, json={"title": "x", "priority": "P9"}, headers=headers()).status_code
        == 422
    )
    assert (
        client.post(url, json={"title": " ", "priority": "P1"}, headers=headers()).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"title": "x", "priority": "P1", "owner_user_id": "U99"}, headers=headers()
        ).status_code
        == 422
    )
    assert (
        client.post(url, json={"title": "x", "priority": "P1"}, headers=headers("U14")).status_code
        == 403
    )
    assert client.get(f"{API}/transitions/TR-9999/defects", headers=headers()).status_code == 404
