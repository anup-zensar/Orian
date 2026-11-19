"""CR-01 admin "Dropdown lists": GET/PUT /admin/option-lists/{key}/items, custom lists, the structural
lock, used values are deactivated (never lost), exactly one critical severity, audit."""

from __future__ import annotations

import pytest

from app.domain import cfg
from app.models import AuditEvent, Transition

API = "/api/v1"
ADMIN = "U16"


def _items(client, headers, key: str) -> dict:
    r = client.get(f"{API}/admin/option-lists/{key}/items", headers=headers(ADMIN))
    assert r.status_code == 200, r.text
    return r.json()


def _body(out: dict) -> dict:
    return {
        "items": [
            {
                "value": i["value"],
                "label": i["label"],
                "description": i["description"],
                "meta": i["meta"],
                "active": i["active"],
            }
            for i in out["items"]
        ]
    }


def _put(client, headers, key: str, body: dict, user: str = ADMIN):
    return client.put(f"{API}/admin/option-lists/{key}/items", json=body, headers=headers(user))


def _audit(db, entity: str):
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.entity == entity)
        .order_by(AuditEvent.id.desc())
        .all()
    )


def test_every_seeded_list_round_trips_unchanged(client, headers, fresh_seed) -> None:
    """What GET returns can always be saved again (no undeclared meta, no lost values)."""
    keys = [
        x["key"] for x in client.get(f"{API}/admin/option-lists", headers=headers(ADMIN)).json()
    ]
    assert len(keys) >= 30
    for key in keys:
        before = _items(client, headers, key)
        r = _put(client, headers, key, _body(before))
        assert r.status_code == 200, (key, r.text)
        after = r.json()
        assert [(i["value"], i["label"], i["active"]) for i in after["items"]] == [
            (i["value"], i["label"], i["active"]) for i in before["items"]
        ], key


def test_relabel_keeps_the_stored_value(client, headers, fresh_seed, db) -> None:
    body = _body(_items(client, headers, "severities"))
    body["items"][1]["label"] = "Serious"  # Major -> Serious
    out = _put(client, headers, "severities", body).json()
    assert [i["value"] for i in out["items"]] == ["Critical", "Major", "Minor"]
    assert out["items"][1]["label"] == "Serious"
    ref = client.get(f"{API}/reference").json()
    assert (
        next(o for o in ref["lists"]["severities"] if o["value"] == "Major")["label"] == "Serious"
    )
    assert ref["enums"]["severities"] == ["Critical", "Major", "Minor"]  # values, not labels
    assert cfg.option_label(db, "severities", "Major") == "Serious"
    assert out["notice"]


def test_add_and_reorder_values(client, headers, fresh_seed) -> None:
    body = _body(_items(client, headers, "regions"))
    first = body["items"].pop(0)
    body["items"].append(first)
    body["items"].insert(
        0, {"value": "Antarctica", "label": "Antarctica", "meta": {"markets": ["Base"]}}
    )
    out = _put(client, headers, "regions", body).json()
    values = [i["value"] for i in out["items"]]
    assert values[0] == "Antarctica" and values[-1] == first["value"]
    assert [i["sort_order"] for i in out["items"]] == list(range(len(values)))
    ref = client.get(f"{API}/reference").json()
    assert ref["regions"] == values
    # a duplicate value in one request is refused
    body["items"].append({"value": "Antarctica"})
    assert _put(client, headers, "regions", body).status_code == 422


def test_used_value_is_deactivated_not_removed(client, headers, fresh_seed, db) -> None:
    out = _items(client, headers, "severities")
    used = next(i for i in out["items"] if i["value"] != "Critical" and i["used_by"] > 0)
    body = _body(out)
    body["items"] = [i for i in body["items"] if i["value"] != used["value"]]  # omitted = removed
    r = _put(client, headers, "severities", body)
    assert r.status_code == 200, r.text
    after = {i["value"]: i for i in r.json()["items"]}
    assert after[used["value"]]["active"] is False  # kept, hidden from new records
    assert any(used["value"] in w for w in r.json()["warnings"])
    assert used["value"] not in client.get(f"{API}/reference").json()["enums"]["severities"]
    inactive = client.get(f"{API}/reference", params={"include_inactive": "true"}).json()
    assert used["value"] in [o["value"] for o in inactive["lists"]["severities"]]
    # an UNCHANGED existing record with that value stays valid
    cfg.validate_option(db, "severities", used["value"], current=used["value"])
    with pytest.raises(Exception, match="not an option"):
        cfg.validate_option(db, "severities", used["value"])


def test_unused_value_is_removed_and_inactive_flag_hides(client, headers, fresh_seed) -> None:
    body = _body(_items(client, headers, "regions"))
    body["items"].append({"value": "Atlantis", "label": "Atlantis"})
    assert _put(client, headers, "regions", body).status_code == 200
    body["items"].pop()  # Atlantis again, unused
    out = _put(client, headers, "regions", body).json()
    assert "Atlantis" not in [i["value"] for i in out["items"]] and out["warnings"] == []
    # sending active=false hides a value but keeps the row
    body["items"][0]["active"] = False
    out = _put(client, headers, "regions", body).json()
    assert out["items"][0]["active"] is False
    assert out["option_list"]["active_count"] == out["option_list"]["item_count"] - 1


def test_built_in_list_keeps_one_active_value(client, headers, fresh_seed) -> None:
    body = _body(_items(client, headers, "regions"))
    for item in body["items"]:
        item["active"] = False
    r = _put(client, headers, "regions", body)
    assert r.status_code == 422 and "at least one value" in r.json()["reasons"][0]


def test_structural_lists_accept_labels_only(client, headers, fresh_seed) -> None:
    out = _items(client, headers, "evidence_statuses")
    assert out["option_list"]["structural"] and out["option_list"]["lock_reason"]
    body = _body(out)
    body["items"][0]["label"] = "Sent in"  # relabel: fine
    assert _put(client, headers, "evidence_statuses", body).status_code == 200
    added = {"items": body["items"] + [{"value": "Parked"}]}
    r = _put(client, headers, "evidence_statuses", added)
    assert r.status_code == 422 and "cannot be added" in r.json()["reasons"][0]
    removed = {"items": body["items"][1:]}
    assert _put(client, headers, "evidence_statuses", removed).status_code == 422
    body["items"][1]["active"] = False
    assert _put(client, headers, "evidence_statuses", body).status_code == 422
    patch = client.patch(
        f"{API}/admin/option-lists/evidence_statuses",
        json={"group": "Elsewhere"},
        headers=headers(ADMIN),
    )
    assert patch.status_code == 422
    ok = client.patch(
        f"{API}/admin/option-lists/evidence_statuses",
        json={"label": "Evidence stages"},
        headers=headers(ADMIN),
    )
    assert ok.status_code == 200
    assert (
        client.delete(
            f"{API}/admin/option-lists/evidence_statuses", headers=headers(ADMIN)
        ).status_code
        == 409
    )


def test_exactly_one_severity_counts_as_critical(client, headers, fresh_seed, db) -> None:
    body = _body(_items(client, headers, "severities"))
    body["items"][1]["meta"]["counts_as_critical"] = True  # two now
    r = _put(client, headers, "severities", body)
    assert r.status_code == 422 and "Exactly one" in r.json()["reasons"][0]
    body["items"][0]["meta"]["counts_as_critical"] = False
    body["items"][1]["meta"]["counts_as_critical"] = False  # none
    assert _put(client, headers, "severities", body).status_code == 422
    body["items"][1]["meta"]["counts_as_critical"] = True  # moved to Major
    assert _put(client, headers, "severities", body).status_code == 200
    assert cfg.critical_severity(db) == "Major"


def test_evidence_type_needs_is_checked(client, headers, fresh_seed) -> None:
    body = _body(_items(client, headers, "evidence_types"))
    body["items"].append({"value": "Screenshot", "label": "Screenshot", "meta": {"needs": "file"}})
    assert _put(client, headers, "evidence_types", body).status_code == 200
    body["items"][-1]["meta"] = {"needs": "telepathy"}
    assert _put(client, headers, "evidence_types", body).status_code == 422
    body["items"][-1]["meta"] = {"made_up": 1}
    r = _put(client, headers, "evidence_types", body)
    assert r.status_code == 422 and "not a column" in r.json()["reasons"][0]


def test_custom_list_lifecycle(client, headers, fresh_seed) -> None:
    h = headers(ADMIN)
    r = client.post(
        f"{API}/admin/option-lists",
        json={"key": "cost_centres", "label": "Cost centres"},
        headers=h,
    )
    assert r.status_code == 201
    made = next(x for x in r.json() if x["key"] == "cost_centres")
    assert not made["is_builtin"] and not made["structural"] and made["group"] == "Custom lists"
    assert (
        client.post(
            f"{API}/admin/option-lists", json={"key": "cost_centres", "label": "x"}, headers=h
        ).status_code
        == 409
    )
    out = _put(
        client,
        headers,
        "cost_centres",
        {"items": [{"value": "CC-1", "label": "Retail"}, {"value": "CC-2"}]},
    ).json()
    assert [i["label"] for i in out["items"]] == ["Retail", "CC-2"]  # label falls back to the value
    # a field that offers the list blocks deleting it
    field = client.post(
        f"{API}/admin/intake-fields",
        json={"label": "Cost centre", "type": "select", "option_list": "cost_centres"},
        headers=h,
    )
    assert field.status_code == 201
    assert client.delete(f"{API}/admin/option-lists/cost_centres", headers=h).status_code == 409
    client.delete(f"{API}/admin/intake-fields/cf_cost_centre", headers=h)
    assert client.delete(f"{API}/admin/option-lists/cost_centres", headers=h).status_code == 200
    assert client.get(f"{API}/admin/option-lists/cost_centres/items", headers=h).status_code == 404
    assert (
        client.delete(f"{API}/admin/option-lists/regions", headers=h).status_code == 409
    )  # built in


def test_values_held_by_custom_fields_count_as_used(client, headers, fresh_seed, db) -> None:
    h = headers(ADMIN)
    client.post(f"{API}/admin/option-lists", json={"key": "tags", "label": "Tags"}, headers=h)
    _put(client, headers, "tags", {"items": [{"value": "red"}, {"value": "blue"}]})
    client.post(
        f"{API}/admin/intake-fields",
        json={"label": "Tag", "type": "select", "option_list": "tags"},
        headers=h,
    )
    db.get(Transition, "TR-0001").custom_fields = {"cf_tag": "red"}
    db.commit()
    out = _items(client, headers, "tags")
    assert {i["value"]: i["used_by"] for i in out["items"]} == {"red": 1, "blue": 0}
    r = _put(client, headers, "tags", {"items": []})  # both removed: red is used -> deactivated
    after = {i["value"]: i["active"] for i in r.json()["items"]}
    assert after == {"red": False}
    usage = client.get(
        f"{API}/admin/usage", params={"kind": "option", "key": "tags:red"}, headers=h
    ).json()
    assert usage["count"] == 1


def test_list_writes_are_audited_and_admin_only(client, headers, fresh_seed, db) -> None:
    body = _body(_items(client, headers, "regions"))
    body["items"][0]["label"] = "Renamed"
    assert _put(client, headers, "regions", body, user="U01").status_code == 403
    assert _put(client, headers, "regions", body).status_code == 200
    event = _audit(db, "config:option_lists")[0]
    assert event.actor_type == "Human" and event.actor_user_id == ADMIN
    assert event.entity_id == "regions" and event.action == "updated"
    assert (
        event.before["items"][0]["label"] != "Renamed"
        and event.after["items"][0]["label"] == "Renamed"
    )
    assert (
        client.put(
            f"{API}/admin/option-lists/nope/items", json={"items": []}, headers=headers(ADMIN)
        ).status_code
        == 404
    )
