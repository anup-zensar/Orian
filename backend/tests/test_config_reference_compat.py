"""CR-01: GET /reference stays backwards compatible (every pre-CR key keeps its shape and, for the
seeded configuration, its VALUES - which are the ones in seed/reference.json)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parents[2] / "seed"
REF = json.loads((SEED / "reference.json").read_text(encoding="utf-8"))

# the key set of ReferenceOut before CR-01
PRE_CR_KEYS = {
    "gates",
    "gate_outcomes",
    "lenses",
    "item_statuses",
    "done_statuses",
    "na_statuses",
    "gap_statuses",
    "design_effectiveness_options",
    "project_types",
    "flavour_rule_note",
    "portfolios",
    "portfolio_details",
    "regions",
    "intake_options",
    "tiers",
    "tier_dimensions",
    "tier_questions",
    "rag_rule",
    "approval_chains",
    "risk_acceptance_routes",
    "risk_acceptance_then",
    "ocet",
    "roles",
    "checklist_counts",
    "enums",
    "app",
}
CR_KEYS = {
    "lists",
    "intake_fields",
    "checklists",
    "labels",
    "thresholds",
    "gate_labels",
    "approval_chain_labels",
}


@pytest.fixture(scope="module")
def ref(client):
    r = client.get("/api/v1/reference")
    assert r.status_code == 200, r.text
    return r.json()


def test_pre_cr_keys_are_all_still_there_and_new_keys_are_additive(ref) -> None:
    assert set(ref) >= PRE_CR_KEYS
    assert set(ref) == PRE_CR_KEYS | CR_KEYS


def test_reference_is_public(client) -> None:
    assert client.get("/api/v1/reference").status_code == 200  # no X-Demo-User


def test_reference_never_contains_users_or_templates(ref) -> None:
    text = json.dumps(ref).lower()
    assert "message_templates" not in ref and "users" not in ref
    assert "asha.menon@example.com" not in text
    assert "{{" not in text  # no template text


def test_gates_keep_their_shape_and_values(ref) -> None:
    for got, want in zip(ref["gates"], REF["gates"], strict=True):
        assert {k: got[k] for k in ("code", "order", "label", "short", "type")} == want
    assert ref["gate_outcomes"] == REF["gate_outcomes"]


def test_lenses_keep_their_values(ref) -> None:
    got = [{k: v for k, v in lens.items()} for lens in ref["lenses"]]
    assert got == REF["lenses"]


def test_structural_vocabulary_unchanged(ref) -> None:
    for key in (
        "item_statuses",
        "done_statuses",
        "na_statuses",
        "gap_statuses",
        "flavour_rule_note",
    ):
        assert ref[key] == REF[key]
    assert ref["design_effectiveness_options"] == REF["design_effectiveness_options"]


def test_project_types_keep_old_fields_and_gain_flags(ref) -> None:
    assert [p["code"] for p in ref["project_types"]] == [p["code"] for p in REF["project_types"]]
    for got, want in zip(ref["project_types"], REF["project_types"], strict=True):
        assert got["checklists"] == want["checklists"]
        assert got["requires_tiering"] == want.get("requires_tiering", False)
        assert got["note"] == want.get("note")
        assert got["label"] == want["code"] and got["active"] is True
    by_code = {p["code"]: p for p in ref["project_types"]}
    for code in ("Agentic AI", "Combined"):
        assert by_code[code]["has_ai_profile"] and by_code[code]["has_eval_metrics"]
        assert by_code[code]["required_intake_fields"] == [
            "audience",
            "write_actions",
            "sensitive_data",
        ]
    for code in ("Normal", "Infrastructure"):
        assert not by_code[code]["has_ai_profile"] and not by_code[code]["has_eval_metrics"]


def test_portfolios_stay_a_name_list_in_seed_order(ref) -> None:
    assert ref["portfolios"] == REF["portfolios"]
    assert [p["name"] for p in ref["portfolio_details"]] == REF["portfolios"]
    detail = {p["name"]: p for p in ref["portfolio_details"]}
    assert detail["Retail Site Systems"]["requires_sites"] is True
    assert not any(p["requires_sites"] for n, p in detail.items() if n != "Retail Site Systems")
    for p in detail.values():
        assert {"name", "code", "focus_areas", "intake_extra_fields", "golden_set_count"} <= set(p)
        assert p["label"] == p["name"] and p["intake_extra_fields"] == []


def test_regions_and_intake_options_are_value_lists(ref) -> None:
    assert ref["regions"] == REF["regions"]
    for key, values in REF["intake_options"].items():
        assert ref["intake_options"][key] == values  # plain active VALUES, old clients keep working


def test_tiering_reference_unchanged(ref) -> None:
    assert ref["tiers"] == REF["tiers"]
    assert ref["tier_dimensions"] == REF["tier_dimensions"]
    assert ref["tier_questions"] == REF["tier_questions"]


def test_rag_rule_text_is_generated_and_equals_the_legacy_text(ref) -> None:
    assert ref["rag_rule"] == REF["rag_rule"]


def test_approval_chains_keep_step_role_label(ref) -> None:
    for chain, steps in REF["approval_chains"].items():
        got = [{k: s[k] for k in ("step", "role", "label")} for s in ref["approval_chains"][chain]]
        assert got == steps
    # the mocked step is flagged
    assert [s["is_mock"] for s in ref["approval_chains"]["EXCEPTION"]] == [False, True]


def test_risk_acceptance_and_ocet(ref) -> None:
    assert ref["risk_acceptance_routes"] == REF["risk_acceptance_routes"]
    assert ref["risk_acceptance_then"] == REF["risk_acceptance_then"]
    for key in (
        "categories",
        "pricing_basis",
        "currencies",
        "default_horizon_years",
        "default_growth_pct",
        "statuses",
    ):
        assert ref["ocet"][key] == REF["ocet"][key]


def test_roles_keep_code_and_label(ref) -> None:
    assert [{"code": r["code"], "label": r["label"]} for r in ref["roles"]] == REF["roles"]
    slots = {r["code"]: r["transition_column"] for r in ref["roles"] if r["has_transition_slot"]}
    assert slots == {
        "OR_FOCAL": "or_focal_user_id",
        "PM": "pm_user_id",
        "ARCHITECT": "architect_user_id",
        "OLM": "olm_user_id",
        "IRM": "irm_user_id",
    }


def test_enums_keep_their_keys_and_values(ref) -> None:
    assert set(ref["enums"]) == {
        "severities",
        "evidence_types",
        "evidence_statuses",
        "action_statuses",
        "action_priorities",
        "condition_statuses",
        "exception_statuses",
        "risk_ratings",
        "defect_priorities",
        "defect_statuses",
        "actor_types",
        "draft_kinds",
        "approval_types",
        "applicability",
        "item_sources",
    }
    e = ref["enums"]
    assert e["severities"] == ["Critical", "Major", "Minor"]
    assert e["evidence_types"] == ["Document", "Link", "Email sign-off", "Recording", "Generated"]
    assert e["action_priorities"] == ["High", "Medium", "Low"]
    assert e["defect_priorities"] == ["P1", "P2", "P3", "P4"]
    assert e["item_sources"] == ["FRAMEWORK", "AI_PLAYBOOK", "PORTFOLIO", "COMMON"]
    assert e["exception_statuses"][0] == "Draft" and e["exception_statuses"][-2:] == [
        "Approved",
        "Rejected",
    ]


def test_new_additive_keys(ref) -> None:
    lists = ref["lists"]
    assert {
        "regions",
        "severities",
        "evidence_types",
        "owner_hints",
        "glossary",
        "operating_rhythm",
    } <= set(lists)
    assert [o["value"] for o in lists["severities"]] == ["Critical", "Major", "Minor"]
    assert all(
        {"value", "label", "description", "meta", "active"} <= set(o) for o in lists["regions"]
    )
    keys = [f["key"] for f in ref["intake_fields"]]
    assert keys[:4] == ["name", "project_type", "portfolio", "region"]
    assert {f["key"] for f in ref["intake_fields"] if f["structural"]} == {
        "name",
        "project_type",
        "portfolio",
        "region",
        "or_focal_user_id",
    }
    assert [c["code"] for c in ref["checklists"]] == [
        "FRAMEWORK",
        "AI_PLAYBOOK",
        "PORTFOLIO",
        "COMMON",
    ]
    assert ref["thresholds"]["rag"]["red_critical_gaps"] == 2
    assert ref["gate_labels"]["SG4_ATD"]["short"] == "AtD"
    assert ref["labels"]["rag.Grey"]


def test_include_inactive_flag_is_accepted(client) -> None:
    r = client.get("/api/v1/reference", params={"include_inactive": "true"})
    assert r.status_code == 200
    assert r.json()["project_types"]
