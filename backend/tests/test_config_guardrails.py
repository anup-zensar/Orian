"""CR-01 guardrails: one pure function per rule in ``app/domain/config_admin.py``. Each returns plain
reasons; the section writers turn a non-empty list into a 422 (tests of the API: test_config_*.py).
"""

from __future__ import annotations

import pytest

from app.domain import config_admin as g
from app.permissions import MATRIX, Perm

PERMS = [p.value for p in Perm]
ROLES = ["OR_FOCAL", "PM", "ARCHITECT", "OLM", "PLANNER", "IRM", "LEADERSHIP", "ADMIN"]


def _matrix() -> dict[str, set[str]]:
    return {p.value: {r.value for r in roles} for p, roles in MATRIX.items()}


# --- 1. permission grid ----------------------------------------------------------------------------


def test_the_seeded_grid_is_valid() -> None:
    assert g.check_permission_matrix(_matrix(), PERMS, ROLES, ["ADMIN", "PM"]) == []


def test_admin_role_must_keep_the_admin_permission() -> None:
    m = _matrix()
    m["admin"] = {"PM"}
    reasons = g.check_permission_matrix(m, PERMS, ROLES, ["ADMIN", "PM"])
    assert any("Admin role must keep" in r for r in reasons)


def test_one_active_user_must_still_hold_admin() -> None:
    m = _matrix()
    m["admin"] = {"ADMIN", "PM"}
    assert g.check_permission_matrix(m, PERMS, ROLES, ["ADMIN"]) == []
    # nobody active holds a role with the admin permission
    reasons = g.check_permission_matrix(m, PERMS, ROLES, ["OR_FOCAL", "IRM"])
    assert any("active user" in r for r in reasons)


def test_view_must_include_every_role() -> None:
    m = _matrix()
    m["view"] = m["view"] - {"LEADERSHIP"}
    reasons = g.check_permission_matrix(m, PERMS, ROLES, ["ADMIN"])
    assert any("LEADERSHIP" in r for r in reasons)


def test_unknown_codes_and_missing_rows_are_refused() -> None:
    m = _matrix()
    m["fly_to_moon"] = {"PM"}
    m["edit_ocet"] = {"WIZARD"}
    del m["send_drafts"]
    reasons = " | ".join(g.check_permission_matrix(m, PERMS, ROLES, ["ADMIN"]))
    assert "Unknown permission 'fly_to_moon'" in reasons
    assert "unknown role 'WIZARD'" in reasons
    assert "'send_drafts' is missing" in reasons


# --- 2. reserved words (BR-050) ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["Orion", "orion agent", "Mail Bot", "AI lead", "The-Agent", "bot"]
)
def test_reserved_words_are_refused(name: str) -> None:
    reasons = g.check_reserved_words("Name", name)
    assert len(reasons) == 1 and "Orion is not a person or a role" in reasons[0]


@pytest.mark.parametrize("name", ["Aiden Smith", "Botha", "Sarah Agentry", "Ali", "Maria Orionis"])
def test_ordinary_names_pass(name: str) -> None:
    assert g.check_reserved_words("Name", name) == []


# --- 4. deactivation and role change -------------------------------------------------------------------

USERS = [
    ("U01", "OR_FOCAL", True),
    ("U16", "ADMIN", True),
    ("U17", "ADMIN", True),
    ("U18", "ADMIN", False),
]
ADMINS = {"ADMIN"}


def test_cannot_deactivate_yourself() -> None:
    assert g.check_user_deactivation("U16", "U16", USERS, ADMINS) == [
        "You cannot deactivate yourself"
    ]


def test_cannot_deactivate_the_last_active_admin() -> None:
    users = [("U01", "OR_FOCAL", True), ("U16", "ADMIN", True), ("U18", "ADMIN", False)]
    reasons = g.check_user_deactivation("U16", "U01", users, ADMINS)
    assert reasons and "last active Admin" in reasons[0]
    assert g.check_user_deactivation("U17", "U16", USERS, ADMINS) == []  # U16 stays
    assert g.check_user_deactivation("U01", "U16", USERS, ADMINS) == []


def test_role_change_away_from_admin() -> None:
    assert (
        g.check_user_role_change("U17", "U16", "PM", USERS, ADMINS) == []
    )  # another admin remains
    assert "own role" in g.check_user_role_change("U16", "U16", "PM", USERS, ADMINS)[0]
    last = [("U16", "ADMIN", True), ("U01", "OR_FOCAL", True)]
    assert "last active Admin" in g.check_user_role_change("U16", "U01", "PM", last, ADMINS)[0]
    assert g.check_user_role_change("U01", "U16", "PM", USERS, ADMINS) == []
    assert g.check_user_role_change("U17", "U16", "ADMIN", USERS, ADMINS) == []


# --- 5. keep one active -------------------------------------------------------------------------------


def test_keep_one_active() -> None:
    assert g.check_keep_one_active("region", 1) == []
    assert g.check_keep_one_active("region", 0) == ["At least one region must stay active"]


# --- 6. exactly one critical severity ------------------------------------------------------------------


def test_exactly_one_active_severity_counts_as_critical() -> None:
    ok = [(True, {"counts_as_critical": True}), (True, {}), (True, {"counts_as_critical": False})]
    assert g.check_one_critical(ok) == []
    assert "found 0" in g.check_one_critical([(True, {}), (True, {})])[0]
    two = [(True, {"counts_as_critical": True}), (True, {"counts_as_critical": True})]
    assert "found 2" in g.check_one_critical(two)[0]
    # an inactive severity does not count
    assert g.check_one_critical([(False, {"counts_as_critical": True}), (True, {})])


# --- 3. structural lists -------------------------------------------------------------------------------


def test_structural_list_allows_labels_only() -> None:
    existing = {"Open": (True, {}), "Done": (True, {})}
    assert g.check_structural_items(True, existing, [("Open", True, {}), ("Done", True, {})]) == []
    added = g.check_structural_items(
        True, existing, [("Open", True, {}), ("Done", True, {}), ("New", True, {})]
    )
    assert "'New' cannot be added" in added[0]
    removed = g.check_structural_items(True, existing, [("Open", True, {})])
    assert "'Done' cannot be removed" in removed[0]
    off = g.check_structural_items(True, existing, [("Open", False, {}), ("Done", True, {})])
    assert "only be relabelled" in off[0]
    assert g.check_structural_items(False, existing, [("Brand new", True, {})]) == []


# --- item meta ------------------------------------------------------------------------------------------

META = [
    {"key": "rank", "type": "number", "label": "Rank"},
    {"key": "counts_as_critical", "type": "boolean", "label": "Critical"},
    {"key": "needs", "type": "select", "label": "Needs", "options": ["file", "url"]},
    {"key": "owner", "type": "role", "label": "Owner"},
    {"key": "gate", "type": "gate", "label": "Gate"},
    {"key": "ext", "type": "list", "label": "Extensions"},
    {"key": "color", "type": "token", "label": "Colour"},
]


def test_item_meta_types() -> None:
    good = {
        "rank": 2,
        "counts_as_critical": False,
        "needs": "file",
        "owner": "PM",
        "gate": "SG3",
        "ext": [".pdf"],
        "color": "red",
    }
    assert g.check_item_meta(META, good, ROLES) == []
    for bad in (
        {"rank": "high"},
        {"rank": True},
        {"counts_as_critical": "yes"},
        {"needs": "email"},
        {"owner": "WIZARD"},
        {"gate": "SG9"},
        {"ext": "pdf"},
        {"undeclared": 1},
    ):
        assert g.check_item_meta(META, bad, ROLES), bad


# --- 8. thresholds ----------------------------------------------------------------------------------------

RAG = {
    "red_critical_gaps": 2,
    "red_lens_below": 50,
    "red_near_days": 7,
    "amber_critical_gaps": 1,
    "amber_lens_below": 70,
}


def _doc(**rag: int) -> dict:
    return {"rag": {**RAG, **rag}, "default_tier": 3, "default_pricing_basis": "Fixed (contract)"}


def test_thresholds_amber_is_not_stricter_than_red() -> None:
    assert g.check_thresholds(_doc(), [1, 2, 3, 4], ["Fixed (contract)"]) == []
    assert g.check_thresholds(_doc(amber_critical_gaps=3), [1, 2, 3, 4], ["Fixed (contract)"])
    assert g.check_thresholds(_doc(amber_lens_below=40), [1, 2, 3, 4], ["Fixed (contract)"])


def test_thresholds_default_tier_and_pricing_basis_must_exist() -> None:
    assert "Default tier 3" in g.check_thresholds(_doc(), [1, 2], ["Fixed (contract)"])[0]
    assert "pricing basis" in g.check_thresholds(_doc(), [1, 2, 3], ["T&M"])[0]


# --- 9. custom fields ---------------------------------------------------------------------------------------


def test_custom_field_keys() -> None:
    assert g.check_custom_field_key("cf_cost_centre", {"name"}) == []
    assert g.check_custom_field_key("cost_centre", set())  # needs the cf_ prefix
    assert g.check_custom_field_key("cf_Cost", set())  # lowercase only
    assert g.check_custom_field_key("cf_1abc", set())  # a letter first
    assert "already exists" in g.check_custom_field_key("cf_cost", {"cf_cost"})[0]


def test_field_type_is_fixed_once_used() -> None:
    assert g.check_field_type_change("text", "text", 5) == []
    assert g.check_field_type_change("text", "number", 0) == []
    assert "3 transitions" in g.check_field_type_change("text", "number", 3)[0]


def test_slug_keys_are_unique_and_valid() -> None:
    assert g.slug_key("Cost centre", set()) == "cf_cost_centre"
    assert g.slug_key("Cost centre", {"cf_cost_centre"}) == "cf_cost_centre_2"
    assert g.slug_key("123 go", set()).startswith("cf_f_")
    assert g.slug_key("!!!", set()) == "cf_field"


# --- 7. templates and reminders ------------------------------------------------------------------------------


def test_template_placeholders_and_markup() -> None:
    allowed = {"greeting", "transition_name"}
    assert (
        g.check_template("chaser", "Hi {{transition_name}}", "<p>{{greeting}}</p>", allowed) == []
    )
    reasons = g.check_template("chaser", "{{secret}}", "<p>{{ other }}</p>", allowed)
    assert "{{secret}}" in reasons[0] and "{{other}}" in reasons[1]
    assert g.check_template("chaser", "x", "<script>alert(1)</script>", allowed)
    assert g.check_template("chaser", "x", '<a href="javascript:x()">y</a>', allowed)
    assert g.check_template("chaser", "x", '<p onclick="x()">y</p>', allowed)


def test_reminder_autonomy_can_only_be_lowered() -> None:
    assert g.check_autonomy_lowered("R1", True, False) == []
    assert g.check_autonomy_lowered("R1", True, True) == []
    assert g.check_autonomy_lowered("R1", False, False) == []
    assert "switched off" in g.check_autonomy_lowered("R4", False, True)[0]


# --- tiering shape, checklists ----------------------------------------------------------------------------------


def test_tier_numbers_and_question_ids_are_fixed() -> None:
    assert g.check_same_ids("Tier", [1, 2, 3, 4], [4, 3, 2, 1]) == []
    reasons = g.check_same_ids("Tier", [1, 2, 3, 4], [1, 2, 3, 5, 5])
    assert any("only once" in r for r in reasons)
    assert any("Tier 4 cannot be removed" in r for r in reasons)
    assert any("Tier 5 cannot be added" in r for r in reasons)


def test_checklist_in_use_cannot_be_deactivated() -> None:
    assert g.check_checklist_deactivation("AI_PLAYBOOK", []) == []
    assert "Agentic AI" in g.check_checklist_deactivation("AI_PLAYBOOK", ["Agentic AI"])[0]
