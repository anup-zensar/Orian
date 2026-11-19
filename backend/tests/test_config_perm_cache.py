"""CR-01 design 1.6: has_perm / permissions_for / denied_reasons_for / DENIAL_REASONS read a cache built
from role_permissions + permission_texts (fallback: the MATRIX defaults); access.py maps the five
built-in roles to their transition slots."""

from __future__ import annotations

import pytest

from app import access, permissions
from app.domain import cfg
from app.models import PermissionText, Role, RolePermission, Transition, User
from app.permissions import DEFAULT_DENIAL_REASONS, DENIAL_REASONS, MATRIX, Perm, has_perm


def _edit(db, fn) -> None:
    fn()
    db.commit()
    cfg.invalidate()


def test_seeded_cache_equals_the_matrix(db) -> None:
    cfg.invalidate()
    for perm in Perm:
        for role in permissions.Role:
            assert has_perm(role.value, perm) == (role in MATRIX[perm])
    assert permissions.current_cache().from_db is True
    assert permissions.permissions_for("ADMIN") == sorted(
        p.value for p in Perm if permissions.Role.ADMIN in MATRIX[p]
    )


def test_matrix_edit_is_effective_after_invalidate(fresh_seed, db) -> None:
    assert not has_perm("PM", Perm.CONFIRM_SCOPE)
    _edit(db, lambda: db.add(RolePermission(perm="confirm_scope", role_code="PM")))
    assert has_perm("PM", Perm.CONFIRM_SCOPE)
    assert "confirm_scope" in permissions.permissions_for("PM")
    assert "confirm_scope" not in permissions.denied_reasons_for("PM")
    _edit(
        db,
        lambda: db.query(RolePermission).filter_by(perm="confirm_scope", role_code="PM").delete(),
    )
    assert not has_perm("PM", Perm.CONFIRM_SCOPE)


def test_edited_denial_text_is_what_callers_see(fresh_seed, db) -> None:
    assert DENIAL_REASONS[Perm.CONFIRM_TIER] == DEFAULT_DENIAL_REASONS[Perm.CONFIRM_TIER]
    _edit(
        db,
        lambda: setattr(
            db.get(PermissionText, "confirm_tier"), "denial_reason", "Ask the IRM please"
        ),
    )
    assert DENIAL_REASONS[Perm.CONFIRM_TIER] == "Ask the IRM please"
    assert permissions.denied_reasons_for("PM")["confirm_tier"] == "Ask the IRM please"
    assert len(DENIAL_REASONS) == len(Perm) and set(DENIAL_REASONS) == set(Perm)


def test_denial_text_reaches_the_403_and_the_access_map(client, headers, fresh_seed, db) -> None:
    _edit(
        db, lambda: setattr(db.get(PermissionText, "admin"), "denial_reason", "Admins only, sorry")
    )
    r = client.get("/api/v1/admin/roles", headers=headers("U01"))
    assert r.status_code == 403 and r.json()["detail"] == "Admins only, sorry"
    me = client.get("/api/v1/me", headers=headers("U01")).json()
    assert me["denied_reasons"]["admin"] == "Admins only, sorry"


def test_inactive_and_unknown_roles_hold_no_permission(fresh_seed, db) -> None:
    assert has_perm("PLANNER", Perm.VIEW)
    _edit(db, lambda: setattr(db.get(Role, "PLANNER"), "active", False))
    assert not has_perm("PLANNER", Perm.VIEW)
    assert not has_perm("NO_SUCH_ROLE", Perm.VIEW)
    assert permissions.permissions_for("PLANNER") == []


def test_empty_tables_fall_back_to_the_matrix(fresh_seed, db) -> None:
    db.query(RolePermission).delete()
    db.query(PermissionText).delete()
    db.commit()
    cfg.invalidate()
    assert has_perm("ADMIN", Perm.ADMIN) and not has_perm("PM", Perm.ADMIN)
    assert permissions.current_cache().from_db is False
    assert DENIAL_REASONS[Perm.ADMIN] == DEFAULT_DENIAL_REASONS[Perm.ADMIN]


def test_reset_and_seed_restores_the_matrix(db) -> None:
    from app.seed.loader import reset_and_seed

    db.add(RolePermission(perm="admin", role_code="PM"))
    db.commit()
    cfg.invalidate()
    assert has_perm("PM", Perm.ADMIN)
    reset_and_seed()
    assert not has_perm("PM", Perm.ADMIN)


@pytest.mark.parametrize(
    ("perm", "role", "expected"),
    [
        (Perm.VIEW_ALL_APPROVALS, "OR_FOCAL", True),
        (Perm.VIEW_ALL_APPROVALS, "ADMIN", True),
        (Perm.VIEW_ALL_APPROVALS, "IRM", False),
        (Perm.SEE_MOCK_APPROVALS, "IRM", True),
        (Perm.SEE_MOCK_APPROVALS, "OR_FOCAL", False),
        (Perm.SEE_ALL_TRANSITIONS, "LEADERSHIP", True),
        (Perm.SEE_ALL_TRANSITIONS, "ADMIN", False),
    ],
)
def test_new_perm_codes(db, perm, role, expected) -> None:
    cfg.invalidate()
    assert has_perm(role, perm) is expected


def test_orion_is_never_a_role(db) -> None:
    cfg.invalidate()
    assert not has_perm("ORION", Perm.VIEW) and not has_perm("Orion agent", Perm.VIEW)
    assert permissions.current_cache().active_roles == {r.value for r in permissions.Role}


# --- access.py: the five built-in slots ---------------------------------------------------------------------


def test_builtin_slots_and_labels_unchanged(db) -> None:
    cfg.invalidate()
    focal = db.get(User, "U01")
    t1 = db.get(Transition, "TR-0001")
    assert access.transition_denial(db, focal, t1, Perm.CONFIRM_SCOPE) is None
    pm = db.get(User, "U10")
    reason = access.transition_denial(db, pm, t1, Perm.CONFIRM_SCOPE)
    assert reason == "Only the OR focal can confirm scope and applicability"
    # built-in label wording comes from cfg with today's text as default
    other_focal = db.get(User, "U02")
    reason = access.transition_denial(db, other_focal, t1, Perm.UPDATE_BT_STATUS)
    assert reason is not None and reason.startswith("Only the people assigned to TR-0001")
    assert "project manager" in reason


def test_admin_has_no_slot_and_no_workflow_override(fresh_seed, db) -> None:
    admin = db.get(User, "U16")
    t1 = db.get(Transition, "TR-0001")
    assert access.assigned_user_id(t1, "ADMIN") is None
    assert [r.code for r in cfg.slot_roles(db)] == ["OR_FOCAL", "PM", "ARCHITECT", "OLM", "IRM"]
    assert not access.is_assigned(admin, t1)
    assert access.transition_denial(db, admin, t1, Perm.CONFIRM_SCOPE) is not None
