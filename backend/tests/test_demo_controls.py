"""Demo controls (spec 8.16, 13 step 9, AC-07 second half): reset, today override, fast-forward."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app import clock
from app.config import get_settings
from app.models import AuditEvent, EvalResult, TransitionItem

API = "/api/v1"
ADMIN = "U16"


@pytest.fixture(autouse=True)
def _clear_override():
    clock.set_today_override(None)
    yield
    clock.set_today_override(None)


def test_demo_routes_404_when_demo_mode_off(client, headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    h = headers(ADMIN)
    assert client.post(f"{API}/admin/demo/reset", headers=h).status_code == 404
    assert client.post(f"{API}/admin/demo/fast-forward", json={}, headers=h).status_code == 404
    assert client.get(f"{API}/admin/demo/today", headers=h).status_code == 404
    assert client.post(f"{API}/admin/demo/today", json={"date": None}, headers=h).status_code == 404


def test_reset_is_idempotent_and_fast(client, headers, fresh_seed):
    h = headers(ADMIN)
    first = client.post(f"{API}/admin/demo/reset", headers=h)
    assert first.status_code == 200, first.text
    second = client.post(f"{API}/admin/demo/reset", headers=h).json()
    for out in (first.json(), second):
        assert out["seconds"] < 10
        assert out["transitions"] == 6 and out["items"] > 100
    assert second["transitions"] == first.json()["transitions"]
    assert second["items"] == first.json()["items"]
    # still usable afterwards
    assert client.get(f"{API}/transitions/TR-0001", headers=headers("U01")).status_code == 200


def test_reset_discards_changes_and_clears_today(client, headers, fresh_seed):
    h = headers(ADMIN)
    client.post(f"{API}/admin/demo/today", json={"date": "2026-12-01"}, headers=h)
    client.put(
        f"{API}/admin/reminder-rules",
        json={"rules": [{"id": "R1", "enabled": False, "params": {}}]},
        headers=h,
    )
    client.post(f"{API}/admin/demo/reset", headers=h)
    assert clock.get_today_override() is None
    rules = client.get(f"{API}/admin/reminder-rules", headers=h).json()
    assert rules[0]["enabled"] is True
    today = client.get(f"{API}/admin/demo/today", headers=h).json()
    assert today["override"] is None and today["today"] == "2026-11-16"


def test_today_override(client, headers, fresh_seed, db):
    h = headers(ADMIN)
    base = client.get(f"{API}/admin/demo/today", headers=h).json()
    assert base == {"today": "2026-11-16", "override": None, "seed_date": "2026-11-16"}
    before = {
        t["id"]: t["days_to_next_decision"]
        for t in client.get(f"{API}/transitions", headers=headers("U01")).json()
    }
    assert before["TR-0001"] is not None

    res = client.post(f"{API}/admin/demo/today", json={"date": "2026-11-20"}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["today"] == "2026-11-20" and res.json()["override"] == "2026-11-20"
    assert clock.today() == date(2026, 11, 20)
    after = {
        t["id"]: t["days_to_next_decision"]
        for t in client.get(f"{API}/transitions", headers=headers("U01")).json()
    }
    assert after["TR-0001"] == before["TR-0001"] - 4

    from app.models import AppSetting

    db.expire_all()
    assert db.get(AppSetting, "today_override").value == "2026-11-20"
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity == "AppSetting")).all()
    assert events and events[-1].actor_type == "Human"

    cleared = client.post(f"{API}/admin/demo/today", json={"date": None}, headers=h).json()
    assert cleared["override"] is None and cleared["today"] == "2026-11-16"
    assert clock.today() == date(2026, 11, 16)
    db.expire_all()
    assert db.get(AppSetting, "today_override").value is None
    bad = client.post(f"{API}/admin/demo/today", json={"date": "not-a-date"}, headers=h)
    assert bad.status_code == 422


def test_fast_forward_unknown_transition(client, headers):
    res = client.post(
        f"{API}/admin/demo/fast-forward", json={"transition_id": "TR-9999"}, headers=headers(ADMIN)
    )
    assert res.status_code == 404


def _ok(res, expected=200):
    assert res.status_code == expected, res.text
    return res.json()


def _real_ocet_flow(client, headers) -> None:
    """OCET v2: Architect fills L6, OR focal submits, Planner then OLM approve (spec 7.5)."""
    ocet = _ok(client.get(f"{API}/transitions/TR-0001/ocet", headers=headers("U01")))
    version_id = ocet["version"]["id"]
    keys = [
        "id",
        "line_key",
        "category",
        "description",
        "vendor",
        "pricing_basis",
        "base_amount",
        "growth_pct",
        "year_overrides",
        "override_reason",
        "input_owner_role",
        "input_status",
    ]
    lines = [{k: line[k] for k in keys} for line in ocet["lines"]]
    for line in lines:
        if line["line_key"] == "L6":
            line["base_amount"] = 10000
            line["input_status"] = "Provided"
    _ok(
        client.put(
            f"{API}/ocet/versions/{version_id}/lines", json={"lines": lines}, headers=headers("U11")
        )
    )
    submitted = _ok(client.post(f"{API}/ocet/versions/{version_id}/submit", headers=headers("U01")))
    request_id = submitted["approval"]["request_id"]
    _ok(
        client.post(
            f"{API}/approvals/{request_id}/steps/1/approve", json={}, headers=headers("U13")
        )
    )
    _ok(
        client.post(
            f"{API}/approvals/{request_id}/steps/2/approve", json={}, headers=headers("U12")
        )
    )
    assert (
        _ok(client.get(f"{API}/transitions/TR-0001/ocet", headers=headers("U01")))["version"][
            "status"
        ]
        == "Approved"
    )


def _real_support_model_flow(client, headers) -> None:
    """Support model: inputs, generate, send for review, Architect then OLM approve."""
    _ok(
        client.post(
            f"{API}/transitions/TR-0001/support-model/inputs",
            data={"confluence_url": "https://confluence.example.com/wiki/voc-landscape"},
            files={"files": ("call.txt", b"System A talks to system B.", "text/plain")},
            headers=headers("U01"),
        )
    )
    _ok(client.post(f"{API}/transitions/TR-0001/support-model/generate", headers=headers("U01")))
    model = _ok(client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U01")))
    _ok(client.post(f"{API}/support-models/{model['id']}/send-for-review", headers=headers("U01")))
    model = _ok(client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U01")))
    request_id = model["approval"]["request_id"]
    _ok(
        client.post(
            f"{API}/approvals/{request_id}/steps/1/approve", json={}, headers=headers("U11")
        )
    )
    _ok(
        client.post(
            f"{API}/approvals/{request_id}/steps/2/approve", json={}, headers=headers("U12")
        )
    )
    model = _ok(client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U01")))
    assert model["status"] == "Agreed"


def test_fast_forward_and_ac07_ready(client, headers, fresh_seed, db):
    # Before: the flagship is not ready for AtD
    pre = client.get(
        f"{API}/transitions/TR-0001/readiness", params={"gate": "SG4_ATD"}, headers=headers("U01")
    ).json()
    assert pre["verdict"] != "Ready"

    # OCET and support model are completed through their REAL flows (linked items are never
    # completed by hand or by fast-forward, spec 7.5)
    _real_ocet_flow(client, headers)
    _real_support_model_flow(client, headers)
    db.expire_all()
    linked = list(
        db.scalars(
            select(TransitionItem).where(
                TransitionItem.transition_id == "TR-0001",
                TransitionItem.playbook_item_id.in_(["FW-008", "S45-006", "FW-031", "FW-035"]),
            )
        )
    )
    assert len(linked) == 4 and all(i.status == "Complete" for i in linked)
    assert all(i.last_updated_source == "Workflow rule" for i in linked), [
        (i.playbook_item_id, i.last_updated_source) for i in linked
    ]

    # EX-01: approve both steps (IRM, then the mocked CISO/BISO step)
    for step in (1, 2):
        res = client.post(
            f"{API}/approvals/APR-0001/steps/{step}/approve", json={}, headers=headers("U14")
        )
        assert res.status_code == 200, res.text
    # CON-001: close
    res = client.patch(
        f"{API}/conditions/CON-001",
        json={"status": "Closed", "close_note": "Resolved for demo"},
        headers=headers("U01"),
    )
    assert res.status_code == 200, res.text

    ff = client.post(f"{API}/admin/demo/fast-forward", json={}, headers=headers(ADMIN))
    assert ff.status_code == 200, ff.text
    out = ff.json()
    assert out["transition_id"] == "TR-0001"
    assert out["items_completed"] > 0 and out["evals_passing"] > 0
    assert out["readiness"] is not None
    # storyline step 9: rule R4 has drafted "Ready for AtD" (a draft only, nothing sent)
    assert out["r4_drafts"] == 1
    from app.models import OrionDraft

    db.expire_all()
    r4 = db.scalars(select(OrionDraft).where(OrionDraft.transition_id == "TR-0001")).all()
    ready = [d for d in r4 if "Ready for AtD" in d.subject]
    assert [d.status for d in ready] == ["Draft"]
    # the draft IS the approval request: To = the OLM, Cc = the OR focal (Asha sends it)
    from app.models import User

    assert ready[0].to == [db.get(User, "U12").email] and ready[0].cc == [db.get(User, "U01").email]

    db.expire_all()
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == "TR-0001", AuditEvent.note.like("Demo fast-forward%")
        )
    ).all()
    assert events and all(e.actor_type == "System" for e in events)
    results = db.scalars(select(EvalResult).where(EvalResult.transition_id == "TR-0001")).all()
    assert results and all(r.passed is True for r in results)

    ready = client.get(
        f"{API}/transitions/TR-0001/readiness", params={"gate": "SG4_ATD"}, headers=headers("U01")
    ).json()
    assert ready["verdict"] == "Ready", ready.get("blocking_items") or ready
    assert not ready.get("blocking_items")


def test_fast_forward_skips_linked_and_exception_items(client, headers, fresh_seed, db):
    from app.models import ExceptionRecord

    excepted = {
        e.transition_item_id
        for e in db.scalars(
            select(ExceptionRecord).where(ExceptionRecord.transition_id == "TR-0001")
        )
        if e.transition_item_id
    }
    assert excepted
    ff = client.post(f"{API}/admin/demo/fast-forward", json={}, headers=headers(ADMIN)).json()
    assert ff["skipped_linked"] > 0 and ff["skipped_exception"] > 0
    db.expire_all()
    for item_id in excepted:
        item = db.get(TransitionItem, item_id)
        assert item.status not in ("Complete", "Compliant")
    touched = {
        e.entity_id
        for e in db.scalars(
            select(AuditEvent).where(
                AuditEvent.entity == "TransitionItem", AuditEvent.note.like("Demo fast-forward%")
            )
        )
    }
    linked_ids = {
        str(i.id)
        for i in db.scalars(
            select(TransitionItem).where(
                TransitionItem.transition_id == "TR-0001",
                TransitionItem.linked_module.in_(["OCET", "SUPPORT_MODEL"]),
            )
        )
    }
    assert touched and not (touched & linked_ids)
    assert not (touched & {str(i) for i in excepted})
    # idempotent: a second run completes nothing more
    again = client.post(f"{API}/admin/demo/fast-forward", json={}, headers=headers(ADMIN)).json()
    assert again["items_completed"] == 0


def test_reset_clears_stale_storage(client, headers, fresh_seed):
    from app.config import get_settings

    stale = get_settings().storage_dir / "TR-0014"
    stale.mkdir(parents=True, exist_ok=True)
    (stale / "a.txt").write_text("old")
    assert client.post(f"{API}/admin/demo/reset", headers=headers("U16")).status_code == 200
    assert not stale.exists()
