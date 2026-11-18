"""Per-transition access on items, evidence and eval results (BE#1) plus BE#4, BE#5, BE#10, BE#11.

TR-0001 belongs to U01 Asha Menon (PM U10, architect U11, OLM U12, IRM U14); U02 Rahul Iyer is the
OR focal of another transition and must be refused. Item ids are stable for the seed.
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.eval import pass_state
from app.domain.readiness_check import load_gate_inputs
from app.models import EvalResult, EvalTarget, Transition, TransitionItem, User

API = "/api/v1"
T = "TR-0001"
FW_068 = 68  # Business, Not started, SG6_ATO
FW_069 = 69  # Business, Not started, SG6_ATO
S45_035 = 175  # Compliance, Not started, SG4_ATD


def _patch(client, headers, item_id, body, user="U01"):
    return client.patch(f"{API}/items/{item_id}", json=body, headers=headers(user))


def _item_id(db, playbook_id: str) -> int:
    db.expire_all()
    return db.scalars(
        select(TransitionItem.id).where(
            TransitionItem.transition_id == T, TransitionItem.playbook_item_id == playbook_id
        )
    ).one()


# --- items: assignment -----------------------------------------------------------------------------


def test_other_focal_cannot_update_items_of_the_transition(client, headers, fresh_seed):
    res = _patch(client, headers, FW_068, {"status": "In progress"}, user="U02")
    assert res.status_code == 403
    assert "Asha Menon" in res.json()["detail"]
    assert _patch(client, headers, FW_068, {"status": "In progress"}).status_code == 200


def test_assigned_pm_and_architect_may_update_business_technical_items(client, headers, fresh_seed):
    assert _patch(client, headers, FW_068, {"note": "pm"}, user="U10").status_code == 200
    assert _patch(client, headers, FW_068, {"note": "arch"}, user="U11").status_code == 200


def test_compliance_status_only_by_the_assigned_irm(client, headers, db, fresh_seed):
    db.add(User(id="U90", name="Second Irm", email="second.irm@example.test", role="IRM"))
    db.commit()
    res = _patch(client, headers, S45_035, {"status": "In review"}, user="U90")
    assert res.status_code == 403
    assert "Fatima Khan" in res.json()["detail"]
    assert _patch(client, headers, S45_035, {"status": "In review"}, user="U14").status_code == 200


def test_item_owner_exception_applies_to_a_pm_outside_the_transition(
    client, headers, db, fresh_seed
):
    db.add(User(id="U91", name="Other Pm", email="other.pm@example.test", role="PM"))
    db.commit()
    assert _patch(client, headers, FW_068, {"owner_user_id": "U91"}).status_code == 200
    assert _patch(client, headers, FW_068, {"status": "In progress"}, user="U91").status_code == 200
    # not the owner of FW-069: refused
    res = _patch(client, headers, FW_069, {"status": "In progress"}, user="U91")
    assert res.status_code == 403


def test_item_list_can_edit_follows_assignment(client, headers, fresh_seed):
    def can_edit(user):
        res = client.get(
            f"{API}/transitions/{T}/items", params={"all_gates": True}, headers=headers(user)
        )
        return next(r for r in res.json()["items"] if r["id"] == FW_068)

    assert can_edit("U01")["can_edit"] is True
    other = can_edit("U02")
    assert other["can_edit"] is False and "Asha Menon" in other["edit_denied_reason"]


# --- bulk -----------------------------------------------------------------------------------------


def test_bulk_skips_items_of_transitions_the_user_does_not_own(client, headers, fresh_seed):
    body = {"item_ids": [FW_068, FW_069], "owner_user_id": "U13"}
    res = client.post(f"{API}/items/bulk", json=body, headers=headers("U02"))
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["updated"] == []
    assert len(out["skipped"]) == 2 and "Asha Menon" in out["skipped"][0]["reason"]
    mine = client.post(f"{API}/items/bulk", json=body, headers=headers("U01"))
    assert sorted(mine.json()["updated"]) == [FW_068, FW_069]


def test_bulk_is_limited_to_500_ids(client, headers):
    body = {"item_ids": list(range(1, 502)), "owner_user_id": "U10"}
    assert client.post(f"{API}/items/bulk", json=body, headers=headers("U01")).status_code == 422


def test_huge_ids_give_validation_errors_not_500(client, headers):
    assert _patch(client, headers, 99999999999999999999, {"note": "x"}).status_code == 422


def test_note_limit(client, headers):
    assert _patch(client, headers, FW_068, {"note": "x" * 4001}).status_code == 422


# --- BE#4 / BE#10 ---------------------------------------------------------------------------------


def test_ocet_linked_item_cannot_be_completed_by_hand(client, headers, db, fresh_seed):
    fw_008 = _item_id(db, "FW-008")
    res = _patch(client, headers, fw_008, {"status": "Complete"})
    assert res.status_code == 409
    assert "OCET is Approved" in " ".join(res.json()["reasons"])
    assert _patch(client, headers, fw_008, {"status": "In progress"}).status_code == 200


def test_support_model_item_cannot_be_completed_by_hand(client, headers, db, fresh_seed):
    linked = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == T,
            TransitionItem.linked_module == "SUPPORT_MODEL",
            TransitionItem.applicability == "Applies",
            TransitionItem.status.in_(["Not started", "In progress"]),
        )
    ).first()
    assert linked is not None
    res = _patch(client, headers, linked.id, {"status": "Complete"})
    assert res.status_code == 409
    assert "support model is Agreed" in " ".join(res.json()["reasons"])


def test_tier_excluded_item_cannot_be_set_to_applies(client, headers, fresh_seed):
    rows = client.get(
        f"{API}/transitions/{T}/items",
        params={"applicability": "excluded", "all_gates": True},
        headers=headers("U01"),
    ).json()["items"]
    row = next(r for r in rows if r["excluded_by"] == "tier" and r["lens"] != "Compliance")
    res = _patch(client, headers, row["id"], {"applicability": "Applies"})
    assert res.status_code == 409
    assert "change the tier" in " ".join(res.json()["reasons"])


# --- evidence -------------------------------------------------------------------------------------


def _upload(client, headers, user, item_id="FW-068"):
    return client.post(
        f"{API}/transitions/{T}/evidence",
        data={"title": "Link", "type": "Link", "url": "https://example.com/x", "item_id": item_id},
        headers=headers(user),
    )


def test_evidence_upload_only_by_people_assigned_to_the_transition(client, headers, fresh_seed):
    denied = _upload(client, headers, "U02")
    assert denied.status_code == 403
    assert "Asha Menon" in denied.json()["detail"]
    assert _upload(client, headers, "U01").status_code == 201
    assert _upload(client, headers, "U11").status_code == 201


def test_evidence_review_only_by_the_assigned_focal(client, headers, fresh_seed):
    evidence_id = _upload(client, headers, "U01").json()["id"]
    review = {"decision": "Accept", "note": ""}
    denied = client.post(
        f"{API}/evidence/{evidence_id}/review", json=review, headers=headers("U02")
    )
    assert denied.status_code == 403
    ok = client.post(f"{API}/evidence/{evidence_id}/review", json=review, headers=headers("U01"))
    assert ok.status_code == 200, ok.text


def test_evidence_can_review_flag_follows_assignment(client, headers, fresh_seed):
    _upload(client, headers, "U01")
    rows = client.get(f"{API}/transitions/{T}/evidence", headers=headers("U02")).json()
    assert rows and all(r["can_review"] is False for r in rows)


# --- eval results ---------------------------------------------------------------------------------


def test_eval_results_only_by_assigned_people(client, headers, fresh_seed):
    url = f"{API}/transitions/{T}/eval-results"
    assert client.post(f"{url}/import", headers=headers("U02")).status_code == 403
    body = [{"metric_id": "EV-01", "value_number": 95}]
    assert client.put(url, json=body, headers=headers("U02")).status_code == 403
    assert client.post(f"{url}/import", headers=headers("U01")).status_code == 200


def test_eval_results_closed_transition_is_409(client, headers, db, fresh_seed):
    db.get(Transition, T).status = "Closed"
    db.commit()
    res = client.post(f"{API}/transitions/{T}/eval-results/import", headers=headers("U01"))
    assert res.status_code == 409


def test_pass_state_ignores_a_stale_stored_flag():
    target = EvalTarget(
        metric_id="EV-99",
        metric="m",
        tier=2,
        target_text="<= 2%",
        operator="<=",
        value=2.0,
        evaluation="auto",
    )
    stale = EvalResult(transition_id=T, metric_id="EV-99", value_number=1.5, passed=False)
    assert pass_state(target, stale) is True
    assert pass_state(target, EvalResult(transition_id=T, metric_id="EV-99")) is None
    assert pass_state(target, None) is None
    manual = EvalTarget(metric_id="EV-98", metric="m", tier=2, target_text="x", evaluation="manual")
    assert pass_state(manual, EvalResult(transition_id=T, metric_id="EV-98", passed=True)) is True


def test_readiness_follows_the_current_eval_targets(db, fresh_seed):
    t = db.get(Transition, T)
    before = load_gate_inputs(db, t, "SG4_ATD").ctx.failed_evals
    assert before, "the flagship has a failing eval metric in the seed"
    metric_id = before[0].metric_id
    target = db.scalars(
        select(EvalTarget).where(EvalTarget.metric_id == metric_id, EvalTarget.tier == t.risk_tier)
    ).one()
    result = db.scalars(
        select(EvalResult).where(EvalResult.transition_id == T, EvalResult.metric_id == metric_id)
    ).one()
    # the stored flag is stale (False) while the target is relaxed: the verdict follows the target
    result.passed = False
    relaxed = (
        (result.value_number or 0) + 1
        if target.operator in ("<=", "<")
        else ((result.value_number or 0) - 1)
    )
    target.value = relaxed
    db.commit()
    after = load_gate_inputs(db, t, "SG4_ATD").ctx.failed_evals
    assert metric_id not in [f.metric_id for f in after]
