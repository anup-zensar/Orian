"""OCET per-transition access (BE#1 / M6-OCET): only the people assigned to TR-0001 edit its OCET."""

from __future__ import annotations

from tests.test_ocet_api import API, _line_in, _save, _view, _with_l6


def _ctx(client, headers):
    body = _view(client, headers)
    return body, body["version"]["id"]


def test_save_lines_only_assigned_people(client, headers, fresh_seed):
    body, vid = _ctx(client, headers)
    lines = [_line_in(ln) for ln in body["lines"]]
    for user in ("U02", "U12", "U13", "U14", "U15", "U16"):
        res = _save(client, headers, user, vid, lines)
        assert res.status_code == 403, (user, res.text)
    for user in ("U11", "U10", "U01"):
        assert _save(client, headers, user, vid, lines).status_code == 200, user


def test_request_inputs_submit_and_new_version_denied_to_other_focal(client, headers, fresh_seed):
    body, vid = _ctx(client, headers)
    l6 = next(ln for ln in body["lines"] if ln["line_key"] == "L6")
    res = client.post(
        f"{API}/ocet/versions/{vid}/request-inputs",
        json={"line_ids": [l6["id"]]},
        headers=headers("U02"),
    )
    assert res.status_code == 403
    submit = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U02"))
    assert submit.status_code == 403
    nv = client.post(f"{API}/transitions/TR-0001/ocet/new-version", headers=headers("U02"))
    assert nv.status_code == 403
    ok = client.post(
        f"{API}/ocet/versions/{vid}/request-inputs",
        json={"line_ids": [l6["id"]]},
        headers=headers("U01"),
    )
    assert ok.status_code == 200


def test_create_estimate_denied_to_other_focal(client, headers, db, fresh_seed):
    from app.models import Transition

    db.get(Transition, "TR-0014").or_focal_user_id = "U02"  # the seed has one focal only
    db.commit()
    assert client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U01")).status_code == 403
    assert client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U02")).status_code == 201


def test_can_edit_and_tooltip_follow_assignment(client, headers, fresh_seed):
    mine = _view(client, headers, "U01")["version"]
    assert mine["can_edit"] is True and mine["edit_denied_reason"] is None
    other = _view(client, headers, "U02")["version"]
    assert other["can_edit"] is False
    assert "Asha Menon" in other["edit_denied_reason"]
    admin = _view(client, headers, "U16")["version"]
    assert admin["can_edit"] is False and admin["edit_denied_reason"]


def test_closed_transition_freezes_ocet(client, headers, db, fresh_seed):
    from app.models import Transition

    body, vid = _ctx(client, headers)
    db.get(Transition, "TR-0001").status = "Closed"
    db.commit()
    res = _save(client, headers, "U11", vid, _with_l6(body, 1))
    assert res.status_code == 409
    view = _view(client, headers, "U01")["version"]
    assert view["can_edit"] is False and "closed" in view["edit_denied_reason"]


def test_bulk_limits_are_422(client, headers, fresh_seed):
    _, vid = _ctx(client, headers)
    res = client.post(
        f"{API}/ocet/versions/{vid}/request-inputs",
        json={"line_ids": list(range(1, 600))},
        headers=headers("U01"),
    )
    assert res.status_code == 422
    huge = client.put(
        f"{API}/ocet/versions/{2**40}/lines", json={"lines": []}, headers=headers("U11")
    )
    assert huge.status_code == 422
