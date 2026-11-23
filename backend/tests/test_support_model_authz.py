"""Support model per-transition access (BE#1 / M7-SUPPORT)."""

from __future__ import annotations

from tests.test_support_model_api import API, TXT, _generate, _inputs, _put


def test_only_assigned_people_edit(client, headers, fresh_seed):
    # U02 is an OR focal, but not of TR-0001
    assert _inputs(client, headers, user="U02", files=TXT).status_code == 403
    gen = client.post(f"{API}/transitions/TR-0001/support-model/generate", headers=headers("U02"))
    assert gen.status_code == 403
    model = _generate(client, headers, user="U11")["support_model"]
    sid, ls = model["id"], model["landscape"]
    assert _put(client, headers, sid, ls, "U02").status_code == 403
    assert _put(client, headers, sid, ls, "U01").status_code == 200
    for user in ("U02", "U16"):
        for path in (f"/support-models/{sid}/send-for-review", f"/support-models/{sid}/pptx"):
            assert client.post(f"{API}{path}", headers=headers(user)).status_code == 403, path
        draft = client.post(f"{API}/support-models/{sid}/questions/0/draft", headers=headers(user))
        assert draft.status_code == 403
    pptx = client.post(f"{API}/support-models/{sid}/pptx", headers=headers("U11"))
    assert pptx.status_code == 200


def test_other_focal_owns_own_transition_only(client, headers, db, fresh_seed):
    from app.models import Transition

    db.get(Transition, "TR-0014").or_focal_user_id = "U02"  # the seed has one focal only
    db.commit()
    assert _inputs(client, headers, "TR-0014", "U01", files=TXT).status_code == 403
    assert _inputs(client, headers, "TR-0014", "U02", files=TXT).status_code == 200


def test_view_stays_open_and_can_edit_follows_assignment(client, headers, fresh_seed):
    url = f"{API}/transitions/TR-0001/support-model"
    mine = client.get(url, headers=headers("U01")).json()
    assert mine["can_edit"] is True
    other = client.get(url, headers=headers("U02"))
    assert other.status_code == 200
    body = other.json()
    assert body["can_edit"] is False and "Asha Menon" in body["edit_denied_reason"]


def test_closed_transition_blocks_writes(client, headers, db, fresh_seed):
    from app.models import Transition

    db.get(Transition, "TR-0001").status = "Closed"
    db.commit()
    assert _inputs(client, headers, user="U01", files=TXT).status_code == 409
    view = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U01")).json()
    assert view["can_edit"] is False and "closed" in view["edit_denied_reason"]


def test_storyline_step_7_still_works(client, headers, fresh_seed):
    model = _generate(client, headers, user="U01")["support_model"]
    sid = model["id"]
    res = client.post(f"{API}/support-models/{sid}/send-for-review", headers=headers("U11"))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "In review"
