"""Per-transition access for records: actions, conditions, risks, defects, exceptions (BE#1, BE#3, BE#7).

TR-0001 belongs to OR focal U01 (Asha Menon); U02 is another OR focal. U14 is the IRM of every
seeded transition. Compliance items on TR-0001 include S45-014 and S45-035.
"""

from __future__ import annotations

from app.models import Transition, User

API = "/api/v1"
T = "TR-0001"


def _make_user(db, user_id: str, role: str) -> None:
    db.add(
        User(id=user_id, name=f"Test {role} {user_id}", email=f"{user_id}@test.example", role=role)
    )
    db.commit()


def test_other_or_focal_is_refused_everywhere_on_records(client, headers, fresh_seed):
    h = headers("U02")
    cases = [
        (
            "post",
            f"/transitions/{T}/actions",
            {"title": "x", "owner_user_id": "U11", "due_date": "2026-12-01"},
        ),
        ("patch", "/actions/ACT-001", {"priority": "Low"}),
        (
            "post",
            f"/transitions/{T}/conditions",
            {"item_id": "S3-019", "owner_user_id": "U01", "due_gate": "SG6_ATO", "text": "x"},
        ),
        ("patch", "/conditions/CON-001", {"text": "changed"}),
        ("post", f"/transitions/{T}/risks", {"title": "r", "rating": "Low"}),
        ("post", f"/transitions/{T}/defects", {"title": "d", "priority": "P3"}),
        ("post", f"/transitions/{T}/defects/confirm-none", {"confirmed": True}),
        ("post", f"/transitions/{T}/exceptions", {"item_id": "S45-035", "text": "x"}),
    ]
    for method, url, body in cases:
        res = getattr(client, method)(f"{API}{url}", json=body, headers=h)
        assert res.status_code == 403, (url, res.text)
        assert "Asha Menon" in res.json()["detail"], (url, res.json())


def test_assigned_focal_passes_the_same_calls(client, headers, fresh_seed):
    h = headers("U01")
    res = client.post(
        f"{API}/transitions/{T}/actions",
        json={"title": "x", "owner_user_id": "U11", "due_date": "2026-12-01"},
        headers=h,
    )
    assert res.status_code == 201, res.text
    assert (
        client.post(
            f"{API}/transitions/{T}/risks", json={"title": "r", "rating": "Low"}, headers=h
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{API}/transitions/{T}/defects", json={"title": "d", "priority": "P3"}, headers=h
        ).status_code
        == 201
    )


def test_action_owner_may_edit_only_when_the_role_qualifies(client, headers, db, fresh_seed):
    _make_user(db, "U90", "PM")  # PM holds MANAGE_ACTIONS but is not assigned to TR-0001
    _make_user(db, "U91", "PM")
    created = client.post(
        f"{API}/transitions/{T}/actions",
        json={"title": "Owned elsewhere", "owner_user_id": "U90", "due_date": "2026-12-01"},
        headers=headers("U01"),
    ).json()
    url = f"{API}/actions/{created['id']}"
    assert (
        client.patch(url, json={"status": "In progress"}, headers=headers("U90")).status_code == 200
    )
    denied = client.patch(url, json={"status": "Done"}, headers=headers("U91"))
    assert denied.status_code == 403


def test_compliance_conditions_belong_to_the_assigned_irm(client, headers, fresh_seed):
    body = {
        "item_id": "S45-035",
        "owner_user_id": "U11",
        "due_gate": "SG6_ATO",
        "text": "Fix logging",
    }
    focal = client.post(f"{API}/transitions/{T}/conditions", json=body, headers=headers("U01"))
    assert focal.status_code == 403
    assert "Fatima Khan" in focal.json()["detail"] and "IRM" in focal.json()["detail"]
    assert (
        client.post(
            f"{API}/transitions/{T}/conditions", json=body, headers=headers("U14")
        ).status_code
        == 201
    )


def test_decision_gate_due_dates_move_only_with_the_irm(client, headers, fresh_seed):
    # CON-001 (S3-019, Technical) is due at AtD: the focal can close it but not push its due gate.
    push = client.patch(
        f"{API}/conditions/CON-001", json={"due_gate": "SG6_ATO"}, headers=headers("U01")
    )
    assert push.status_code == 403 and "Fatima Khan" in push.json()["detail"]
    ok = client.patch(
        f"{API}/conditions/CON-001", json={"due_gate": "SG6_ATO"}, headers=headers("U14")
    )
    assert ok.status_code == 200 and ok.json()["due_gate"] == "SG6_ATO"


def test_focal_can_close_a_technical_condition(client, headers, fresh_seed):
    res = client.patch(
        f"{API}/conditions/CON-001",
        json={"status": "Closed", "close_note": "Stress test passed"},
        headers=headers("U01"),
    )
    assert res.status_code == 200 and res.json()["status"] == "Closed"


def test_closed_transition_freezes_records(client, headers, db, fresh_seed):
    transition = db.get(Transition, "TR-0017")
    transition.status = "Closed"
    db.commit()
    tid = "TR-0017"
    h = headers(transition.or_focal_user_id)
    calls = [
        (
            "post",
            f"/transitions/{tid}/actions",
            {"title": "x", "owner_user_id": "U11", "due_date": "2026-12-01"},
        ),
        ("post", f"/transitions/{tid}/risks", {"title": "r", "rating": "Low"}),
        ("post", f"/transitions/{tid}/defects", {"title": "d", "priority": "P3"}),
        ("post", f"/transitions/{tid}/defects/confirm-none", {"confirmed": False}),
    ]
    for method, url, body in calls:
        res = getattr(client, method)(f"{API}{url}", json=body, headers=h)
        assert res.status_code == 409, (url, res.text)
        assert (
            "closed" in res.json()["detail"].lower()
            or "closed" in str(res.json()["reasons"]).lower()
        )
    assert client.get(f"{API}/transitions/{tid}/risks", headers=h).status_code == 200


def test_huge_ids_and_long_text_are_422_not_500(client, headers):
    h = headers("U01")
    big = "9" * 20
    assert client.get(f"{API}/orion/drafts/{big}", headers=h).status_code == 422
    assert client.post(f"{API}/notifications/{big}/read", headers=h).status_code == 422
    long_text = "x" * 3_000_000
    res = client.post(
        f"{API}/transitions/{T}/risks",
        json={"title": "r", "rating": "Low", "decision": long_text},
        headers=h,
    )
    assert res.status_code == 422
