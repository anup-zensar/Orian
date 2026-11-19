"""CR-01 admin "People & permissions" grid: PUT /admin/permissions is effective immediately (permission
cache), keeps its guardrails, and an edited denial text is what 403s and the access map show."""

from __future__ import annotations

from app import permissions
from app.domain import cfg
from app.models import AuditEvent
from app.permissions import Perm, has_perm
from app.seed.loader import reset_and_seed

API = "/api/v1"
ADMIN = "U16"


def _grid(client, headers) -> dict:
    return client.get(f"{API}/admin/permissions", headers=headers(ADMIN)).json()


def _matrix(grid: dict) -> dict[str, list[str]]:
    return {row["perm"]: list(row["roles"]) for row in grid["permissions"]}


def _put(client, headers, matrix: dict, texts: dict | None = None, user: str = ADMIN):
    body = {"matrix": matrix, "texts": texts or {}}
    return client.put(f"{API}/admin/permissions", json=body, headers=headers(user))


def test_saving_the_unchanged_grid_changes_nothing(client, headers, fresh_seed) -> None:
    grid = _grid(client, headers)
    r = _put(client, headers, _matrix(grid))
    assert r.status_code == 200, r.text
    assert _matrix(r.json()) == _matrix(grid)
    rows = {p["perm"]: p for p in r.json()["permissions"]}
    assert (
        rows["confirm_tier"]["denial_reason"]
        == permissions.DEFAULT_DENIAL_REASONS[Perm.CONFIRM_TIER]
    )
    assert not any(p["is_custom"] for p in rows.values())


def test_grant_and_revoke_are_effective_immediately(client, headers, fresh_seed) -> None:
    matrix = _matrix(_grid(client, headers))
    assert (
        "send_drafts" not in client.get(f"{API}/me", headers=headers("U10")).json()["permissions"]
    )
    matrix["send_drafts"] = ["PM"]  # the PM may send, the OR focal no longer
    r = _put(client, headers, matrix)
    assert r.status_code == 200
    assert has_perm("PM", Perm.SEND_DRAFTS) and not has_perm("OR_FOCAL", Perm.SEND_DRAFTS)
    assert "send_drafts" in client.get(f"{API}/me", headers=headers("U10")).json()["permissions"]
    focal = client.get(f"{API}/me", headers=headers("U01")).json()
    assert "send_drafts" not in focal["permissions"]
    # the text was regenerated from the role names, so it never names the role that lost the right
    reason = focal["denied_reasons"]["send_drafts"]
    assert "project manager" in reason and "OR focal" not in reason


def test_edited_denial_text_is_used_by_403_and_the_access_map(client, headers, fresh_seed) -> None:
    matrix = _matrix(_grid(client, headers))
    texts = {
        "admin": {"denial_reason": "Ask the Playbook team to change this"},
        "confirm_scope": {"denial_reason": "Scope is confirmed by the OR focal only"},
    }
    r = _put(client, headers, matrix, texts)
    assert r.status_code == 200
    rows = {p["perm"]: p for p in r.json()["permissions"]}
    assert (
        rows["admin"]["is_custom"]
        and rows["admin"]["denial_reason"] == texts["admin"]["denial_reason"]
    )
    denied = client.get(f"{API}/admin/roles", headers=headers("U01"))
    assert denied.status_code == 403 and denied.json()["detail"] == texts["admin"]["denial_reason"]
    detail = client.get(f"{API}/transitions/TR-0001", headers=headers("U10")).json()  # the PM
    assert detail["access"]["confirm_scope"] == texts["confirm_scope"]["denial_reason"]
    me = client.get(f"{API}/me", headers=headers("U10")).json()
    assert me["denied_reasons"]["confirm_scope"] == texts["confirm_scope"]["denial_reason"]
    # sending the generated text back switches the custom flag off again
    generated = rows["confirm_scope"]["default_denial_reason"]
    back = _put(client, headers, matrix, {"confirm_scope": {"denial_reason": generated}})
    assert not next(p for p in back.json()["permissions"] if p["perm"] == "confirm_scope")[
        "is_custom"
    ]


def test_wording_of_a_permission_can_change(client, headers, fresh_seed) -> None:
    matrix = _matrix(_grid(client, headers))
    texts = {"edit_ocet": {"label": "Change the cost estimate", "description": "Edit OCET lines"}}
    rows = {p["perm"]: p for p in _put(client, headers, matrix, texts).json()["permissions"]}
    assert rows["edit_ocet"]["label"] == "Change the cost estimate"
    assert rows["edit_ocet"]["description"] == "Edit OCET lines"


def test_guardrails_over_the_api(client, headers, fresh_seed) -> None:
    matrix = _matrix(_grid(client, headers))

    def refused(change, texts=None) -> str:
        m = {k: list(v) for k, v in matrix.items()}
        change(m)
        r = _put(client, headers, m, texts)
        assert r.status_code == 422, r.text
        return " | ".join(r.json()["reasons"])

    assert "Admin role must keep" in refused(lambda m: m.update(admin=["PM"]))
    assert "(view)" in refused(lambda m: m.update(view=[r for r in m["view"] if r != "LEADERSHIP"]))
    assert "unknown role 'WIZARD'" in refused(lambda m: m["edit_ocet"].append("WIZARD"))
    assert "Unknown permission 'fly'" in refused(lambda m: m.update(fly=["PM"]))
    assert "'send_drafts' is missing" in refused(lambda m: m.pop("send_drafts"))
    assert "reserved word" in refused(lambda m: None, {"view": {"label": "Orion access"}})
    assert "Unknown permission 'nope'" in refused(lambda m: None, {"nope": {"label": "x"}})
    # nothing changed
    assert _matrix(_grid(client, headers)) == matrix


def test_orion_never_appears_as_a_role_or_permission_holder(client, headers) -> None:
    grid = _grid(client, headers)
    assert "ORION" not in {r["code"] for r in grid["roles"]}
    assert all("orion" not in code.lower() for row in grid["permissions"] for code in row["roles"])
    assert any("Orion is never a role" in n for n in grid["notices"])


def test_transition_permissions_warn_that_admin_has_no_override(client, headers) -> None:
    rows = {p["perm"]: p for p in _grid(client, headers)["permissions"]}
    assert rows["confirm_scope"]["scope"] == "transition"
    assert "no workflow override" in rows["confirm_scope"]["lock_reasons"]["ADMIN"]
    assert rows["admin"]["scope"] == "global" and "ADMIN" in rows["admin"]["locked_roles"]
    assert set(rows["view"]["locked_roles"]) == {r["code"] for r in _grid(client, headers)["roles"]}


def test_edits_are_audited_with_before_and_after(client, headers, fresh_seed, db) -> None:
    matrix = _matrix(_grid(client, headers))
    matrix["send_drafts"] = ["PM", "OR_FOCAL"]
    assert _put(client, headers, matrix).status_code == 200
    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity == "config:permissions")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert event.actor_type == "Human" and event.actor_user_id == ADMIN
    assert event.before["matrix"] == {"send_drafts": ["OR_FOCAL"]}
    assert event.after["matrix"] == {"send_drafts": ["OR_FOCAL", "PM"]}


def test_only_the_admin_can_edit_the_grid(client, headers, fresh_seed) -> None:
    matrix = _matrix(_grid(client, headers))
    for user in ("U01", "U14", "U15"):
        assert _put(client, headers, matrix, user=user).status_code == 403


def test_reset_and_seed_restores_the_matrix(client, headers, fresh_seed, db) -> None:
    matrix = _matrix(_grid(client, headers))
    matrix["send_drafts"] = ["PM"]
    assert (
        _put(client, headers, matrix, {"send_drafts": {"denial_reason": "Custom"}}).status_code
        == 200
    )
    assert not has_perm("OR_FOCAL", Perm.SEND_DRAFTS)
    reset_and_seed()
    cfg.invalidate()
    assert has_perm("OR_FOCAL", Perm.SEND_DRAFTS) and not has_perm("PM", Perm.SEND_DRAFTS)
    assert (
        permissions.DENIAL_REASONS[Perm.SEND_DRAFTS]
        == permissions.DEFAULT_DENIAL_REASONS[Perm.SEND_DRAFTS]
    )
