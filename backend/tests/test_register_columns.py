"""Register columns (CR-03 item 6): project ID, custom-field columns, search, show_in_list."""

from __future__ import annotations

from app.domain import cfg
from app.models import IntakeField, Transition

API = "/api/v1"


def _list(client, headers, **params):
    res = client.get(f"{API}/transitions", params=params, headers=headers("U01"))
    assert res.status_code == 200, res.text
    return res.json()


def test_rows_carry_project_id_and_custom_fields(client, headers, db, fresh_seed):
    t = db.query(Transition).first()
    t.servicenow_project_id = "PRJ0041037"
    t.custom_fields = {"project_status": "Executing"}
    db.commit()
    row = next(r for r in _list(client, headers) if r["id"] == t.id)
    assert row["servicenow_project_id"] == "PRJ0041037"
    assert row["custom_fields"] == {"project_status": "Executing"}


def test_search_matches_project_id(client, headers, db, fresh_seed):
    t = db.query(Transition).first()
    t.servicenow_project_id = "PRJ0041037"
    db.commit()
    assert [r["id"] for r in _list(client, headers, q="prj0041037")] == [t.id]


def test_custom_filter_works_with_and_without_cf_prefix_in_key(client, headers, db, fresh_seed):
    a, b = db.query(Transition).limit(2).all()
    a.custom_fields = {"project_status": "Executing"}
    b.custom_fields = {"project_status": "Planning"}
    db.commit()
    ids = {r["id"] for r in _list(client, headers, cf_project_status="Executing")}
    assert a.id in ids and b.id not in ids


def test_show_in_list_flag_is_configurable(client, headers, db, fresh_seed):
    field = db.get(IntakeField, "project_status")
    assert field is not None and field.show_in_list is True
    res = client.patch(
        f"{API}/admin/intake-fields/project_status",
        json={"show_in_list": False},
        headers=headers("U16"),
    )
    assert res.status_code == 200, res.text
    cfg.invalidate()
    ref = client.get(f"{API}/reference", headers=headers("U01")).json()
    by_key = {f["key"]: f for f in ref["intake_fields"]}
    assert by_key["project_status"]["show_in_list"] is False
    assert by_key["application_tier"]["show_in_list"] is True


def test_control_tower_lists_every_portfolio_and_region(client, headers):
    ct = client.get(f"{API}/control-tower", headers=headers("U01")).json()
    ref = client.get(f"{API}/reference", headers=headers("U01")).json()
    assert ct["heatmap"]["portfolios"] == ref["portfolios"]
    assert [r["region"] for r in ct["readiness_by_region"]] == ref["regions"]
    assert len(ct["heatmap"]["gates"]) == 7
