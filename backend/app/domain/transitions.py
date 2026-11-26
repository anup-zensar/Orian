"""Transition register: filtering and involvement (FR-012, spec §8.2; A-50, A-51)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.metrics import TransitionMetrics, compute_metrics
from app.models import Transition, User
from app.schemas.transitions import TransitionFilters

# Role -> the Transition column that makes a user "involved" (A-51). Planner, Leadership and Admin are
# not tied to one transition: for them "mine" means every transition.
INVOLVEMENT_COLUMN: dict[str, str] = {
    "OR_FOCAL": "or_focal_user_id",
    "PM": "pm_user_id",
    "ARCHITECT": "architect_user_id",
    "OLM": "olm_user_id",
    "IRM": "irm_user_id",
}


def is_involved(user: User, transition: Transition) -> bool:
    column = INVOLVEMENT_COLUMN.get(user.role)
    if column is None:
        return True
    return getattr(transition, column) == user.id


def _matches_static(t: Transition, f: TransitionFilters, user: User) -> bool:
    """Filters that need only the transition row (exact match, AND)."""
    if f.portfolio is not None and t.portfolio != f.portfolio:
        return False
    if f.region is not None and t.region != f.region:
        return False
    if f.gate is not None and t.current_gate != f.gate:
        return False
    if f.type is not None and t.project_type != f.type:
        return False
    if f.status is not None and t.status != f.status:
        return False
    return not f.mine or is_involved(user, t)


def _matches_custom(t: Transition, custom: dict[str, str]) -> bool:
    """Custom-field filters (``?cf_<key>=value``, AND): the stored value must equal ``value``; a list
    value (multiselect) must contain it."""
    stored = t.custom_fields or {}
    for key, wanted in custom.items():
        # Admin keys may or may not carry the "cf_" prefix (project_status vs cf_urgent); URL param = cf_ + key.
        value = stored.get(key, stored.get(key.removeprefix("cf_")))
        if isinstance(value, list):
            if wanted not in [str(v) for v in value]:
                return False
        elif isinstance(value, bool):
            if str(value).lower() != wanted.lower():
                return False
        elif value is None or str(value) != wanted:
            return False
    return True


def _matches_computed(m: TransitionMetrics, f: TransitionFilters) -> bool:
    """Filters on computed values (RAG, days, gaps, readiness) and the free-text search."""
    t = m.transition
    if f.rag is not None and m.rag != f.rag:
        return False
    if f.q:
        needle = f.q.strip().lower()
        haystack = (t.id, t.name, t.market, t.servicenow_project_id, m.or_focal.name)
        if needle and not any(needle in (text or "").lower() for text in haystack):
            return False
    if f.decision_within_days is not None:
        # Overdue decisions (negative days) are INCLUDED: they are the most urgent (A-50).
        days = m.days_to_next_decision
        if days is None or days > f.decision_within_days:
            return False
    if f.has_critical is not None and (m.critical_gaps > 0) != f.has_critical:
        return False
    # A transition without a launched assessment has no readiness: never "below N %" (A-34).
    return f.compliance_below is None or (
        m.launched and m.lens_pct["Compliance"] < f.compliance_below
    )


def sort_register(rows: list[TransitionMetrics]) -> list[TransitionMetrics]:
    """Soonest decision first, transitions without a date last, then by name."""
    return sorted(
        rows,
        key=lambda m: (
            m.days_to_next_decision is None,
            m.days_to_next_decision if m.days_to_next_decision is not None else 0,
            m.transition.name.lower(),
        ),
    )


def filter_metrics(
    rows: list[TransitionMetrics], user: User, filters: TransitionFilters
) -> list[TransitionMetrics]:
    """Apply ``filters`` (AND) to already computed metrics, in register order (no queries)."""
    return sort_register(
        [
            m
            for m in rows
            if _matches_static(m.transition, filters, user) and _matches_computed(m, filters)
        ]
    )


def filter_transitions(
    db: Session,
    user: User,
    filters: TransitionFilters,
    custom: dict[str, str] | None = None,
) -> list[TransitionMetrics]:
    """Metrics of every transition matching ``filters`` (AND), in register order. ``custom`` holds the
    ``cf_<key>`` filters of the Admin's custom fields.

    The Active/Closed filter runs in SQL; other cheap row filters run before metrics are computed
    so metrics are only computed for the survivors.
    """
    query = select(Transition)
    if filters.status is not None:
        query = query.where(Transition.status == filters.status)
    candidates = [
        t
        for t in db.scalars(query).all()
        if _matches_static(t, filters, user) and _matches_custom(t, custom or {})
    ]
    metrics = compute_metrics(db, candidates)
    return sort_register([m for m in metrics if _matches_computed(m, filters)])


def my_transitions(db: Session, user: User, *, active_only: bool = True) -> list[TransitionMetrics]:
    """The "mine" involvement set used by the dashboard and insights (Active only by default)."""
    filters = TransitionFilters(mine=True, status="Active" if active_only else None)
    return filter_transitions(db, user, filters)
