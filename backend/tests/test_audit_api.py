"""Audit trail query (FR-110, spec 8.17, NFR-03, AC-13)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app import clock
from app.domain import audit
from app.models import AuditEvent, User

API = "/api/v1"
T = "TR-0001"


def _audit(client, headers, user="U01", **params):
    res = client.get(f"{API}/audit", params=params, headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _make_events(client, headers):
    """A few real writes by different people so the filters have something to chew on."""
    assert (
        client.patch(f"{API}/items/68", json={"note": "first"}, headers=headers("U01")).status_code
        == 200
    )
    assert (
        client.post(
            f"{API}/transitions/{T}/actions",
            json={"title": "Chase vendor", "owner_user_id": "U11", "due_date": "2026-11-20"},
            headers=headers("U10"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{API}/transitions/{T}/risks",
            json={"title": "Vendor lock-in", "rating": "Low"},
            headers=headers("U14"),
        ).status_code
        == 201
    )


def test_requires_header(client):
    assert client.get(f"{API}/audit").status_code == 401


def test_seed_events_present_and_newest_first(client, headers):
    data = _audit(client, headers)
    assert data["total"] > 0 and 0 < len(data["items"]) <= 100
    keys = [(i["at"], i["id"]) for i in data["items"]]
    assert keys == sorted(keys, reverse=True)
    first = data["items"][0]
    assert {
        "actor_name",
        "actor_type",
        "transition_name",
        "entity",
        "before",
        "after",
        "note",
    } <= set(first)


def test_filters_and_actor_types(client, headers, db, fresh_seed):
    _make_events(client, headers)
    # a Workflow rule event (AC-13 shows every actor type)
    audit.record(
        db,
        actor=None,
        actor_type="Workflow rule",
        entity="TransitionItem",
        entity_id=68,
        action="updated",
        transition_id=T,
        after={"status": "Complete"},
        note="OCET approved",
    )
    db.commit()

    by_transition = _audit(client, headers, transition_id=T, limit=500)
    assert by_transition["total"] >= 4
    assert all(i["transition_id"] == T for i in by_transition["items"])
    assert by_transition["items"][0]["transition_name"] == "Mobility Knowledge Agent"

    humans = _audit(client, headers, transition_id=T, actor_type="Human", limit=500)
    assert humans["total"] >= 3 and all(i["actor_type"] == "Human" for i in humans["items"])
    wf = _audit(client, headers, actor_type="Workflow rule", limit=500)
    assert wf["total"] >= 1
    assert wf["items"][0]["actor_name"] is None and wf["items"][0]["note"] == "OCET approved"
    system = _audit(client, headers, actor_type="System", limit=5)
    assert system["total"] > 0 and all(i["actor_type"] == "System" for i in system["items"])

    by_actor = _audit(client, headers, actor="U10", limit=500)
    assert by_actor["total"] >= 1
    assert all(i["actor_user_id"] == "U10" and i["actor_name"] for i in by_actor["items"])
    assert any(i["entity"] == "Action" for i in by_actor["items"])

    items = _audit(client, headers, entity="TransitionItem", transition_id=T, limit=500)["items"]
    assert items and all(i["entity"] == "TransitionItem" for i in items)
    item_row = next(i for i in items if i["actor_user_id"] == "U01")
    assert "note" in item_row["before"]
    assert item_row["after"]["note"] == "first"
    combined = _audit(client, headers, entity="Risk", actor="U14", transition_id=T)
    assert combined["total"] == 1 and combined["items"][0]["action"] == "created"
    assert _audit(client, headers, entity="Risk", actor="U10")["total"] == 0


def test_paging_and_total(client, headers, fresh_seed):
    _make_events(client, headers)
    everything = _audit(client, headers, transition_id=T, limit=500)
    total = everything["total"]
    page1 = _audit(client, headers, transition_id=T, limit=2, offset=0)
    page2 = _audit(client, headers, transition_id=T, limit=2, offset=2)
    assert page1["total"] == page2["total"] == total
    assert len(page1["items"]) == 2
    ids = [i["id"] for i in everything["items"]]
    assert [i["id"] for i in page1["items"]] == ids[:2]
    assert [i["id"] for i in page2["items"]] == ids[2:4]
    assert _audit(client, headers, transition_id=T, offset=total + 10)["items"] == []
    assert client.get(f"{API}/audit", params={"limit": 501}, headers=headers()).status_code == 422
    assert client.get(f"{API}/audit", params={"limit": 0}, headers=headers()).status_code == 422
    assert client.get(f"{API}/audit", params={"offset": -1}, headers=headers()).status_code == 422
    assert (
        client.get(f"{API}/audit", params={"actor_type": "Robot"}, headers=headers()).status_code
        == 422
    )


def test_date_filters_inclusive(client, headers, db, fresh_seed):
    today = clock.today()
    for day, note in (
        (datetime(2020, 1, 1, 0, 0, 0), "start"),
        (datetime(2020, 1, 2, 23, 59, 59), "end"),
    ):
        db.add(
            AuditEvent(
                at=day,
                actor_user_id=None,
                actor_type="System",
                transition_id="TR-0001",
                entity="Probe",
                entity_id="p",
                action="probe",
                note=note,
            )
        )
    db.commit()
    both = _audit(client, headers, entity="Probe", **{"from": "2020-01-01", "to": "2020-01-02"})
    assert both["total"] == 2
    assert [i["note"] for i in both["items"]] == ["end", "start"]  # newest first
    assert _audit(client, headers, entity="Probe", **{"from": "2020-01-02"})["total"] == 1
    assert _audit(client, headers, entity="Probe", to="2020-01-01")["total"] == 1
    assert _audit(client, headers, entity="Probe", **{"from": "2020-01-03"})["total"] == 0
    assert _audit(client, headers, entity="Probe", to="2019-12-31")["total"] == 0
    res = client.get(
        f"{API}/audit", params={"from": "2020-02-01", "to": "2020-01-01"}, headers=headers()
    )
    assert res.status_code == 422
    # today's writes are inside [today, today]
    _make_events(client, headers)
    todays = _audit(
        client, headers, transition_id=T, **{"from": today.isoformat(), "to": today.isoformat()}
    )
    assert todays["total"] >= 3


def test_every_storyline_write_has_an_actor_type(client, headers, db, fresh_seed):
    """AC-13: no audit row without an actor type from the allowed set."""
    _make_events(client, headers)
    db.expire_all()
    types = set(db.scalars(select(AuditEvent.actor_type)).all())
    assert types <= {"Human", "Workflow rule", "Orion agent", "System"}
    user_ids = {u for u in db.scalars(select(AuditEvent.actor_user_id)).all() if u}
    assert user_ids <= set(db.scalars(select(User.id)).all())
