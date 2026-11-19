"""AI playbook eval metrics (spec 7.5, 8.7 j, FR-037): table, manual results, mock import."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditEvent
from app.seed.loader import eval_passes

API = "/api/v1"
T = "TR-0001"
OTHER_AI = "TR-0003"  # Agentic AI, Tier 2
NON_AI = "TR-0004"  # Normal


def _table(client, headers, tid=T, user="U01"):
    res = client.get(f"{API}/transitions/{tid}/eval-metrics", headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _failed(table):
    return sorted(r["metric_id"] for r in table["rows"] if r["status"] == "fail")


def _row(table, metric_id):
    return next(r for r in table["rows"] if r["metric_id"] == metric_id)


def test_flagship_table_fails_exactly_ev03_and_ev12(client, headers):
    table = _table(client, headers)
    assert table["tier"] == 2
    assert _failed(table) == ["EV-03", "EV-12"]
    assert table["failed_count"] == 2
    assert len(table["rows"]) == 38
    ev03 = _row(table, "EV-03")
    assert ev03["result_number"] == 3.1 and ev03["passed"] is False and ev03["operator"] == "<="
    assert ev03["value"] == 2.0 and ev03["evaluation"] == "auto"
    ev12 = _row(table, "EV-12")
    assert ev12["result_number"] == 84 and ev12["status"] == "fail"
    ev01 = _row(table, "EV-01")
    assert ev01["status"] == "pass" and ev01["passed"] is True
    # metrics without a result are "not evaluated" (warning only)
    assert _row(table, "EV-15")["status"] == "not evaluated"
    assert table["not_evaluated_count"] == 38 - 13
    assert table["not_evaluated_count"] + table["failed_count"] < len(table["rows"])
    assert table["targets_confirmed"] is False and "Targets currently identical" in table["banner"]
    ids = [r["metric_id"] for r in table["rows"]]
    assert ids == sorted(ids)  # sort_order follows the metric ids


def test_requires_header_and_404(client, headers):
    assert client.get(f"{API}/transitions/{T}/eval-metrics").status_code == 401
    assert (
        client.get(f"{API}/transitions/TR-9999/eval-metrics", headers=headers()).status_code == 404
    )


def test_non_ai_is_409(client, headers, fresh_seed):
    res = client.get(f"{API}/transitions/{NON_AI}/eval-metrics", headers=headers("U03"))
    assert res.status_code == 409
    assert res.json()["detail"] == "Eval metrics apply to AI flavours only"
    put = client.put(
        f"{API}/transitions/{NON_AI}/eval-results",
        json=[{"metric_id": "EV-01", "value_number": 95}],
        headers=headers("U03"),
    )
    assert put.status_code == 409
    imp = client.post(f"{API}/transitions/{NON_AI}/eval-results/import", headers=headers("U03"))
    assert imp.status_code == 409


def test_put_results_computes_pass_and_audits(client, headers, db, fresh_seed):
    url = f"{API}/transitions/{T}/eval-results"
    body = [
        {"metric_id": "EV-03", "value_number": 1.5, "passed": False},  # client 'passed' is ignored
        {"metric_id": "EV-15", "value_number": 70},
    ]
    res = client.put(url, json=body, headers=headers("U10"))  # PM may enter results
    assert res.status_code == 200, res.text
    table = res.json()
    assert _row(table, "EV-03")["status"] == "pass" and _row(table, "EV-03")["passed"] is True
    assert _row(table, "EV-15")["status"] == "fail"  # 70 < 75
    assert _failed(table) == ["EV-12", "EV-15"]
    assert _row(table, "EV-03")["source"] == "Manual" and _row(table, "EV-03")["evaluated_at"]
    assert table["failed_count"] == 2
    # GET returns the same
    assert _table(client, headers) == table

    db.expire_all()
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity == "EvalResult", AuditEvent.entity_id.in_(["EV-03", "EV-15"]))
            .order_by(AuditEvent.id)
        ).all()
    )
    by_metric = {e.entity_id: e for e in events}
    assert by_metric["EV-03"].actor_type == "Human" and by_metric["EV-03"].action == "updated"
    assert by_metric["EV-03"].before["value_number"] == 3.1
    assert (
        by_metric["EV-03"].after["value_number"] == 1.5
        and by_metric["EV-03"].after["passed"] is True
    )
    assert by_metric["EV-15"].before is None
    assert by_metric["EV-03"].transition_id == T


def test_put_results_manual_metric_toggle(client, headers, fresh_seed):
    url = f"{API}/transitions/{T}/eval-results"
    res = client.put(
        url, json=[{"metric_id": "EV-14", "passed": True, "value_text": "62%"}], headers=headers()
    )
    assert res.status_code == 200
    row = _row(res.json(), "EV-14")
    assert row["evaluation"] == "manual" and row["status"] == "pass" and row["result_text"] == "62%"
    res = client.put(url, json=[{"metric_id": "EV-14", "passed": False}], headers=headers())
    assert _row(res.json(), "EV-14")["status"] == "fail"


def test_put_results_validation_and_permissions(client, headers, fresh_seed):
    url = f"{API}/transitions/{T}/eval-results"
    assert (
        client.put(
            url, json=[{"metric_id": "EV-99", "value_number": 1}], headers=headers()
        ).status_code
        == 422
    )
    assert (
        client.put(url, json=[{"metric_id": "EV-03"}], headers=headers()).status_code == 422
    )  # auto needs a value
    assert (
        client.put(url, json=[{"metric_id": "EV-14"}], headers=headers()).status_code == 422
    )  # manual needs something
    res = client.put(url, json=[{"metric_id": "EV-03", "value_number": 1}], headers=headers("U12"))
    assert res.status_code == 403
    assert res.json()["detail"] == "Only the OR focal, PM or Architect can enter eval results"
    # nothing was applied by the failed batch
    assert _row(_table(client, headers), "EV-03")["result_number"] == 3.1
    # an invalid entry blocks the whole batch
    mixed = [{"metric_id": "EV-01", "value_number": 99}, {"metric_id": "EV-99", "value_number": 1}]
    assert client.put(url, json=mixed, headers=headers()).status_code == 422
    assert _row(_table(client, headers), "EV-01")["result_number"] == 92


def test_import_flagship_uses_seed_values(client, headers, db, fresh_seed):
    client.put(
        f"{API}/transitions/{T}/eval-results",
        json=[
            {"metric_id": "EV-03", "value_number": 1.0},
            {"metric_id": "EV-12", "value_number": 99},
        ],
        headers=headers(),
    )
    assert _failed(_table(client, headers)) == []
    res = client.post(f"{API}/transitions/{T}/eval-results/import", headers=headers("U11"))
    assert res.status_code == 200, res.text
    table = res.json()
    assert _failed(table) == ["EV-03", "EV-12"]
    assert _row(table, "EV-03")["result_number"] == 3.1
    assert _row(table, "EV-09")["result_number"] == 1740
    assert _row(table, "EV-03")["source"] == "Imported (mock)"
    assert _row(table, "EV-15")["status"] == "not evaluated"  # not part of the flagship seed
    db.expire_all()
    ev = db.scalars(
        select(AuditEvent).where(AuditEvent.entity == "EvalResult", AuditEvent.action == "imported")
    ).one()
    assert ev.actor_type == "Human" and ev.actor_user_id == "U11" and ev.entity_id == T
    assert ev.after["EV-03"]["value_number"] == 3.1
    assert (
        client.post(
            f"{API}/transitions/{T}/eval-results/import", headers=headers("U12")
        ).status_code
        == 403
    )


def test_import_other_ai_transition_is_deterministic_and_passes(client, headers, fresh_seed):
    first = client.post(f"{API}/transitions/{OTHER_AI}/eval-results/import", headers=headers("U10"))
    assert first.status_code == 200, first.text
    table = first.json()
    assert table["failed_count"] == 0 and table["not_evaluated_count"] == 0
    assert all(r["status"] == "pass" and r["source"] == "Imported (mock)" for r in table["rows"])
    for r in table["rows"]:
        if r["evaluation"] == "auto" and r["operator"]:
            assert eval_passes(r["operator"], r["value"], r["result_number"]) is True
    again = client.post(
        f"{API}/transitions/{OTHER_AI}/eval-results/import", headers=headers("U10")
    ).json()
    assert [r["result_number"] for r in again["rows"]] == [
        r["result_number"] for r in table["rows"]
    ]
    assert _table(client, headers, OTHER_AI)["failed_count"] == 0
    # values differ between metrics (not one constant)
    assert len({r["result_number"] for r in table["rows"] if r["result_number"] is not None}) > 5


def test_eval_tab_follows_the_has_eval_metrics_switch(client, headers, db, fresh_seed):
    from app.domain import cfg
    from app.models import FlavourRule

    flagship = client.get(f"{API}/transitions/TR-0001", headers=headers("U01")).json()
    assert flagship["has_eval_metrics"] is True
    assert (
        client.get(f"{API}/transitions/TR-0001/eval-metrics", headers=headers("U01")).status_code
        == 200
    )

    # Switch it off for the flagship's project type: the table is refused (409), nothing else changes.
    db.get(FlavourRule, flagship["project_type"]).has_eval_metrics = False
    db.commit()
    cfg.invalidate()
    assert (
        client.get(f"{API}/transitions/TR-0001/eval-metrics", headers=headers("U01")).status_code
        == 409
    )
    detail = client.get(f"{API}/transitions/TR-0001", headers=headers("U01")).json()
    assert detail["has_eval_metrics"] is False and detail["requires_tiering"] is True
