"""CR-01 design 8: the seeded configuration reproduces today's behaviour exactly. Compares the
seeded rows (and the cfg read API) with the constants still in code."""

from __future__ import annotations

import pytest

from app import permissions
from app.domain import cfg, cfg_defaults
from app.models import (
    ApprovalChainConfig,
    Checklist,
    IntakeField,
    MessageTemplate,
    PermissionText,
    PlaybookItem,
    Role,
    RolePermission,
    User,
)
from app.permissions import MATRIX, Perm
from app.rules import constants as K
from app.rules import tiering as T


def test_option_lists_equal_the_code_constants(db) -> None:
    assert cfg.option_values(db, "severities") == list(K.SEVERITIES)
    assert cfg.option_values(db, "design_effectiveness") == list(K.DESIGN_EFFECTIVENESS)
    assert cfg.option_values(db, "actor_types") == list(K.ACTOR_TYPES)
    assert {o.value: o.meta["gate_code"] for o in cfg.options(db, "target_gate")} == {
        "SG0-SG2": "SG2",
        "SG3": "SG3",
        "AtD": "SG4_ATD",
        "AtO": "SG6_ATO",
        "Closure": "CLOSURE",
    }
    for lens, statuses in K.STATUSES_BY_LENS.items():
        assert cfg.option_values(db, f"item_statuses_{lens.lower()}") == list(statuses)
    assert cfg.option_values(db, "rag_words") == ["Red", "Amber", "Green", "Grey"]


def test_tier_facts_equal_the_tiering_rules_strings(db) -> None:
    for value, fact in T._AUDIENCE_FACT.items():
        assert cfg.option_meta(db, "audience", value)["fact"] == fact
    for value, fact in T._SENSITIVE_FACT.items():
        assert cfg.option_meta(db, "sensitive_data", value)["fact"] == fact


def test_critical_severity_is_exactly_one(db) -> None:
    assert cfg.critical_severity(db) == "Critical"
    assert [o.value for o in cfg.options(db, "severities") if o.meta["counts_as_critical"]] == [
        "Critical"
    ]


def test_owner_hints_equal_the_checklist_keyword_map(db) -> None:
    from app.rules import checklist as C

    assert dict(cfg.owner_hints(db)) == {kw.lower(): role for kw, role in C.DEFAULT_OWNER_HINTS}


def test_default_thresholds_equal_the_rule_numbers(db) -> None:
    t = cfg.thresholds(db)
    assert t == cfg_defaults.DEFAULT_THRESHOLDS
    assert (
        cfg_defaults.seed_config()["settings"]["cfg.thresholds"] == cfg_defaults.DEFAULT_THRESHOLDS
    )
    rag = cfg.rag_thresholds(db)
    assert (rag.red_critical_gaps, rag.red_lens_below, rag.red_near_days) == (2, 50, 7)
    assert (rag.amber_critical_gaps, rag.amber_lens_below) == (1, 70)
    assert t["calendar_horizon_days"] == 45 and t["leadership_decision_window_days"] == 30
    assert t["insights"] == {"low_readiness_below": 70, "within_days": 45}
    assert t["default_tier"] == 3


def test_approval_chain_settings_equal_the_constants(db) -> None:
    assert cfg.gate_chain(db) == {"SG4_ATD": "AtD", "SG6_ATO": "AtO"}
    assert cfg.mock_approver(db)["mock_role"] == "CISO_BISO"


def test_permission_matrix_is_copied_into_role_permissions(db) -> None:
    rows: dict[str, set[str]] = {}
    for r in db.query(RolePermission).all():
        rows.setdefault(r.perm, set()).add(r.role_code)
    assert rows == {p.value: {r.value for r in roles} for p, roles in MATRIX.items()}
    assert {t.perm: t.denial_reason for t in db.query(PermissionText).all()} == {
        p.value: text for p, text in permissions.DEFAULT_DENIAL_REASONS.items()
    }


def test_new_perm_codes_are_seeded_to_todays_roles(db) -> None:
    assert permissions.roles_with(Perm.VIEW_ALL_APPROVALS) == {"OR_FOCAL", "ADMIN"}
    assert permissions.roles_with(Perm.SEE_MOCK_APPROVALS) == {"IRM"}
    assert permissions.roles_with(Perm.SEE_ALL_TRANSITIONS) == {"LEADERSHIP"}


def test_roles_seeded_with_todays_labels_and_slots(db) -> None:
    roles = {r.code: r for r in db.query(Role).all()}
    assert set(roles) == {r.value for r in permissions.Role}
    assert roles["PM"].label == "Project manager" and roles["PM"].short_label == "PM"
    assert cfg.role_phrase_label(db, "PM") == "project manager"
    assert [r.code for r in cfg.slot_roles(db)] == ["OR_FOCAL", "PM", "ARCHITECT", "OLM", "IRM"]
    assert roles["ADMIN"].has_transition_slot is False and roles["ADMIN"].transition_column is None
    assert cfg.role_label(db, "CISO_BISO") == "CISO/BISO"  # the mock role is not a user role


def test_project_types_portfolios_checklists(db) -> None:
    assert [p.code for p in cfg.project_types(db)] == [
        "Normal",
        "Infrastructure",
        "Agentic AI",
        "Combined",
    ]
    assert cfg.project_type(db, "Combined").has_ai_profile
    assert cfg.portfolio(db, "Retail Site Systems").requires_sites
    assert not cfg.portfolio(db, "GCC").requires_sites
    defs = {c.code: c for c in cfg.checklist_defs(db)}
    assert set(defs) == {"FRAMEWORK", "AI_PLAYBOOK", "PORTFOLIO", "COMMON"}
    assert defs["AI_PLAYBOOK"].tier_filtered and defs["COMMON"].kind == "common"
    assert defs["PORTFOLIO"].kind == "portfolio_golden" and defs["FRAMEWORK"].kind == "library"
    assert db.query(Checklist).count() == 4


def test_library_applies_to_all_types_is_stored_as_empty(db) -> None:
    for item in (
        db.query(PlaybookItem).filter(PlaybookItem.source.in_(["COMMON", "PORTFOLIO"])).all()
    ):
        assert item.applies_to_project_types == []
    assert db.query(PlaybookItem).filter(PlaybookItem.default_owner_role.is_(None)).count() >= 0
    legacy_all = {"Agentic AI", "Normal", "Combined", "Infrastructure"}
    assert not [
        i
        for i in db.query(PlaybookItem).all()
        if i.applies_to_project_types and legacy_all <= set(i.applies_to_project_types)
    ]


def test_tier_questions_and_tiers_are_seeded(db) -> None:
    """BR-011 stays in rules/tiering.py; only the wording of questions and tiers is data."""
    assert [q.id for q in cfg.tier_questions(db)] == list(T.TIER_QUESTION_IDS)
    assert cfg.tier_numbers(db) == [1, 2, 3, 4]
    assert cfg.default_tier(db) == 3


def test_intake_fields_seeded_in_form_order(db) -> None:
    keys = [f.key for f in cfg.intake_fields(db)]
    assert keys == [
        "name",
        "project_type",
        "portfolio",
        "region",
        "market",
        "audience",
        "write_actions",
        "sensitive_data",
        "target_gate",
        "investment_type",
        "delivery_method",
        "description",
        "or_focal_user_id",
        "pm_user_id",
        "architect_user_id",
        "olm_user_id",
        "irm_user_id",
        "next_decision_date",
    ]
    assert {"audience", "write_actions", "sensitive_data"} <= set(
        cfg.required_fields_for(db, "Agentic AI")
    )
    assert "audience" not in cfg.required_fields_for(db, "Normal")
    assert {"name", "project_type", "portfolio", "region", "or_focal_user_id"} <= set(
        cfg.required_fields_for(db, "Normal")
    )
    assert db.query(IntakeField).filter(IntakeField.builtin.is_(False)).count() == 0


def test_approval_chains_flag_the_mock_step(db) -> None:
    exception = db.get(ApprovalChainConfig, "EXCEPTION")
    assert [s["is_mock"] for s in exception.steps] == [False, True]
    assert db.get(ApprovalChainConfig, "OCET").label == "OCET approval"


def test_users_are_active(db) -> None:
    assert db.query(User).filter(User.active.is_(False)).count() == 0


def test_every_template_key_is_seeded_last_from_the_code_defaults(db) -> None:
    rows = {t.key: t for t in db.query(MessageTemplate).all()}
    assert set(rows) == set(cfg_defaults.DEFAULT_TEMPLATES)
    for key, (name, subject, body, _src) in cfg_defaults.DEFAULT_TEMPLATES.items():
        assert (rows[key].name, rows[key].subject, rows[key].body) == (name, subject, body)
        assert {p["name"] for p in rows[key].placeholders} >= set(cfg_defaults.COMMON_PLACEHOLDERS)


@pytest.mark.parametrize("key", list(cfg_defaults.DEFAULT_TEMPLATES))
def test_template_placeholders_are_all_declared(key) -> None:
    name, subject, body, _src = cfg_defaults.DEFAULT_TEMPLATES[key]
    for used in cfg_defaults.placeholders_in(subject, body):
        assert used in cfg_defaults.PLACEHOLDERS, f"{key}: undeclared placeholder {used}"
