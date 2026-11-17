"""Checklist assembly (BR-010, spec §7.1). PURE: no DB, no I/O.

``assemble_checklist`` decides, for one transition flavour (project type + portfolio + tier), which
library items apply, which are excluded (tier / project type), which still need the OR focal's
confirmation, who owns them by default and what their first status is.

``reassemble`` implements BR-010 step 7 (re-assembly after a tier change): it compares the items a
transition already has with a freshly assembled plan and returns the changes to persist (M3 does
the persisting and writes the audit event with the counts).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.rules.constants import (
    APPLIES,
    NOT_APPLICABLE,
    NOT_STARTED,
    TO_CONFIRM,
    na_status_for,
)

SOURCE_FRAMEWORK = "FRAMEWORK"
SOURCE_AI_PLAYBOOK = "AI_PLAYBOOK"
SOURCE_PORTFOLIO = "PORTFOLIO"
SOURCE_COMMON = "COMMON"

EXCLUDED_BY_TIER = "tier"
EXCLUDED_BY_PROJECT_TYPE = "project_type"
EXCLUDED_BY_PORTFOLIO = "portfolio"

SCOPE_CLARITY_CATEGORY = "Scope Clarity & Architecture"
SUPPORT_MODEL_KIND = "Support model"


@dataclass(frozen=True)
class LibraryItem:
    """The subset of a PlaybookItem that assembly needs."""

    id: str
    source: str  # FRAMEWORK | AI_PLAYBOOK | PORTFOLIO | COMMON
    gate: str
    lens: str
    portfolio: str | None = None
    category: str = ""
    kind: str = "Deliverable"
    applicable_tiers: Sequence[int] = ()
    mandatory: bool = True
    mandatory_rule: str | None = None  # always | if_applicable
    applies_to_project_types: Sequence[str] = ()  # empty = all project types
    owner_role_hint: str = ""
    linked_module: str | None = None
    active: bool = True


@dataclass(frozen=True)
class TransitionRoles:
    """User ids of the people on a transition (None when the role is not filled)."""

    or_focal: str | None = None
    pm: str | None = None
    architect: str | None = None
    olm: str | None = None
    irm: str | None = None


@dataclass(frozen=True)
class PlannedItem:
    """One TransitionItem as BR-010 would create it."""

    playbook_item_id: str
    applicability: str  # Applies | Not applicable | To confirm
    excluded_by: str | None  # tier | project_type | None
    status: str
    due_gate: str
    owner_user_id: str | None
    linked_module: str | None
    lens: str
    source: str = ""
    portfolio: str | None = None


@dataclass(frozen=True)
class ExistingItem:
    """What reassembly needs to know about an item the transition already has."""

    playbook_item_id: str
    applicability: str
    excluded_by: str | None
    status: str


@dataclass(frozen=True)
class ItemChange:
    """A change to persist after re-assembly. Untouched items are not listed."""

    playbook_item_id: str
    change: str  # added | excluded | restored
    applicability: str
    excluded_by: str | None
    status: str
    planned: PlannedItem  # full plan row (used to create the item when ``change == "added"``)


@dataclass
class Reassembly:
    changes: list[ItemChange] = field(default_factory=list)
    counts: dict[str, int] = field(
        default_factory=lambda: {"added": 0, "excluded": 0, "restored": 0, "unchanged": 0}
    )


# --- owners (A-11) -----------------------------------------------------------------------------

# Scanned left to right; the first keyword found in ``owner_role_hint`` wins.
_ROLE_PATTERN = re.compile(r"\b(S&T|Architecture|Architect|SOM|OLM|Project|PM)\b", re.IGNORECASE)
_ROLE_BY_KEYWORD = {
    "s&t": "or_focal",
    "architect": "architect",
    "architecture": "architect",
    "som": "olm",
    "olm": "olm",
    "project": "pm",
    "pm": "pm",
}


def role_from_hint(owner_role_hint: str) -> str | None:
    """Role attribute name ("or_focal", "architect", "olm", "pm") named first in the hint."""
    match = _ROLE_PATTERN.search(owner_role_hint or "")
    return _ROLE_BY_KEYWORD[match.group(1).lower()] if match else None


def default_owner_role(item: LibraryItem) -> str:
    """Role attribute of ``TransitionRoles`` that owns ``item`` by default (A-11, BR-010 step 6)."""
    if item.lens == "Compliance":
        return "irm"
    hinted = role_from_hint(item.owner_role_hint)  # never "irm": IRM is not a keyword
    if hinted is not None:
        return hinted
    if item.lens == "Technical" and (
        item.category == SCOPE_CLARITY_CATEGORY or item.kind == SUPPORT_MODEL_KIND
    ):
        return "architect"
    return "pm"


def default_owner(item: LibraryItem, roles: TransitionRoles) -> str | None:
    return getattr(roles, default_owner_role(item))


# --- assembly (BR-010) -------------------------------------------------------------------------


def _plan(
    item: LibraryItem,
    roles: TransitionRoles,
    applicability: str,
    excluded_by: str | None = None,
) -> PlannedItem:
    excluded = applicability == NOT_APPLICABLE
    return PlannedItem(
        playbook_item_id=item.id,
        applicability=applicability,
        excluded_by=excluded_by,
        # Excluded items carry the lens' N/A status so they never count as open work.
        status=na_status_for(item.lens) if excluded else NOT_STARTED,
        due_gate=item.gate,
        owner_user_id=default_owner(item, roles),
        linked_module=item.linked_module,  # A-10
        lens=item.lens,
        source=item.source,
        portfolio=item.portfolio,
    )


def assemble_checklist(
    library: Iterable[LibraryItem],
    project_type: str,
    portfolio: str,
    tier: int | None,
    flavour_checklists: Sequence[str],
    roles: TransitionRoles,
) -> list[PlannedItem]:
    """Plan the TransitionItems of one transition (BR-010 steps 1-6). Library order is preserved.

    ``tier`` None means "not proposed yet": every AI Playbook item applies (A-35).
    """
    planned: list[PlannedItem] = []
    for item in library:
        if not item.active:
            continue

        if item.source == SOURCE_FRAMEWORK:
            if SOURCE_FRAMEWORK not in flavour_checklists:
                continue
            applicability = APPLIES
        elif item.source == SOURCE_AI_PLAYBOOK:
            if SOURCE_AI_PLAYBOOK not in flavour_checklists:
                continue
            in_tier = tier is None or tier in item.applicable_tiers
            applicability = APPLIES if in_tier else NOT_APPLICABLE
        elif item.source == SOURCE_PORTFOLIO:
            if item.portfolio != portfolio:
                continue
            applicability = APPLIES if item.mandatory else TO_CONFIRM
        elif item.source == SOURCE_COMMON:
            always = item.mandatory_rule == "always" or (
                item.mandatory_rule is None and item.mandatory
            )
            applicability = APPLIES if always else TO_CONFIRM
        else:
            continue  # unknown source: never guess

        excluded_by = EXCLUDED_BY_TIER if applicability == NOT_APPLICABLE else None
        # Project-type exclusion wins: the item does not belong to this flavour at all.
        if item.applies_to_project_types and project_type not in item.applies_to_project_types:
            applicability, excluded_by = NOT_APPLICABLE, EXCLUDED_BY_PROJECT_TYPE

        planned.append(_plan(item, roles, applicability, excluded_by))
    return planned


def summarize_counts(planned: Iterable[PlannedItem]) -> dict[str, int]:
    """Numbers shown on the Scope page ("13 items not applicable for Tier 2 (view)")."""
    counts = {
        "framework": 0,
        "ai_applicable": 0,
        "ai_excluded": 0,
        "golden_set_applies": 0,
        "golden_set_to_confirm": 0,
        "common": 0,
        "total_applicable": 0,
    }
    for p in planned:
        if p.applicability == APPLIES:
            counts["total_applicable"] += 1
        if p.source == SOURCE_FRAMEWORK:
            counts["framework"] += 1
        elif p.source == SOURCE_AI_PLAYBOOK:
            if p.applicability == APPLIES:
                counts["ai_applicable"] += 1
            elif p.applicability == NOT_APPLICABLE:
                counts["ai_excluded"] += 1
        elif p.source == SOURCE_PORTFOLIO:
            if p.applicability == APPLIES:
                counts["golden_set_applies"] += 1
            elif p.applicability == TO_CONFIRM:
                counts["golden_set_to_confirm"] += 1
        elif p.source == SOURCE_COMMON:
            counts["common"] += 1
    return counts


# --- re-assembly (BR-010 step 7) ----------------------------------------------------------------


def reassemble(
    existing: Iterable[ExistingItem],
    planned: Iterable[PlannedItem],
    library: Iterable[LibraryItem] = (),
) -> Reassembly:
    """Compare a transition's current items with a fresh plan.

    * still applicable                 -> unchanged (status, note, severity, DE, evidence are kept)
    * applicable now, excluded in plan -> ``excluded``: Not applicable + excluded_by + lens N/A status
    * excluded by tier/project type, applicable in plan -> ``restored``: plan applicability, Not started
    * in plan but not on the transition -> ``added`` (created exactly as planned)

    * applicable now, dropped from the plan (project type / portfolio changed), library line still
      active -> ``excluded`` by ``project_type`` (framework, AI playbook) or ``portfolio`` (golden
      set of another portfolio). ``library`` supplies source and lens for these.

    A human's own "Not applicable" decision (``excluded_by`` None) is never overridden. Items whose
    library line is retired or unknown are left alone.
    """
    existing = list(existing)
    planned = list(planned)
    by_id = {e.playbook_item_id: e for e in existing}
    result = Reassembly()
    for plan in planned:
        current = by_id.get(plan.playbook_item_id)
        change: str | None = None
        if current is None:
            change = "added"
        elif plan.applicability == NOT_APPLICABLE and current.applicability != NOT_APPLICABLE:
            change = "excluded"
        elif (
            plan.applicability != NOT_APPLICABLE
            and current.applicability == NOT_APPLICABLE
            and current.excluded_by is not None
        ):
            change = "restored"

        if change is None:
            result.counts["unchanged"] += 1
            continue
        result.counts[change] += 1
        result.changes.append(
            ItemChange(
                playbook_item_id=plan.playbook_item_id,
                change=change,
                applicability=plan.applicability,
                excluded_by=plan.excluded_by,
                status=plan.status,  # N/A status for excluded, Not started otherwise
                planned=plan,
            )
        )

    planned_ids = {p.playbook_item_id for p in planned}
    lib_by_id = {item.id: item for item in library}
    for current in existing:
        item = lib_by_id.get(current.playbook_item_id)
        if (
            current.playbook_item_id in planned_ids
            or item is None
            or not item.active
            or current.applicability not in (APPLIES, TO_CONFIRM)
        ):
            continue
        if item.source == SOURCE_PORTFOLIO:
            excluded_by = EXCLUDED_BY_PORTFOLIO
        elif item.source in (SOURCE_AI_PLAYBOOK, SOURCE_FRAMEWORK):
            excluded_by = EXCLUDED_BY_PROJECT_TYPE
        else:
            continue
        status = na_status_for(item.lens)
        result.counts["excluded"] += 1
        result.changes.append(
            ItemChange(
                playbook_item_id=current.playbook_item_id,
                change="excluded",
                applicability=NOT_APPLICABLE,
                excluded_by=excluded_by,
                status=status,
                planned=PlannedItem(
                    playbook_item_id=item.id,
                    applicability=NOT_APPLICABLE,
                    excluded_by=excluded_by,
                    status=status,
                    due_gate=item.gate,
                    owner_user_id=None,
                    linked_module=item.linked_module,
                    lens=item.lens,
                    source=item.source,
                    portfolio=item.portfolio,
                ),
            )
        )
    return result
