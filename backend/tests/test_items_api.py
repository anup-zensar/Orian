"""Checklist items API (FR-031, BR-030, AC-06). Seed date 2026-11-16, flagship TR-0001 at SG4_ATD."""

from __future__ import annotations

from sqlalchemy import select

from app.domain.metrics import compute_metrics
from app.models import AuditEvent, Transition

API = "/api/v1"
T = "TR-0001"
# flagship rows (integer TransitionItem ids are stable for the seed)
S3_019 = 141  # Technical, In progress, open condition CON-001 (due SG4_ATD)
S02_012 = 87  # Compliance, Compliant with conditions, CON-002
S45_014 = 154  # Compliance, Non-compliant, exception EX-01
S45_035 = 175  # Compliance, Not started, SG4_ATD
SM_257 = 255  # Compliance, Not started, SG6_ATO
FW_068 = 68  # Business, Not started, SG6_ATO
FW_069 = 69  # Business, Not started, SG6_ATO
GATES = ["SG0", "SG2", "SG3", "SG4_ATD", "SG5_HYPERCARE", "SG6_ATO", "CLOSURE"]


def _items(client, headers, user="U01", **params):
    res = client.get(f"{API}/transitions/{T}/items", params=params, headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _row(client, headers, item_id, user="U01"):
    rows = _items(client, headers, user, all_gates=True, applicability="all")["items"]
    return next(r for r in rows if r["id"] == item_id)


def _patch(client, headers, item_id, body, user="U01"):
    return client.patch(f"{API}/items/{item_id}", json=body, headers=headers(user))


def _audit(db, entity_id, entity="TransitionItem"):
    db.expire_all()
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity == entity, AuditEvent.entity_id == str(entity_id))
            .order_by(AuditEvent.id)
        ).all()
    )


# --- list -----------------------------------------------------------------------------------------
def test_requires_header(client):
    assert client.get(f"{API}/transitions/{T}/items").status_code == 401


def test_unknown_transition_404(client, headers):
    assert client.get(f"{API}/transitions/TR-9999/items", headers=headers()).status_code == 404


def test_default_gate_is_current_gate_and_cuts_later_gates(client, headers):
    data = _items(client, headers)
    assert data["gate"] == "SG4_ATD"
    assert data["items"]
    assert all(GATES.index(i["gate"]) <= GATES.index("SG4_ATD") for i in data["items"])
    assert all(i["applicability"] == "Applies" for i in data["items"])
    everything = _items(client, headers, all_gates=True)
    assert len(everything["items"]) > len(data["items"])


def test_sort_order_gate_then_lens(client, headers):
    items = _items(client, headers, all_gates=True)["items"]
    lenses = ["Business", "Technical", "Compliance"]
    keys = [(GATES.index(i["gate"]), lenses.index(i["lens"])) for i in items]
    assert keys == sorted(keys)


def test_summary_matches_shared_readiness(client, headers, db):
    data = _items(client, headers)
    assert [s["lens"] for s in data["summary"]] == ["Business", "Technical", "Compliance"]
    metrics = compute_metrics(db, [db.get(Transition, T)])[0]
    for row in data["summary"]:
        lens = metrics.readiness.lenses[row["lens"]]
        assert row["readiness_pct"] == lens.readiness_pct
        assert (row["scope"], row["done"], row["open_gaps"], row["critical_gaps"]) == (
            lens.scope,
            lens.done,
            lens.open_gaps,
            lens.critical_gaps,
        )


def test_summary_ignores_row_filters(client, headers):
    base = _items(client, headers)["summary"]
    assert _items(client, headers, lens="Technical", status="Gap", q="zzz")["summary"] == base


def test_excluded_counts_and_filter(client, headers):
    data = _items(client, headers)
    assert data["excluded_count"] == 8
    assert data["excluded_by_tier_count"] == 8
    excluded = _items(client, headers, applicability="excluded", all_gates=True)["items"]
    assert len(excluded) == 8
    assert all(
        i["applicability"] == "Not applicable" and i["excluded_by"] == "tier" for i in excluded
    )


def test_filters(client, headers):
    gaps = _items(client, headers, status="Gap")["items"]
    assert gaps and all(i["status"] == "Gap" for i in gaps)
    comp = _items(client, headers, lens="Compliance")["items"]
    assert comp and all(i["lens"] == "Compliance" for i in comp)
    mine = _items(client, headers, user="U10", mine=True)["items"]
    assert mine and all(i["owner"]["id"] == "U10" for i in mine)
    owned = _items(client, headers, owner="U14", lens="Compliance")["items"]
    assert owned and all(i["owner"]["id"] == "U14" for i in owned)
    by_id = _items(client, headers, q="s3-019")["items"]
    assert [i["item_id"] for i in by_id] == ["S3-019"]
    by_owner = _items(client, headers, q="Fatima Khan", all_gates=True)["items"]
    assert by_owner and all(i["owner"]["name"] == "Fatima Khan" for i in by_owner)
    ai = _items(client, headers, source="AI_PLAYBOOK")["items"]
    assert ai and all(i["source"] == "AI_PLAYBOOK" for i in ai)


def test_unknown_gate_422(client, headers):
    res = client.get(f"{API}/transitions/{T}/items", params={"gate": "SG9"}, headers=headers())
    assert res.status_code == 422


def test_row_fields_conditions_and_exception(client, headers):
    cond = _row(client, headers, S3_019)
    assert cond["open_condition_id"] == "CON-001"
    assert cond["allowed_statuses"] == ["Not started", "In progress", "Complete", "Gap", "N/A"]
    exc = _row(client, headers, S45_014)
    assert exc["exception_ref"] == "EX-01"
    assert exc["design_effectiveness"] == "No"
    assert _row(client, headers, S02_012)["open_condition_id"] == "CON-002"


def test_can_edit_by_lens(client, headers):
    pm = _row(client, headers, S45_035, user="U10")
    assert pm["can_edit"] is False
    assert pm["edit_denied_reason"] == "Only IRM can set compliance status"
    assert _row(client, headers, S3_019, user="U10")["can_edit"] is True
    irm = _row(client, headers, S3_019, user="U14")
    assert irm["can_edit"] is False
    assert "OR focal" in irm["edit_denied_reason"]
    assert _row(client, headers, S45_035, user="U14")["can_edit"] is True


def test_not_launched_returns_empty(client, headers, db, fresh_seed):
    t = db.get(Transition, "TR-0002")
    t.assessment_launched_at = None
    db.commit()
    data = client.get(f"{API}/transitions/TR-0002/items", headers=headers()).json()
    assert data["items"] == []
    assert all(s["scope"] == 0 and s["done"] == 0 for s in data["summary"])
    assert data["excluded_count"] == 0


# --- AC-06: BR-030 + permissions ------------------------------------------------------------------
def test_gap_needs_severity_and_note(client, headers, db, fresh_seed):
    res = _patch(client, headers, FW_068, {"status": "Gap"})
    assert res.status_code == 409
    assert len(res.json()["reasons"]) == 2
    res = _patch(client, headers, FW_068, {"status": "Gap", "gap_severity": "Major"})
    assert res.status_code == 409
    assert any("note" in r for r in res.json()["reasons"])
    body = {"status": "Gap", "gap_severity": "Major", "note": "Vendor late"}
    res = _patch(client, headers, FW_068, body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "Gap" and out["gap_severity"] == "Major"
    assert out["last_updated_source"] == "Human" and out["last_updated_by"]["id"] == "U01"
    # leaving the gap clears the severity
    res = _patch(client, headers, FW_068, {"status": "In progress"})
    assert res.status_code == 200
    assert res.json()["gap_severity"] is None


def test_gap_uses_stored_note(client, headers, fresh_seed):
    assert _patch(client, headers, FW_068, {"note": "Vendor late"}).status_code == 200
    res = _patch(client, headers, FW_068, {"status": "Gap", "gap_severity": "Minor"})
    assert res.status_code == 200


def test_input_validation_422_and_404(client, headers):
    assert _patch(client, headers, FW_068, {"status": "Compliant"}).status_code == 422
    assert _patch(client, headers, FW_068, {"owner_user_id": "U99"}).status_code == 422
    assert _patch(client, headers, FW_068, {"gap_severity": "Huge"}).status_code == 422
    assert _patch(client, headers, 999999, {"note": "x"}).status_code == 404


def test_na_needs_reason_and_or_focal(client, headers, db, fresh_seed):
    res = _patch(client, headers, FW_068, {"status": "N/A"})
    assert res.status_code == 409
    assert any("reason" in r for r in res.json()["reasons"])
    # PM may update B/T statuses but not mark N/A
    body = {"status": "N/A", "na_reason": "Not needed"}
    res = _patch(client, headers, FW_068, body, user="U10")
    assert res.status_code == 403
    assert res.json()["detail"] == "Only the OR focal can confirm scope and applicability"
    res = _patch(client, headers, FW_068, body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "N/A" and out["applicability"] == "Not applicable"
    assert out["na_reason"] == "Not needed" and out["excluded_by"] is None
    # restore through applicability
    res = _patch(client, headers, FW_068, {"applicability": "Applies"})
    assert res.status_code == 200
    assert res.json()["status"] == "Not started" and res.json()["na_reason"] is None


def test_na_via_applicability_and_compliance_na_is_irm(client, headers, fresh_seed):
    res = _patch(client, headers, FW_069, {"applicability": "Not applicable"})
    assert res.status_code == 409
    res = _patch(client, headers, FW_069, {"applicability": "Not applicable", "na_reason": "Dup"})
    assert res.status_code == 200
    assert res.json()["status"] == "N/A"
    # the OR focal cannot mark a Compliance item N/A
    res = _patch(client, headers, SM_257, {"applicability": "Not applicable", "na_reason": "x"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Only IRM can set compliance status"
    res = _patch(client, headers, SM_257, {"status": "Not applicable"}, user="U14")
    assert res.status_code == 409
    body = {"status": "Not applicable", "na_reason": "No PII"}
    res = _patch(client, headers, SM_257, body, user="U14")
    assert res.status_code == 200
    assert res.json()["applicability"] == "Not applicable"
    assert res.json()["status"] == "Not applicable"


def test_status_change_on_excluded_item_needs_restore(client, headers, fresh_seed):
    rows = _items(client, headers, applicability="excluded", all_gates=True)["items"]
    bt = next(r for r in rows if r["lens"] != "Compliance")
    res = _patch(client, headers, bt["id"], {"status": "In progress"})
    assert res.status_code == 409
    res = _patch(client, headers, bt["id"], {"status": "In progress", "applicability": "Applies"})
    assert res.status_code == 200
    assert res.json()["applicability"] == "Applies" and res.json()["excluded_by"] is None


def test_compliance_is_irm_only_and_needs_design_effectiveness(client, headers, fresh_seed):
    res = _patch(client, headers, S45_035, {"status": "In review"}, user="U10")
    assert res.status_code == 403
    assert res.json()["detail"] == "Only IRM can set compliance status"
    assert res.json()["reasons"] == ["Only IRM can set compliance status"]
    assert _patch(client, headers, S45_035, {"status": "In review"}).status_code == 403
    res = _patch(client, headers, S45_035, {"status": "Compliant"}, user="U14")
    assert res.status_code == 409
    assert any("design effectiveness" in r for r in res.json()["reasons"])
    res = _patch(client, headers, S45_035, {"design_effectiveness": "Yes"}, user="U10")
    assert res.status_code == 403
    body = {"status": "Compliant", "design_effectiveness": "No"}
    assert _patch(client, headers, S45_035, body, user="U14").status_code == 409
    body = {"status": "Compliant", "design_effectiveness": "Yes"}
    res = _patch(client, headers, S45_035, body, user="U14")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "Compliant" and res.json()["design_effectiveness"] == "Yes"
    # DE downgrade while Compliant breaks the rule, N/A is fine
    de_no = {"design_effectiveness": "No"}
    assert _patch(client, headers, S45_035, de_no, user="U14").status_code == 409
    de_na = {"design_effectiveness": "N/A"}
    assert _patch(client, headers, S45_035, de_na, user="U14").status_code == 200


def test_design_effectiveness_not_for_business_items(client, headers, fresh_seed):
    res = _patch(client, headers, FW_068, {"design_effectiveness": "Yes"}, user="U14")
    assert res.status_code == 422


def test_note_and_owner_permissions(client, headers, fresh_seed):
    assert _patch(client, headers, FW_068, {"note": "hello"}, user="U10").status_code == 200
    assert _patch(client, headers, FW_068, {"owner_user_id": "U11"}, user="U12").status_code == 200
    assert _patch(client, headers, FW_068, {"note": "x"}, user="U14").status_code == 403
    assert _patch(client, headers, FW_068, {"note": "x"}, user="U13").status_code == 403
    # Compliance note: IRM (or the item's owner, here also IRM); PM is not
    assert _patch(client, headers, S45_035, {"note": "x"}, user="U10").status_code == 403
    assert _patch(client, headers, S45_035, {"note": "x"}, user="U14").status_code == 200


def test_compliant_with_conditions_creates_condition(client, headers, db, fresh_seed):
    res = _patch(client, headers, SM_257, {"status": "Compliant with conditions"}, user="U14")
    assert res.status_code == 409
    assert any("condition" in r for r in res.json()["reasons"])
    cond = {"owner_user_id": "U11", "due_gate": "SG6_ATO", "text": "Close pen-test findings"}
    early = {"status": "Compliant with conditions", "condition": {**cond, "due_gate": "SG3"}}
    assert _patch(client, headers, SM_257, early, user="U14").status_code == 409
    body = {"status": "Compliant with conditions", "condition": cond}
    res = _patch(client, headers, SM_257, body, user="U14")
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "Compliant with conditions"
    assert out["open_condition_id"] == "CON-003"
    conds = client.get(f"{API}/transitions/{T}/conditions", headers=headers()).json()
    new = next(c for c in conds if c["id"] == "CON-003")
    assert new["set_at_gate"] == "SG4_ATD" and new["due_gate"] == "SG6_ATO"
    assert new["owner"]["id"] == "U11" and new["status"] == "Open" and new["item_id"] == "SM-257"
    events = _audit(db, "CON-003", "Condition")
    assert events and events[0].actor_type == "Human" and events[0].action == "created"
    # same status again does not create another condition
    again = {"status": "Compliant with conditions", "note": "n"}
    assert _patch(client, headers, SM_257, again, user="U14").status_code == 200
    conds = client.get(f"{API}/transitions/{T}/conditions", headers=headers()).json()
    assert [c["id"] for c in conds if c["item_id"] == "SM-257"] == ["CON-003"]


def test_complete_leaves_open_condition_open(client, headers, fresh_seed):
    res = _patch(client, headers, S3_019, {"status": "Complete"}, user="U10")
    assert res.status_code == 200
    assert res.json()["open_condition_id"] == "CON-001"


def test_audit_before_after_actor_human(client, headers, db, fresh_seed):
    body = {"status": "Gap", "gap_severity": "Critical", "note": "No vendor"}
    assert _patch(client, headers, FW_068, body).status_code == 200
    events = _audit(db, FW_068)
    assert len(events) == 1
    ev = events[0]
    assert ev.actor_type == "Human" and ev.actor_user_id == "U01" and ev.action == "updated"
    assert ev.transition_id == T
    assert ev.before["status"] == "Not started" and ev.before["gap_severity"] is None
    assert ev.after["status"] == "Gap" and ev.after["gap_severity"] == "Critical"
    # no change -> no new audit row
    _patch(client, headers, FW_068, {"status": "Gap"})
    assert len(_audit(db, FW_068)) == 1


def test_closed_transition_is_read_only(client, headers, db, fresh_seed):
    db.get(Transition, T).status = "Closed"
    db.commit()
    res = _patch(client, headers, FW_068, {"note": "x"})
    assert res.status_code == 409
    assert _row(client, headers, FW_068)["can_edit"] is False


# --- bulk -----------------------------------------------------------------------------------------
def _bulk(client, headers, body, user="U01"):
    return client.post(f"{API}/items/bulk", json=body, headers=headers(user))


def test_bulk_owner_and_na(client, headers, db, fresh_seed):
    res = _bulk(client, headers, {"item_ids": [FW_068], "owner_user_id": "U11"}, user="U10")
    assert res.status_code == 403
    assert _bulk(client, headers, {"item_ids": [FW_068]}).status_code == 422
    blank = {"item_ids": [FW_068], "mark_na": {"reason": " "}}
    assert _bulk(client, headers, blank).status_code == 422
    assert _bulk(client, headers, {"item_ids": [FW_068], "owner_user_id": "U99"}).status_code == 422

    res = _bulk(client, headers, {"item_ids": [FW_068, FW_069], "owner_user_id": "U12"})
    assert res.status_code == 200
    assert res.json()["updated"] == [FW_068, FW_069] and res.json()["skipped"] == []
    assert _row(client, headers, FW_068)["owner"]["id"] == "U12"

    body = {"item_ids": [FW_068, SM_257, 999999, FW_069], "mark_na": {"reason": "Out of scope"}}
    data = _bulk(client, headers, body).json()
    assert data["updated"] == [FW_068, FW_069]
    skipped = {s["id"]: s["reason"] for s in data["skipped"]}
    assert "IRM" in skipped[SM_257] and skipped[999999] == "Item not found"
    row = _row(client, headers, FW_068)
    assert row["status"] == "N/A" and row["na_reason"] == "Out of scope"
    assert row["applicability"] == "Not applicable"
    again = _bulk(client, headers, {"item_ids": [FW_068], "mark_na": {"reason": "again"}}).json()
    assert again["updated"] == [] and again["skipped"][0]["reason"] == "Item is already N/A"
    events = _audit(db, FW_068)
    assert len(events) == 2 and all(e.actor_type == "Human" for e in events)
    assert events[-1].after["status"] == "N/A"


def test_bulk_other_focal_is_skipped(client, headers, fresh_seed):
    res = _bulk(client, headers, {"item_ids": [FW_068], "owner_user_id": "U11"}, user="U02")
    assert res.status_code == 200
    assert res.json()["updated"] == []
    assert "OR focal" in res.json()["skipped"][0]["reason"]
