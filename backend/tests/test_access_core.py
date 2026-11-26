"""Unit tests of the per-transition access helper (app/access.py, review finding BE#1).

Transient (unsaved) Transition objects keep the cases independent of the seeded assignments; the
seeded users provide the names used in the messages.
"""

from __future__ import annotations

import pytest

from app.access import (
    ensure_admin,
    ensure_admin_or_assigned,
    ensure_transition_role,
    is_assigned,
    transition_denial,
    transition_for,
)
from app.errors import Conflict, Forbidden, NotFound
from app.models import Transition, User
from app.permissions import DENIAL_REASONS, Perm


def _transition(**overrides: object) -> Transition:
    values: dict[str, object] = {
        "id": "TR-9001",
        "or_focal_user_id": "U01",
        "pm_user_id": "U10",
        "architect_user_id": "U11",
        "olm_user_id": "U12",
        "irm_user_id": "U14",
        "status": "Active",
    }
    values.update(overrides)
    return Transition(**values)


def _user(db, user_id: str) -> User:
    user = db.get(User, user_id)
    assert user is not None
    return user


def test_assigned_or_focal_passes(db):
    t = _transition()
    assert transition_denial(db, _user(db, "U01"), t, Perm.RECORD_GATE_DECISION) is None
    assert is_assigned(_user(db, "U01"), t)


def test_other_or_focal_is_denied_with_the_owner_named(db):
    reason = transition_denial(db, _user(db, "U02"), _transition(), Perm.RECORD_GATE_DECISION)
    assert reason == "Only Asha Menon, the OR focal of TR-9001, can record gate decisions"


def test_role_without_the_permission_gets_the_matrix_reason(db):
    t = _transition()
    pm = _user(db, "U10")
    assert (
        transition_denial(db, pm, t, Perm.RECORD_GATE_DECISION)
        == DENIAL_REASONS[Perm.RECORD_GATE_DECISION]
    )


def test_admin_has_no_workflow_override(db):
    admin = _user(db, "U16")
    reason = transition_denial(db, admin, _transition(), Perm.RECORD_GATE_DECISION)
    assert reason == DENIAL_REASONS[Perm.RECORD_GATE_DECISION]


def test_multi_role_message_lists_the_assigned_people(db):
    reason = transition_denial(db, _user(db, "U02"), _transition(), Perm.UPDATE_BT_STATUS)
    assert reason is not None
    assert reason.startswith("Only the people assigned to TR-9001 (Asha Menon (OR focal)")
    assert "(project manager)" in reason and "(OLM)" in reason
    assert "(architect)" not in reason  # CR-03: the Architect holds update_t_status instead
    assert reason.endswith("can update Business/Technical items")
    # every assigned qualifying role passes
    for uid in ("U01", "U10", "U12"):
        assert transition_denial(db, _user(db, uid), _transition(), Perm.UPDATE_BT_STATUS) is None


def test_also_allowed_lets_an_owner_with_the_role_through(db):
    t = _transition(pm_user_id=None)
    pm = _user(db, "U10")
    assert transition_denial(db, pm, t, Perm.UPDATE_BT_STATUS) is not None
    assert transition_denial(db, pm, t, Perm.UPDATE_BT_STATUS, also_allowed=["U10"]) is None
    # ...but never a user whose role lacks the permission
    planner = _user(db, "U13")
    assert (
        transition_denial(db, planner, t, Perm.UPDATE_BT_STATUS, also_allowed=["U13"])
        == DENIAL_REASONS[Perm.UPDATE_BT_STATUS]
    )


def test_roles_narrowing_names_the_qualifying_person(db):
    reason = transition_denial(
        db, _user(db, "U01"), _transition(), Perm.MANAGE_CONDITIONS, roles=["IRM"]
    )
    assert reason == "Only Fatima Khan, the IRM of TR-9001, can manage conditions"
    assert (
        transition_denial(
            db, _user(db, "U14"), _transition(), Perm.MANAGE_CONDITIONS, roles=["IRM"]
        )
        is None
    )


def test_empty_slot_asks_for_an_assignment(db):
    reason = transition_denial(
        db, _user(db, "U14"), _transition(irm_user_id=None), Perm.CONFIRM_TIER
    )
    assert reason == "TR-9001 has no IRM assigned - ask an Admin to assign one"


def test_permission_is_checked_before_closed(db):
    closed = _transition(status="Closed")
    with pytest.raises(Forbidden):
        ensure_transition_role(db, _user(db, "U02"), closed, Perm.RECORD_GATE_DECISION)
    with pytest.raises(Conflict):
        ensure_transition_role(db, _user(db, "U01"), closed, Perm.RECORD_GATE_DECISION)
    ensure_transition_role(
        db, _user(db, "U01"), closed, Perm.RECORD_GATE_DECISION, allow_closed=True
    )


def test_forbidden_body_carries_the_reason(db):
    with pytest.raises(Forbidden) as info:
        ensure_transition_role(db, _user(db, "U02"), _transition(), Perm.SEND_DRAFTS)
    assert info.value.reasons == ["Only Asha Menon, the OR focal of TR-9001, can send Orion drafts"]


def test_admin_helpers(db):
    admin, focal, other = _user(db, "U16"), _user(db, "U01"), _user(db, "U02")
    ensure_admin(admin, "change configuration")
    with pytest.raises(Forbidden) as info:
        ensure_admin(focal, "change the OR focal or IRM")
    assert info.value.detail == "Only an Admin can change the OR focal or IRM"
    t = _transition()
    ensure_admin_or_assigned(db, admin, t, Perm.EDIT_TRANSITION)
    ensure_admin_or_assigned(db, focal, t, Perm.EDIT_TRANSITION)
    with pytest.raises(Forbidden):
        ensure_admin_or_assigned(db, other, t, Perm.EDIT_TRANSITION)
    with pytest.raises(Conflict):
        ensure_admin_or_assigned(db, admin, _transition(status="Closed"), Perm.EDIT_TRANSITION)


def test_transition_for(db):
    assert transition_for(db, "TR-0001").id == "TR-0001"
    with pytest.raises(NotFound):
        transition_for(db, "TR-9999")


def test_access_map_covers_transition_perms(db):
    from app.access import TRANSITION_PERMS, access_map

    focal_map = access_map(db, _user(db, "U01"), _transition())
    assert set(focal_map) == {p.value for p in TRANSITION_PERMS}
    assert focal_map["record_gate_decision"] is None
    assert focal_map["confirm_tier"] == DENIAL_REASONS[Perm.CONFIRM_TIER]
    other = access_map(db, _user(db, "U02"), _transition())
    assert other["record_gate_decision"].startswith("Only Asha Menon")
    admin = access_map(db, _user(db, "U16"), _transition())
    assert admin["edit_transition"] is None and admin["record_gate_decision"] is not None
    closed = access_map(db, _user(db, "U01"), _transition(status="Closed"))
    assert closed["record_gate_decision"] == (
        "TR-9001 is closed - records can no longer be added or changed"
    )


def test_transition_detail_carries_access(client, headers):
    body = client.get("/api/v1/transitions/TR-0001", headers=headers("U01")).json()
    assert body["access"]["record_gate_decision"] is None
    body = client.get("/api/v1/transitions/TR-0001", headers=headers("U02")).json()
    assert body["access"]["record_gate_decision"].startswith("Only Asha Menon")
