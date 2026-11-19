"""BR-010 checklist assembly (spec 7.1), AC-03 at rule level, owners (A-11), linked modules (A-10)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.config import get_settings
from app.rules.checklist import (
    ChecklistDef,
    ExistingItem,
    LibraryItem,
    TransitionRoles,
    assemble_checklist,
    default_owner_role,
    reassemble,
    role_from_hint,
    summarize_counts,
)
from app.seed import loader

ROLES = TransitionRoles(or_focal="U01", pm="U10", architect="U11", olm="U12", irm="U14")
FRAMEWORK_ONLY = ["FRAMEWORK"]
WITH_AI = ["FRAMEWORK", "AI_PLAYBOOK"]
TIER2_EXCLUDED = {
    "S45-007",
    "S45-008",
    "S45-016",
    "S45-017",
    "S45-018",
    "S45-025",
    "S45-028",
    "S45-029",
}


@pytest.fixture(scope="module")
def library() -> list[LibraryItem]:
    seed_dir = Path(get_settings().seed_dir)
    rows = loader._library_rows(
        loader._read(seed_dir, "framework_activities.json"),
        loader._read(seed_dir, "ai_playbook_items.json"),
        loader._read(seed_dir, "portfolios.json"),
    )
    return [loader._to_library_item(r) for r in rows]


def assemble(library, project_type, portfolio="GCC", tier=None, checklists=FRAMEWORK_ONLY):
    return assemble_checklist(library, project_type, portfolio, tier, checklists, ROLES)


@pytest.mark.parametrize("project_type", ["Normal", "Infrastructure"])
def test_framework_only_flavours(library, project_type):
    planned = assemble(library, project_type, "GCC")
    counts = summarize_counts(planned)
    assert counts["framework"] == 72
    assert counts["ai_applicable"] == 0 and counts["ai_excluded"] == 0
    assert counts["common"] == 2
    # GCC golden set: 5 items, none mandatory -> all To confirm
    assert counts["golden_set_applies"] == 0 and counts["golden_set_to_confirm"] == 5
    # 72 framework + ALL-01 (always); ALL-02 "if applicable" is To confirm
    assert counts["total_applicable"] == 73
    assert {p.playbook_item_id for p in planned if p.applicability == "To confirm"} >= {"ALL-02"}


def test_golden_set_mandatory_applies_others_to_confirm(library):
    planned = assemble(library, "Normal", "Telecoms")
    counts = summarize_counts(planned)
    assert counts["golden_set_applies"] == 3  # Telecoms has 3 mandatory of 8
    assert counts["golden_set_to_confirm"] == 5
    # only the transition's own portfolio is added
    assert not any(p.portfolio not in (None, "Telecoms") for p in planned)


@pytest.mark.parametrize("project_type", ["Agentic AI", "Combined"])
def test_tier2_ai_items_and_exclusions_ac03(library, project_type):
    planned = assemble(library, project_type, "GCC", tier=2, checklists=WITH_AI)
    counts = summarize_counts(planned)
    assert counts["ai_applicable"] == 208
    assert counts["ai_excluded"] == 8
    excluded = [p for p in planned if p.source == "AI_PLAYBOOK" and p.applicability != "Applies"]
    assert {p.playbook_item_id for p in excluded} == TIER2_EXCLUDED
    for p in excluded:
        assert p.applicability == "Not applicable"
        assert p.excluded_by == "tier"
        assert p.status == ("Not applicable" if p.lens == "Compliance" else "N/A")
    for p in planned:
        if p.applicability != "Not applicable":
            assert p.status == "Not started"
            assert p.excluded_by is None


def test_tier1_excludes_24_and_unknown_tier_applies_all(library):
    tier1 = summarize_counts(assemble(library, "Agentic AI", tier=1, checklists=WITH_AI))
    assert (tier1["ai_applicable"], tier1["ai_excluded"]) == (192, 24)
    tier4 = summarize_counts(assemble(library, "Agentic AI", tier=4, checklists=WITH_AI))
    assert (tier4["ai_applicable"], tier4["ai_excluded"]) == (216, 0)
    unknown = summarize_counts(assemble(library, "Agentic AI", tier=None, checklists=WITH_AI))
    assert (unknown["ai_applicable"], unknown["ai_excluded"]) == (216, 0)  # A-35


def test_project_type_exclusion_and_inactive_items():
    only_ai = LibraryItem(
        id="X-1",
        source="FRAMEWORK",
        gate="SG0",
        lens="Technical",
        applies_to_project_types=("Agentic AI",),
    )
    retired = replace(only_ai, id="X-2", applies_to_project_types=(), active=False)
    planned = assemble_checklist([only_ai, retired], "Normal", "GCC", None, FRAMEWORK_ONLY, ROLES)
    assert [p.playbook_item_id for p in planned] == ["X-1"]  # inactive item never planned
    assert planned[0].applicability == "Not applicable"
    assert planned[0].excluded_by == "project_type"
    assert planned[0].status == "N/A"


@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        ("S&T (table for review), Cloud Workstream", "or_focal"),
        ("Architect (solution clarity), Project Team", "architect"),
        ("Project Team (scope clarity)", "pm"),
        ("SOM (OLM) review", "olm"),
        ("Project (drives), S&T (documentation)", "pm"),  # leftmost keyword wins
        ("Project Architecture", "pm"),
        ("Architecture review", "architect"),
        ("PM", "pm"),
        ("Business owner / Product", None),
        ("ERS (access)", None),
        ("", None),
        ("Some SOMEthing", None),  # keywords match whole words only
    ],
)
def test_role_from_hint(hint, expected):
    assert role_from_hint(hint) == expected


def _item(lens, hint="", category="", kind="Check") -> LibraryItem:
    return LibraryItem(
        id="T-1",
        source="FRAMEWORK",
        gate="SG2",
        lens=lens,
        owner_role_hint=hint,
        category=category,
        kind=kind,
    )


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (_item("Compliance", hint="Project Team"), "irm"),  # compliance is always IRM
        (_item("Business"), "pm"),
        (_item("Technical"), "pm"),
        (_item("Technical", category="Scope Clarity & Architecture"), "architect"),
        (_item("Technical", kind="Support model"), "architect"),
        (_item("Business", category="Scope Clarity & Architecture"), "pm"),
        (_item("Technical", hint="S&T", kind="Support model"), "or_focal"),  # hint beats default
    ],
)
def test_default_owner_role(item, expected):
    assert default_owner_role(item) == expected


def test_owners_on_real_library_never_irm_for_business_technical(library):
    planned = assemble(library, "Agentic AI", "Retail Site Systems", 3, WITH_AI)
    for p in planned:
        if p.lens == "Compliance":
            assert p.owner_user_id == "U14"
        else:
            assert p.owner_user_id in {"U01", "U10", "U11", "U12"}
            assert p.owner_user_id != "U14"


def test_missing_role_gives_no_owner(library):
    planned = assemble_checklist(
        library, "Normal", "GCC", None, FRAMEWORK_ONLY, TransitionRoles(or_focal="U01")
    )
    compliance = [p for p in planned if p.lens == "Compliance"]
    assert compliance and all(p.owner_user_id is None for p in compliance)


def test_linked_modules_a10(library):
    planned = {
        p.playbook_item_id: p for p in assemble(library, "Agentic AI", tier=4, checklists=WITH_AI)
    }
    assert planned["FW-008"].linked_module == "OCET"
    assert planned["S45-006"].linked_module == "OCET"
    for n in range(27, 36):
        assert planned[f"FW-{n:03d}"].linked_module == "SUPPORT_MODEL"
    sm = [i for i in library if i.id.startswith("SM-")]
    assert sm, "Support Model sheet items expected in the AI playbook"
    for item in sm:
        expected = None if item.lens == "Compliance" else "SUPPORT_MODEL"
        assert planned[item.id].linked_module == expected
    assert planned["FW-001"].linked_module is None


def test_reassemble_tier_change_keeps_statuses_and_counts_changes(library):
    tier4 = assemble(library, "Agentic AI", tier=4, checklists=WITH_AI)
    existing = [
        ExistingItem(p.playbook_item_id, p.applicability, p.excluded_by, "Complete") for p in tier4
    ]
    tier2 = assemble(library, "Agentic AI", tier=2, checklists=WITH_AI)
    result = reassemble(existing, tier2)
    assert result.counts["excluded"] == 8
    assert result.counts["added"] == 0 and result.counts["restored"] == 0
    assert result.counts["unchanged"] == len(tier2) - 8
    assert {c.playbook_item_id for c in result.changes} == TIER2_EXCLUDED
    for change in result.changes:
        assert change.change == "excluded"
        assert change.applicability == "Not applicable" and change.excluded_by == "tier"
        assert change.status in {"N/A", "Not applicable"}
    # unchanged items are not listed, so their statuses/notes/evidence are never touched
    assert len(result.changes) == 8


def test_reassemble_restore_add_and_manual_na(library):
    tier2 = assemble(library, "Agentic AI", tier=2, checklists=WITH_AI)
    existing = [
        ExistingItem(p.playbook_item_id, p.applicability, p.excluded_by, "In progress")
        for p in tier2
        if p.playbook_item_id != "FW-001"  # missing on the transition -> will be "added"
    ]
    # a human marked FW-002 N/A (no excluded_by): a later plan must not restore it
    existing = [
        (
            replace(e, applicability="Not applicable", excluded_by=None, status="N/A")
            if e.playbook_item_id == "FW-002"
            else e
        )
        for e in existing
    ]
    tier4 = assemble(library, "Agentic AI", tier=4, checklists=WITH_AI)
    result = reassemble(existing, tier4)
    by_kind = {}
    for change in result.changes:
        by_kind.setdefault(change.change, []).append(change.playbook_item_id)
    assert set(by_kind["restored"]) == TIER2_EXCLUDED
    assert by_kind["added"] == ["FW-001"]
    assert "FW-002" not in {c.playbook_item_id for c in result.changes}
    assert result.counts == {
        "added": 1,
        "excluded": 0,
        "restored": 8,
        "unchanged": len(tier4) - 9,
    }
    for change in result.changes:
        if change.change == "restored":
            assert change.applicability == "Applies" and change.status == "Not started"
            assert change.excluded_by is None


# --- CR-01: checklists and owner hints are configuration -----------------------------------------

SECURITY = ChecklistDef("SECURITY_PLAYBOOK")  # an Admin-added "library" checklist
SECURITY_ITEMS = [
    LibraryItem(id="SEC-1", source="SECURITY_PLAYBOOK", gate="SG0", lens="Business"),
    LibraryItem(id="SEC-2", source="SECURITY_PLAYBOOK", gate="SG3", lens="Technical"),
]


def _with_security(library):
    return [*library, *SECURITY_ITEMS]


def test_default_definitions_change_nothing(library):
    from app.rules.checklist import DEFAULT_CHECKLIST_DEFS

    plain = assemble(library, "Agentic AI", "GCC", 2, WITH_AI)
    explicit = assemble_checklist(
        library, "Agentic AI", "GCC", 2, WITH_AI, ROLES, checklist_defs=DEFAULT_CHECKLIST_DEFS
    )
    assert plain == explicit


def test_admin_added_checklist_is_assembled_when_the_type_lists_it(library):
    defs = [*loader_defaults(), SECURITY]
    planned = assemble_checklist(
        _with_security(library),
        "Security Review",
        "GCC",
        None,
        ["FRAMEWORK", "SECURITY_PLAYBOOK"],
        ROLES,
        checklist_defs=defs,
    )
    sources = {p.source for p in planned}
    assert sources == {"FRAMEWORK", "SECURITY_PLAYBOOK", "COMMON", "PORTFOLIO"}
    security = [p for p in planned if p.source == "SECURITY_PLAYBOOK"]
    assert [p.applicability for p in security] == ["Applies", "Applies"]  # not tier filtered
    counts = summarize_counts(planned)
    assert counts["other"] == 2 and counts["ai_applicable"] == 0
    assert counts["total_applicable"] == 72 + 1 + 2  # framework + ALL-01 + the two security items


def test_checklist_not_listed_by_the_type_is_skipped(library):
    planned = assemble_checklist(
        _with_security(library),
        "Normal",
        "GCC",
        None,
        FRAMEWORK_ONLY,
        ROLES,
        checklist_defs=[*loader_defaults(), SECURITY],
    )
    assert "SECURITY_PLAYBOOK" not in {p.source for p in planned}


def test_unknown_checklist_is_never_guessed(library):
    # SECURITY_PLAYBOOK is not a configured checklist here: its items are ignored
    planned = assemble_checklist(
        _with_security(library),
        "Normal",
        "GCC",
        None,
        ["FRAMEWORK", "SECURITY_PLAYBOOK"],
        ROLES,
    )
    assert "SECURITY_PLAYBOOK" not in {p.source for p in planned}


def test_tier_filter_follows_the_checklist_definition_not_its_name():
    tiered = ChecklistDef("RISK_LIST", tier_filtered=True)
    items = [
        LibraryItem(
            id="R-1", source="RISK_LIST", gate="SG0", lens="Business", applicable_tiers=(3, 4)
        ),
        LibraryItem(
            id="R-2", source="RISK_LIST", gate="SG0", lens="Business", applicable_tiers=(1,)
        ),
    ]

    def run(tier):
        return {
            p.playbook_item_id: p.applicability
            for p in assemble_checklist(
                items, "X", "GCC", tier, ["RISK_LIST"], ROLES, checklist_defs=[tiered]
            )
        }

    assert run(3) == {"R-1": "Applies", "R-2": "Not applicable"}
    assert run(None) == {"R-1": "Applies", "R-2": "Applies"}  # no tier yet: everything applies


def test_reassemble_excludes_dropped_admin_checklist_items_by_project_type(library):
    from app.rules.checklist import ExistingItem

    defs = [*loader_defaults(), SECURITY]
    items = _with_security(library)
    existing = [ExistingItem("SEC-1", "Applies", None, "Not started")]
    planned = assemble_checklist(
        items, "Normal", "GCC", None, FRAMEWORK_ONLY, ROLES, checklist_defs=defs
    )
    result = reassemble(existing, planned, items, checklist_defs=defs)
    change = next(c for c in result.changes if c.playbook_item_id == "SEC-1")
    assert (change.change, change.excluded_by) == ("excluded", "project_type")


def loader_defaults():
    from app.rules.checklist import DEFAULT_CHECKLIST_DEFS

    return list(DEFAULT_CHECKLIST_DEFS)


def test_owner_hints_come_from_configuration():
    hints = [("Security", "ARCHITECT"), ("Delivery", "PM")]
    assert role_from_hint("Security (review), Delivery", hints) == "architect"  # leftmost wins
    assert role_from_hint("Delivery then Security", hints) == "pm"
    assert role_from_hint("S&T", hints) is None  # the default keywords are replaced, not added
    item = _item("Business", hint="Security team")
    assert default_owner_role(item, hints) == "architect"


def test_item_default_owner_role_beats_hint_and_lens():
    item = LibraryItem(
        id="T-2",
        source="FRAMEWORK",
        gate="SG2",
        lens="Compliance",
        owner_role_hint="Project Team",
        default_owner_role="OLM",
    )
    assert default_owner_role(item) == "olm"
    item_unknown = LibraryItem(
        id="T-3", source="FRAMEWORK", gate="SG2", lens="Compliance", default_owner_role="NO_SUCH"
    )
    assert default_owner_role(item_unknown) == "irm"  # an unknown role code falls back to the rules
