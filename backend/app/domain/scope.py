"""Scope page, assessment launch and checklist (re-)assembly persistence (BR-010, FR-022; A-35, A-40).

The pure planning lives in ``app.rules.checklist``; this module loads the library, applies the OR
focal's scope decisions, persists TransitionItems and writes the audit events with counts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain import audit
from app.errors import BadRequest, Conflict
from app.models import (
    FlavourRule,
    PlaybookItem,
    Portfolio,
    TierAssessment,
    Transition,
    TransitionItem,
    User,
)
from app.rules.checklist import (
    EXCLUDED_BY_PROJECT_TYPE,
    SOURCE_COMMON,
    SOURCE_PORTFOLIO,
    ExistingItem,
    LibraryItem,
    PlannedItem,
    TransitionRoles,
    assemble_checklist,
    reassemble,
    summarize_counts,
)
from app.rules.constants import (
    ACTOR_HUMAN,
    APPLIES,
    GATE_SHORT,
    NA_STATUSES,
    NOT_APPLICABLE,
    NOT_STARTED,
    TO_CONFIRM,
    na_status_for,
)
from app.schemas.scope import (
    LaunchOut,
    RecommendationOut,
    ScopeCountsOut,
    ScopeOut,
    ScopeRowOut,
    ScopeUpdateIn,
    TierBannerOut,
)
from app.services.factory import get_ai_service

DEFAULT_CHECKLISTS: tuple[str, ...] = ("FRAMEWORK",)
_YES, _NO = "Yes", "No"
_APPLIES_TO_DECISION = {APPLIES: _YES, NOT_APPLICABLE: _NO, TO_CONFIRM: TO_CONFIRM}


# --- loading -------------------------------------------------------------------------------------


def to_library_item(row: PlaybookItem) -> LibraryItem:
    return LibraryItem(
        id=row.id,
        source=row.source,
        portfolio=row.portfolio,
        gate=row.gate,
        lens=row.lens,
        category=row.category or "",
        kind=row.kind or "Deliverable",
        applicable_tiers=tuple(row.applicable_tiers or ()),
        mandatory=True if row.mandatory is None else row.mandatory,
        mandatory_rule=row.mandatory_rule,
        applies_to_project_types=tuple(row.applies_to_project_types or ()),
        owner_role_hint=row.owner_role_hint or "",
        linked_module=row.linked_module,
        active=True if row.active is None else row.active,
    )


def library_rows(db: Session) -> list[PlaybookItem]:
    """Every library line in display order (active and retired, re-assembly needs both)."""
    return list(db.scalars(select(PlaybookItem).order_by(PlaybookItem.sort_order, PlaybookItem.id)))


def flavour_checklists(db: Session, project_type: str) -> list[str]:
    rule = db.get(FlavourRule, project_type)
    return list(rule.checklists) if rule is not None else list(DEFAULT_CHECKLISTS)


def requires_tiering(db: Session, project_type: str) -> bool:
    rule = db.get(FlavourRule, project_type)
    return bool(rule and rule.requires_tiering)


def roles_of(t: Transition) -> TransitionRoles:
    return TransitionRoles(
        or_focal=t.or_focal_user_id,
        pm=t.pm_user_id,
        architect=t.architect_user_id,
        olm=t.olm_user_id,
        irm=t.irm_user_id,
    )


def get_assessment(db: Session, transition_id: str) -> TierAssessment | None:
    return db.scalar(select(TierAssessment).where(TierAssessment.transition_id == transition_id))


def applied_tier(db: Session, t: Transition) -> int | None:
    """Tier used for the checklist: confirmed, else proposed, else None (A-35)."""
    assessment = get_assessment(db, t.id)
    if assessment is not None:
        if assessment.confirmed_tier is not None:
            return assessment.confirmed_tier
        if assessment.proposed_tier is not None:
            return assessment.proposed_tier
    return t.risk_tier


def plan_transition(
    db: Session, t: Transition, rows: Sequence[PlaybookItem] | None = None
) -> list[PlannedItem]:
    """BR-010 plan for ``t`` as it is now (no scope decisions applied)."""
    library = [to_library_item(r) for r in (rows if rows is not None else library_rows(db))]
    return assemble_checklist(
        library,
        t.project_type,
        t.portfolio,
        applied_tier(db, t),
        flavour_checklists(db, t.project_type),
        roles_of(t),
    )


# --- scope decisions -----------------------------------------------------------------------------


def is_locked(row: PlaybookItem) -> bool:
    """Mandatory golden-set rows and "always" common rows are locked to Yes."""
    if row.source == SOURCE_PORTFOLIO:
        return bool(row.mandatory)
    if row.source == SOURCE_COMMON:
        return row.mandatory_rule == "always" or (
            row.mandatory_rule is None and bool(row.mandatory)
        )
    return False


def default_applies(row: PlaybookItem) -> str:
    return _YES if is_locked(row) else TO_CONFIRM


def apply_decisions(
    planned: Sequence[PlannedItem], decisions: Mapping[str, Mapping[str, Any]]
) -> list[PlannedItem]:
    """Overlay the OR focal's decisions on golden-set / common rows (Yes -> Applies, No -> Not
    applicable with ``excluded_by`` None, To confirm -> To confirm). Rows excluded by project type
    are never changed."""
    result: list[PlannedItem] = []
    for p in planned:
        decision = decisions.get(p.playbook_item_id)
        if (
            decision is None
            or p.source not in (SOURCE_PORTFOLIO, SOURCE_COMMON)
            or p.excluded_by == EXCLUDED_BY_PROJECT_TYPE
        ):
            result.append(p)
            continue
        applies = decision.get("applies")
        if applies == _YES:
            result.append(replace(p, applicability=APPLIES, excluded_by=None, status=NOT_STARTED))
        elif applies == _NO:
            result.append(
                replace(
                    p,
                    applicability=NOT_APPLICABLE,
                    excluded_by=None,
                    status=na_status_for(p.lens),
                )
            )
        elif applies == TO_CONFIRM:
            result.append(
                replace(p, applicability=TO_CONFIRM, excluded_by=None, status=NOT_STARTED)
            )
        else:
            result.append(p)
    return result


def _effective_decisions(
    t: Transition, rows: Sequence[PlaybookItem]
) -> dict[str, Mapping[str, Any]]:
    """Stored decisions without those on locked rows (locked rows are always Yes)."""
    locked = {r.id for r in rows if is_locked(r)}
    return {k: v for k, v in (t.scope_decisions or {}).items() if k not in locked}


def planned_with_decisions(
    db: Session, t: Transition, rows: Sequence[PlaybookItem] | None = None
) -> list[PlannedItem]:
    rows = rows if rows is not None else library_rows(db)
    return apply_decisions(plan_transition(db, t, rows), _effective_decisions(t, rows))


# --- stored items --------------------------------------------------------------------------------


def stored_items(db: Session, transition_id: str) -> list[TransitionItem]:
    return list(
        db.scalars(
            select(TransitionItem)
            .where(TransitionItem.transition_id == transition_id)
            .order_by(TransitionItem.id)
        )
    )


def stored_counts(items: Sequence[TransitionItem]) -> dict[str, int]:
    """BR-010 ``summarize_counts`` over the stored TransitionItems."""
    return summarize_counts(
        PlannedItem(
            playbook_item_id=i.playbook_item_id,
            applicability=i.applicability,
            excluded_by=i.excluded_by,
            status=i.status,
            due_gate=i.due_gate,
            owner_user_id=i.owner_user_id,
            linked_module=i.linked_module,
            lens=i.playbook_item.lens,
            source=i.playbook_item.source,
            portfolio=i.playbook_item.portfolio,
        )
        for i in items
    )


def _new_item(transition_id: str, p: PlannedItem, na_reason: str | None = None) -> TransitionItem:
    return TransitionItem(
        transition_id=transition_id,
        playbook_item_id=p.playbook_item_id,
        applicability=p.applicability,
        na_reason=na_reason,
        excluded_by=p.excluded_by,
        status=p.status,
        owner_user_id=p.owner_user_id,
        due_gate=p.due_gate,
        note="",
        linked_module=p.linked_module,
        last_updated_by=None,
        last_updated_source="System",
    )


# --- re-assembly (BR-010 step 7, A-40) -----------------------------------------------------------


def reassemble_transition(
    db: Session, t: Transition, actor: User | None, *, action: str, note: str = ""
) -> dict[str, int]:
    """Re-plan the launched transition and persist the changes; returns {added, excluded, restored,
    unchanged}. Writes one audit event with the counts."""
    rows = library_rows(db)
    library = [to_library_item(r) for r in rows]
    planned = plan_transition(db, t, rows)
    items = stored_items(db, t.id)
    by_id = {i.playbook_item_id: i for i in items}
    result = reassemble(
        [ExistingItem(i.playbook_item_id, i.applicability, i.excluded_by, i.status) for i in items],
        planned,
        library,
    )
    for change in result.changes:
        item = by_id.get(change.playbook_item_id)
        if change.change == "added" or item is None:
            db.add(_new_item(t.id, change.planned))
            continue
        item.applicability = change.applicability
        item.excluded_by = change.excluded_by
        item.status = change.status
        item.na_reason = None
    db.flush()
    counts = result.counts
    audit.record(
        db,
        actor=actor,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action=action,
        transition_id=t.id,
        after=dict(counts),
        note=note
        or f"{counts['added']} added, {counts['excluded']} excluded, {counts['restored']} restored",
    )
    return dict(counts)


# --- scope page ----------------------------------------------------------------------------------


def _tier_banner(db: Session, t: Transition) -> TierBannerOut | None:
    if not requires_tiering(db, t.project_type):
        return None
    assessment = get_assessment(db, t.id)
    tier: int | None
    status: str | None
    if assessment is not None and assessment.confirmed_tier is not None:
        tier, status = assessment.confirmed_tier, "Confirmed"
        text = f"Checklist based on confirmed Tier {tier}"
    elif assessment is not None and assessment.proposed_tier is not None:
        tier, status = assessment.proposed_tier, "Proposed"
        text = f"Checklist based on proposed Tier {tier} — confirm tier to finalise"
    else:
        tier, status, text = None, None, "Tier not proposed yet"
    return TierBannerOut(tier=tier, status=status, text=text)


def _row(
    row: PlaybookItem,
    type_label: str,
    stored: TransitionItem | None,
    decisions: Mapping[str, Mapping[str, Any]],
) -> ScopeRowOut:
    locked = is_locked(row)
    decision = decisions.get(row.id) or {}
    reason: str | None = None
    if locked:
        applies = _YES
    elif stored is not None:
        applies = _APPLIES_TO_DECISION.get(stored.applicability, TO_CONFIRM)
        reason = stored.na_reason or decision.get("reason")
    else:
        applies = decision.get("applies") or default_applies(row)
        reason = decision.get("reason")
    return ScopeRowOut(
        id=row.id,
        requirement=row.title,
        type=type_label,  # type: ignore[arg-type]
        gate=row.gate,
        gate_short=GATE_SHORT.get(row.gate, row.gate),
        owner_hint=row.owner_role_hint or "",
        lens=row.lens,
        lens_is_suggested=bool(row.lens_is_suggested),
        applies=applies,
        locked=locked,
        reason=reason or None,
    )


def _flavour_context(db: Session, t: Transition, focus_areas: list[str]) -> dict[str, Any]:
    return {
        "transition_id": t.id,
        "name": t.name,
        "description": t.description or "",
        "project_type": t.project_type,
        "portfolio": t.portfolio,
        "region": t.region,
        "market": t.market,
        "audience": t.audience,
        "write_actions": t.write_actions,
        "sensitive_data": t.sensitive_data,
        "focus_areas": focus_areas,
        "tier": applied_tier(db, t),
    }


def build_scope(db: Session, t: Transition) -> ScopeOut:
    rows = library_rows(db)
    portfolio = db.get(Portfolio, t.portfolio)
    focus_areas = list(portfolio.focus_areas) if portfolio is not None else []
    launched = t.assessment_launched_at is not None
    stored = {i.playbook_item_id: i for i in stored_items(db, t.id)} if launched else {}
    decisions = t.scope_decisions or {}

    golden = [
        _row(r, "Mandatory" if r.mandatory else "Portfolio", stored.get(r.id), decisions)
        for r in rows
        if r.active and r.source == SOURCE_PORTFOLIO and r.portfolio == t.portfolio
    ]
    common = [
        _row(r, "Common", stored.get(r.id), decisions)
        for r in rows
        if r.active and r.source == SOURCE_COMMON
    ]

    if launched:
        counts = stored_counts(list(stored.values()))
    else:
        counts = summarize_counts(planned_with_decisions(db, t, rows))
    counts_out = ScopeCountsOut(
        framework=counts["framework"],
        ai_applicable=counts["ai_applicable"],
        ai_excluded=counts["ai_excluded"],
        golden_set_applies=counts["golden_set_applies"],
        golden_set_to_confirm=counts["golden_set_to_confirm"],
        common=counts["common"],
        total=counts["total_applicable"],
    )

    pending = [r for r in (*golden, *common) if r.applies == TO_CONFIRM]
    recommendations: list[RecommendationOut] = []
    if pending:
        by_id = {r.id: r for r in rows}
        payload = [
            {
                "id": p.id,
                "title": p.requirement,
                "description": by_id[p.id].description or "",
                "lens": p.lens,
                "gate": p.gate,
                "type": p.type,
                "owner_hint": p.owner_hint,
            }
            for p in pending
        ]
        for rec in get_ai_service().recommend_applicability(
            payload, _flavour_context(db, t, focus_areas)
        ):
            recommendations.append(
                RecommendationOut(
                    item_id=rec["item_id"],
                    recommendation=rec["recommendation"],
                    reason=rec["reason"],
                )
            )

    return ScopeOut(
        transition_id=t.id,
        portfolio=t.portfolio,
        focus_areas=focus_areas,
        golden_set=golden,
        common=common,
        counts=counts_out,
        tier_banner=_tier_banner(db, t),
        recommendations=recommendations,
        launched=launched,
    )


def update_scope(db: Session, user: User, t: Transition, body: ScopeUpdateIn) -> None:
    """Persist decisions (caller commits and rebuilds the page)."""
    rows = {r.id: r for r in library_rows(db)}
    eligible = {
        r.id
        for r in rows.values()
        if r.active
        and (
            (r.source == SOURCE_PORTFOLIO and r.portfolio == t.portfolio)
            or r.source == SOURCE_COMMON
        )
    }
    unknown = sorted({d.item_id for d in body.decisions if d.item_id not in eligible})
    if unknown:
        raise BadRequest(
            "Validation failed",
            [f"{i} is not a golden-set or common item of this transition" for i in unknown],
        )
    if t.status == "Closed":
        raise Conflict("Transition is closed")
    locked = [
        f"{d.item_id} is mandatory and cannot be set to '{d.applies}'"
        for d in body.decisions
        if d.applies != _YES and is_locked(rows[d.item_id])
    ]
    if locked:
        raise Conflict("Locked rows cannot be changed", locked)

    launched = t.assessment_launched_at is not None
    tally = {"yes": 0, "no": 0, "to_confirm": 0}
    key = {_YES: "yes", _NO: "no", TO_CONFIRM: "to_confirm"}
    stored = {i.playbook_item_id: i for i in stored_items(db, t.id)} if launched else {}
    plan = {p.playbook_item_id: p for p in plan_transition(db, t, list(rows.values()))}
    new_decisions = dict(t.scope_decisions or {})
    for d in body.decisions:
        tally[key[d.applies]] += 1
        reason = (d.reason or "").strip() or None
        new_decisions[d.item_id] = {"applies": d.applies, "reason": reason}
        if not launched:
            continue
        item = stored.get(d.item_id)
        if item is None:
            planned = plan.get(d.item_id)
            if planned is None:
                continue
            item = _new_item(t.id, planned)
            db.add(item)
        lens = rows[d.item_id].lens
        if d.applies == _YES:
            item.applicability, item.na_reason = APPLIES, None
        elif d.applies == _NO:
            item.applicability, item.na_reason = NOT_APPLICABLE, reason
            item.status = na_status_for(lens)
        else:
            item.applicability, item.na_reason = TO_CONFIRM, None
        if d.applies != _NO and item.status in NA_STATUSES:
            item.status = NOT_STARTED
        item.excluded_by = None
        item.last_updated_by = user.id
        item.last_updated_source = ACTOR_HUMAN
    t.scope_decisions = new_decisions
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action="Scope decisions recorded",
        transition_id=t.id,
        after=tally,
        note=(
            "Accepted Orion recommendations"
            if body.source == "orion_recommendation"
            else f"{tally['yes']} yes, {tally['no']} no, {tally['to_confirm']} to confirm"
        ),
    )


def launch_assessment(db: Session, user: User, t: Transition) -> LaunchOut:
    """Create the TransitionItems (BR-010) and mark the assessment launched (caller commits)."""
    reasons: list[str] = []
    if t.assessment_launched_at is not None:
        reasons.append("Assessment already launched")
    if requires_tiering(db, t.project_type) and applied_tier(db, t) is None:
        reasons.append("Propose a tier before launching")
    if reasons:
        raise Conflict(reasons[0], reasons)

    rows = library_rows(db)
    decisions = _effective_decisions(t, rows)
    planned = apply_decisions(plan_transition(db, t, rows), decisions)
    for p in planned:
        reason = (decisions.get(p.playbook_item_id) or {}).get("reason")
        is_human_na = p.applicability == NOT_APPLICABLE and p.excluded_by is None
        db.add(_new_item(t.id, p, na_reason=reason if is_human_na else None))
    t.assessment_launched_at = clock.now()
    counts = summarize_counts(planned)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action="Assessment launched",
        transition_id=t.id,
        after={**counts, "items": len(planned)},
        note=f"{len(planned)} items created, {counts['total_applicable']} applicable",
    )
    return LaunchOut(
        transition_id=t.id,
        counts={**counts, "total": counts["total_applicable"]},
        redirect=f"/transitions/{t.id}/assessment",
    )
