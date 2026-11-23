"""OCET API (FR-060, BR-070, AC-09, storyline step 6)."""

from __future__ import annotations

import json

from sqlalchemy import select

from app.models import AuditEvent, OrionDraft, OutboxMessage, TransitionItem, User

API = "/api/v1"


def _view(client, headers, user="U01", tid="TR-0001"):
    res = client.get(f"{API}/transitions/{tid}/ocet", headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _line_in(line, **changes):
    body = {
        "id": line["id"],
        "line_key": line["line_key"],
        "category": line["category"],
        "description": line["description"],
        "vendor": line["vendor"],
        "pricing_basis": line["pricing_basis"],
        "base_amount": line["base_amount"],
        "growth_pct": line["growth_pct"],
        "year_overrides": line["year_overrides"],
        "override_reason": line["override_reason"],
        "input_owner_role": line["input_owner_role"],
        "input_owner_user_id": line["input_owner"]["id"] if line["input_owner"] else None,
        "input_status": line["input_status"],
    }
    body.update(changes)
    return body


def _save(client, headers, user, version_id, lines, deleted=()):
    return client.put(
        f"{API}/ocet/versions/{version_id}/lines",
        json={"lines": lines, "deleted_line_ids": list(deleted)},
        headers=headers(user),
    )


def _approve(client, headers, user, step, rid):
    return client.post(
        f"{API}/approvals/{rid}/steps/{step}/approve", json={}, headers=headers(user)
    )


def _with_l6(body, amount):
    lines = [_line_in(ln) for ln in body["lines"]]
    for item in lines:
        if item["line_key"] == "L6":
            item["base_amount"] = amount
    return lines


def test_seeded_view(client, headers):
    body = _view(client, headers)
    assert body["years"] == [2027, 2028, 2029, 2030, 2031]
    assert body["version"]["version"] == 2 and body["version"]["status"] == "Inputs pending"
    assert [v["status"] for v in body["versions"]] == ["Superseded", "Inputs pending"]
    lines = {ln["line_key"]: ln for ln in body["lines"]}
    assert len(lines) == 6
    l1 = lines["L1"]
    assert l1["base_amount"] == 100_000 and l1["growth_pct"] == 10
    assert round(l1["yearly"][-1]["amount"], 2) == 146_410
    l2 = lines["L2"]
    assert l2["year_overrides"] == {"2028": 30} or l2["year_overrides"] == {2028: 30}
    assert round(l2["yearly"][1]["amount"], 2) == 52_000
    l6 = lines["L6"]
    assert l6["base_amount"] is None and l6["input_status"] == "Requested"
    assert l6["yearly"][0]["amount"] == 0
    assert body["version"]["inputs_pending"] and body["version"]["missing_line_ids"] == [l6["id"]]
    assert body["version"]["can_edit"] is True and body["version"]["can_submit"] is False
    assert any("base amount missing" in r for r in body["version"]["submit_denied_reasons"])
    assert body["variance"]["previous_version"] == 1
    assert body["variance"]["total_abs"] > 0
    assert body["explanation"] and "vs v1" in body["explanation"]
    assert body["approval"] is None
    assert body["total_label"].endswith(("M", "k"))
    assert "AI tokens / inference" in body["categories"]
    other = _view(client, headers, "U12")
    assert other["version"]["can_edit"] is False and other["version"]["edit_denied_reason"]


def test_not_found(client, headers):
    assert client.get(f"{API}/transitions/TR-9999/ocet", headers=headers()).status_code == 404
    res = client.get(f"{API}/transitions/TR-0014/ocet", headers=headers())
    assert res.status_code == 404


def test_create_estimate_and_permissions(client, headers, fresh_seed):
    denied = client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U12"))
    assert denied.status_code == 403 and denied.json()["reasons"]
    assert client.post(f"{API}/transitions/TR-9999/ocet", headers=headers()).status_code == 404
    res = client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U01"))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["estimate"]["horizon_years"] == 5 and body["estimate"]["currency"] == "USD"
    assert body["version"]["status"] == "Draft" and body["lines"] == []
    assert body["explanation"] is None and body["total"] == 0
    assert client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U01")).status_code == 409


def test_save_validation_and_permissions(client, headers, fresh_seed):
    body = _view(client, headers)
    vid = body["version"]["id"]
    l1 = body["lines"][0]
    assert _save(client, headers, "U12", vid, [_line_in(l1)]).status_code == 403
    assert _save(client, headers, "U01", 99999, [_line_in(l1)]).status_code == 404
    bad = [
        _line_in(l1, category="Nope"),
        _line_in(l1, pricing_basis="Nope"),
        _line_in(l1, year_overrides={"2040": 10}, override_reason="x"),
        _line_in(l1, year_overrides={"2028": 10}, override_reason=None),
        _line_in(l1, id=987654),
    ]
    for item in bad:
        res = _save(client, headers, "U01", vid, [item])
        assert res.status_code == 422, item
        assert res.json()["reasons"]
    assert _save(client, headers, "U01", vid, [_line_in(l1, growth_pct=1500)]).status_code == 422
    assert _save(client, headers, "U01", vid, [_line_in(l1)], deleted=[987654]).status_code == 422
    assert _view(client, headers)["version"]["status"] == "Inputs pending"


def test_save_add_and_delete_lines(client, headers, fresh_seed):
    body = _view(client, headers)
    vid = body["version"]["id"]
    l2 = body["lines"][1]
    new = {
        "category": "Licences",
        "description": "Extra licence",
        "base_amount": 1000,
        "growth_pct": 0,
    }
    keep = [_line_in(ln) for ln in body["lines"] if ln["id"] != l2["id"]]
    res = _save(client, headers, "U10", vid, [*keep, new], deleted=[l2["id"]])
    assert res.status_code == 200, res.text
    out = res.json()
    keys = [ln["line_key"] for ln in out["lines"]]
    assert len(keys) == 6 and len(set(keys)) == 6 and keys[0] == "L1"
    assert keys[-1] == "L7"  # a deleted line key is never reused (compare matches by key)
    assert out["version"]["status"] == "Inputs pending"
    assert out["lines"][-1]["input_status"] == "Provided"


def test_storyline_step_6(client, headers, db, fresh_seed):
    body = _view(client, headers)
    vid = body["version"]["id"]
    l6 = next(ln for ln in body["lines"] if ln["line_key"] == "L6")
    total_before = body["total"]
    mei = db.get(User, "U11")

    res = client.post(
        f"{API}/ocet/versions/{vid}/request-inputs",
        json={"line_ids": [l6["id"]]},
        headers=headers("U01"),
    )
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["lines_requested"] == [l6["id"]] and len(out["draft_ids"]) == 1
    draft = db.get(OrionDraft, out["draft_ids"][0])
    assert draft.kind == "Input request" and draft.status == "Draft"
    assert draft.created_source == "Orion agent" and draft.to == [mei.email]
    assert "/transitions/TR-0001/ocet" in draft.body_html
    assert db.scalar(select(OutboxMessage.id).where(OutboxMessage.subject == draft.subject)) is None

    l1 = next(ln for ln in body["lines"] if ln["line_key"] == "L1")
    for ids in ([l1["id"]], []):
        bad = client.post(
            f"{API}/ocet/versions/{vid}/request-inputs",
            json={"line_ids": ids},
            headers=headers("U01"),
        )
        assert bad.status_code == 422

    blocked = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01"))
    assert blocked.status_code == 409 and blocked.json()["reasons"]

    res = _save(client, headers, "U11", vid, _with_l6(body, 10_000))
    assert res.status_code == 200, res.text
    saved = res.json()
    assert saved["version"]["status"] == "Draft" and saved["version"]["can_submit"] is True
    assert saved["total"] > total_before
    assert all(ln["input_status"] == "Provided" for ln in saved["lines"])

    res = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01"))
    assert res.status_code == 200, res.text
    sub = res.json()
    assert sub["version"]["status"] == "Submitted"
    assert [v["status"] for v in sub["versions"]] == ["Superseded", "Submitted"]
    rid = sub["approval"]["request_id"]
    assert [s["role"] for s in sub["approval"]["steps"]] == ["PLANNER", "OLM"]
    assert sub["approval"]["steps"][0]["approver"]["id"] == "U13"
    assert sub["version"]["can_edit"] is False and sub["version"]["edit_denied_reason"]
    assert _save(client, headers, "U01", vid, _with_l6(body, 1)).status_code == 409
    again = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01"))
    assert again.status_code == 409
    nv = client.post(f"{API}/transitions/TR-0001/ocet/new-version", headers=headers("U01"))
    assert nv.status_code == 409
    req = client.get(f"{API}/approvals/{rid}", headers=headers("U13")).json()
    assert req["subject_label"].startswith("OCET v2 · 5-year total ")
    assert req["subject_label"].count("USD") == 1

    cards = db.scalars(select(OutboxMessage).where(OutboxMessage.channel == "Teams")).all()
    text = " ".join(json.dumps(c.adaptive_card_json) for c in cards if c.adaptive_card_json)
    assert "OCET approval request" in text and "5-year total" in text and "v2" in text

    assert _approve(client, headers, "U12", 1, rid).status_code == 403

    assert _approve(client, headers, "U13", 1, rid).status_code == 200
    mid = _view(client, headers)
    assert mid["version"]["status"] == "Planner approved"
    assert mid["approval"]["steps"][0]["status"] == "Approved"

    assert _approve(client, headers, "U12", 2, rid).status_code == 200
    done = _view(client, headers)
    assert done["version"]["status"] == "Approved"
    db.expire_all()
    items = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == "TR-0001",
            TransitionItem.playbook_item_id.in_(["FW-008", "S45-006"]),
        )
    ).all()
    assert {i.playbook_item_id for i in items} == {"FW-008", "S45-006"}
    assert all(i.status == "Complete" and i.last_updated_source == "Workflow rule" for i in items)
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "TransitionItem",
            AuditEvent.actor_type == "Workflow rule",
            AuditEvent.note == "OCET v2 approved",
        )
    ).all()
    assert len(events) == 2

    res = client.post(f"{API}/transitions/TR-0001/ocet/new-version", headers=headers("U10"))
    assert res.status_code == 201, res.text
    v3 = res.json()
    assert v3["version"]["version"] == 3 and v3["version"]["status"] == "Draft"
    assert [ln["line_key"] for ln in v3["lines"]] == [ln["line_key"] for ln in done["lines"]]
    assert abs(v3["variance"]["total_abs"]) < 1e-6
    assert all(r["status"] == "same" for r in v3["variance"]["by_line"])


def test_reject_chain_marks_version_rejected(client, headers, fresh_seed):
    body = _view(client, headers)
    vid = body["version"]["id"]
    assert _save(client, headers, "U11", vid, _with_l6(body, 5_000)).status_code == 200
    sub = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01")).json()
    rid = sub["approval"]["request_id"]
    res = client.post(
        f"{API}/approvals/{rid}/steps/1/reject",
        json={"comment": "Too high"},
        headers=headers("U13"),
    )
    assert res.status_code == 200, res.text
    out = _view(client, headers)
    assert out["version"]["status"] == "Rejected"
    assert out["approval"]["status"] == "Rejected"
    assert out["versions"][0]["status"] == "Superseded"
    nv = client.post(f"{API}/transitions/TR-0001/ocet/new-version", headers=headers("U01"))
    assert nv.status_code == 201


def test_compare(client, headers):
    body = _view(client, headers)
    v1, v2 = body["versions"]
    res = client.get(
        f"{API}/ocet/compare", params={"from": v1["id"], "to": v2["id"]}, headers=headers("U12")
    )
    assert res.status_code == 200, res.text
    cmp = res.json()
    rows = {r["key"]: r for r in cmp["rows"]}
    assert rows["L6"]["status"] == "added" and rows["L6"]["pct_change"] is None
    assert rows["L2"]["status"] == "changed" and rows["L2"]["abs_change"] > 0
    assert rows["L1"]["status"] == "same"
    assert len(rows["L1"]["from_yearly"]) == 5
    assert cmp["from_version"]["version"] == 1 and cmp["to_version"]["version"] == 2
    assert abs(cmp["total_abs"] - (cmp["to_total"] - cmp["from_total"])) < 1e-6
    assert cmp["category_rows"]
    missing = client.get(
        f"{API}/ocet/compare", params={"from": 99999, "to": v2["id"]}, headers=headers()
    )
    assert missing.status_code == 404


def test_compare_different_estimates(client, headers, fresh_seed):
    seeded = _view(client, headers)["version"]["id"]
    other = client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U01")).json()
    res = client.get(
        f"{API}/ocet/compare",
        params={"from": seeded, "to": other["version"]["id"]},
        headers=headers(),
    )
    assert res.status_code == 422


def test_huge_ids_and_nan_are_422_not_500(client, headers):
    h = headers("U11")
    huge = 10**25
    assert (
        client.put(f"/api/v1/ocet/versions/{huge}/lines", json={"lines": []}, headers=h).status_code
        == 422
    )
    assert (
        client.get("/api/v1/ocet/compare", params={"from": huge, "to": 1}, headers=h).status_code
        == 422
    )
    assert client.post(f"/api/v1/support-models/{huge}/pptx", headers=h).status_code == 422
    nan_body = b'{"lines":[{"category":"Hosting","base_amount":NaN}]}'
    res = client.put(
        "/api/v1/ocet/versions/2/lines",
        content=nan_body,
        headers={**h, "content-type": "application/json"},
    )
    assert res.status_code == 422


def test_huge_base_amount_is_422(client, headers, fresh_seed):
    body = _view(client, headers)
    lines = [_line_in(ln) for ln in body["lines"]]
    lines[0]["base_amount"] = 1e300
    lines[0]["growth_pct"] = 1000
    res = _save(client, headers, "U10", body["version"]["id"], lines)
    assert res.status_code == 422, res.text


def test_format_labels_tolerate_extremes():
    from app.rules.ocet import format_k, format_total_label

    for value in (1e300, float("inf"), float("nan"), -1e308):
        assert isinstance(format_total_label(value), str)
        assert isinstance(format_k(value), str)


def test_deleted_line_key_not_reused_and_compare_shows_removed_added(client, headers, fresh_seed):
    body = _view(client, headers)
    vid = body["version"]["id"]
    l5 = next(ln for ln in body["lines"] if ln["line_key"] == "L5")
    keep = [_line_in(ln) for ln in body["lines"] if ln["id"] != l5["id"]]
    new = {"category": "Licences", "description": "Brand new audit", "base_amount": 5000}
    out = _save(client, headers, "U10", vid, [*keep, new], deleted=[l5["id"]])
    assert out.status_code == 200, out.text
    keys = [ln["line_key"] for ln in out.json()["lines"]]
    assert keys[-1] != "L5" and len(set(keys)) == len(keys)
    res = client.get(f"{API}/ocet/compare?from=1&to=2", headers=headers("U01")).json()
    rows = {r["key"]: r["status"] for r in res["rows"]}
    assert rows.get("L5") == "removed"
    assert "added" in rows.values()


def test_override_for_start_year_is_rejected(client, headers, fresh_seed):
    body = _view(client, headers)
    lines = [_line_in(ln) for ln in body["lines"]]
    lines[0]["year_overrides"] = {"2027": 50}
    lines[0]["override_reason"] = "x"
    res = _save(client, headers, "U10", body["version"]["id"], lines)
    assert res.status_code == 422, res.text


def test_rejected_version_stays_rejected_after_next_submit(client, headers, fresh_seed):
    body = _view(client, headers)
    vid = body["version"]["id"]
    assert _save(client, headers, "U11", vid, _with_l6(body, 5_000)).status_code == 200
    sub = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01")).json()
    rid = sub["approval"]["request_id"]
    client.post(
        f"{API}/approvals/{rid}/steps/1/reject", json={"comment": "no"}, headers=headers("U13")
    )
    nv = client.post(f"{API}/transitions/TR-0001/ocet/new-version", headers=headers("U01"))
    assert nv.status_code == 201
    v3 = _view(client, headers)
    sub = client.post(f"{API}/ocet/versions/{v3['version']['id']}/submit", headers=headers("U01"))
    assert sub.status_code == 200, sub.text
    statuses = [v["status"] for v in _view(client, headers)["versions"]]
    assert statuses[:2] == ["Superseded", "Rejected"]


def test_completion_hook_skips_not_applicable_item(client, headers, db, fresh_seed):
    item = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == "TR-0001", TransitionItem.playbook_item_id == "FW-008"
        )
    ).one()
    item.applicability = "Not applicable"
    before, item_id = item.status, item.id
    db.commit()
    body = _view(client, headers)
    vid = body["version"]["id"]
    assert _save(client, headers, "U11", vid, _with_l6(body, 5_000)).status_code == 200
    sub = client.post(f"{API}/ocet/versions/{vid}/submit", headers=headers("U01")).json()
    rid = sub["approval"]["request_id"]
    assert _approve(client, headers, "U13", 1, rid).status_code == 200
    assert _approve(client, headers, "U12", 2, rid).status_code == 200
    db.expire_all()
    assert db.get(TransitionItem, item_id).status == before
