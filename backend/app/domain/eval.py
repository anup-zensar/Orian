"""AI playbook eval metrics: table, manual results, mock import (spec 7.5, 8.7 j, FR-037).

Pass/fail of an ``auto`` metric is always computed by the machine check (``eval_passes``) from the
tier's target; manual metrics use the stored toggle. A failed metric is a Technical blocker at
SG4_ATD (the gate rules read ``EvalResult.passed``); metrics without a result are a warning only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_transition_role
from app.config import get_settings
from app.domain import audit, cfg
from app.domain.records import get_transition
from app.errors import BadRequest, Conflict
from app.models import EvalResult, EvalTarget, TierAssessment, Transition, User
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN
from app.schemas.eval import EvalResultIn, EvalRowOut, EvalTableOut
from app.seed.loader import eval_passes

BANNER = (
    "Targets currently identical for all tiers - tier-specific thresholds to be confirmed by the "
    "S&T team (editable in Admin)."
)
RESULT_FIELDS = ("value_number", "value_text", "passed", "source")
LOWEST_TIER_FALLBACK = 1


def has_eval_metrics(db: Session, transition: Transition) -> bool:
    """True when the transition's project type has the "Has eval metrics" switch on."""
    from app.domain.scope import has_eval_metrics as type_has_eval_metrics

    return type_has_eval_metrics(db, transition.project_type)


def ensure_ai(db: Session, transition: Transition) -> None:
    if not has_eval_metrics(db, transition):
        raise Conflict(
            "Eval metrics apply to AI flavours only",
            [
                f"{transition.id} is a {cfg.project_type_label(db, transition.project_type)} transition"
            ],
        )


def transition_tier(db: Session, transition: Transition) -> int | None:
    """Confirmed tier if confirmed, else the proposed tier, else None."""
    if transition.risk_tier is not None:
        return transition.risk_tier
    assessment = db.scalar(
        select(TierAssessment).where(TierAssessment.transition_id == transition.id)
    )
    if assessment is None:
        return None
    return (
        assessment.confirmed_tier
        if assessment.confirmed_tier is not None
        else assessment.proposed_tier
    )


def _targets(db: Session, tier: int | None) -> list[EvalTarget]:
    return list(
        db.scalars(
            select(EvalTarget)
            .where(
                EvalTarget.tier == (tier if tier is not None else LOWEST_TIER_FALLBACK),
                EvalTarget.active.isnot(False),  # the Admin can switch a metric off
            )
            .order_by(EvalTarget.sort_order, EvalTarget.metric_id)
        ).all()
    )


def _results(db: Session, transition_id: str) -> dict[str, EvalResult]:
    return {
        r.metric_id: r
        for r in db.scalars(select(EvalResult).where(EvalResult.transition_id == transition_id))
    }


def is_machine_checked(target: EvalTarget) -> bool:
    return target.evaluation == "auto" and target.operator is not None and target.value is not None


def pass_state(target: EvalTarget, result: EvalResult | None) -> bool | None:
    """THE pass/fail rule (BE#5), shared by the eval table and the readiness check.

    Evaluated against the target passed in (callers use the CURRENT tier's targets), never against the
    ``passed`` flag stored when the result was entered: machine-checked metrics compare the number with
    the target, manual metrics use the stored toggle. None = not evaluated."""
    if result is None:
        return None
    if is_machine_checked(target):
        if result.value_number is None:
            return None
        return eval_passes(target.operator, target.value, result.value_number)
    return result.passed


def targets_for_transition(db: Session, transition: Transition) -> list[EvalTarget]:
    """Eval targets of the transition's CURRENT tier (confirmed, else proposed)."""
    return _targets(db, transition_tier(db, transition))


def row_for(target: EvalTarget, result: EvalResult | None) -> EvalRowOut:
    """One table row with its computed status."""
    passed = pass_state(target, result)
    status = "not evaluated" if passed is None else ("pass" if passed else "fail")
    return EvalRowOut(
        metric_id=target.metric_id,
        metric=target.metric,
        target_text=target.target_text,
        operator=target.operator,
        value=target.value,
        unit=target.unit,
        evaluation=target.evaluation,  # type: ignore[arg-type]
        result_number=result.value_number if result else None,
        result_text=result.value_text if result else None,
        passed=passed,
        status=status,  # type: ignore[arg-type]
        evaluated_at=result.evaluated_at if result else None,
        source=result.source if result else None,
    )


def eval_table(db: Session, transition: Transition) -> EvalTableOut:
    tier = transition_tier(db, transition)
    targets = _targets(db, tier)
    results = _results(db, transition.id)
    rows = [row_for(t, results.get(t.metric_id)) for t in targets]
    return EvalTableOut(
        tier=tier,
        targets_confirmed=bool(targets) and all(t.confirmed for t in targets),
        banner="" if targets and all(t.confirmed for t in targets) else BANNER,
        rows=rows,
        failed_count=sum(1 for r in rows if r.status == "fail"),
        not_evaluated_count=sum(1 for r in rows if r.status == "not evaluated"),
    )


def get_eval_table(db: Session, transition_id: str) -> EvalTableOut:
    transition = get_transition(db, transition_id)
    ensure_ai(db, transition)
    return eval_table(db, transition)


# --- manual results -------------------------------------------------------------------------------
def _result_snapshot(result: EvalResult | None) -> dict[str, Any] | None:
    return audit.snapshot(result, RESULT_FIELDS) if result is not None else None


def put_results(
    db: Session, transition_id: str, body: list[EvalResultIn], user: User
) -> EvalTableOut:
    transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.EDIT_EVAL_RESULTS)
    ensure_ai(db, transition)
    tier = transition_tier(db, transition)
    targets = {t.metric_id: t for t in _targets(db, tier)}

    reasons: list[str] = []
    for entry in body:
        target = targets.get(entry.metric_id)
        if target is None:
            reasons.append(f"'{entry.metric_id}' is not an eval metric of this tier")
        elif is_machine_checked(target):
            if entry.value_number is None:
                reasons.append(f"{entry.metric_id} ({target.metric}) needs a numeric result")
        elif entry.passed is None and entry.value_number is None:
            reasons.append(f"{entry.metric_id} ({target.metric}) needs pass/fail or a value")
    if reasons:
        raise BadRequest("Invalid eval results", reasons)

    existing = _results(db, transition.id)
    now = clock.now()
    for entry in body:
        target = targets[entry.metric_id]
        result = existing.get(entry.metric_id)
        before = _result_snapshot(result)
        if is_machine_checked(target):
            passed: bool | None = eval_passes(target.operator, target.value, entry.value_number)  # type: ignore[arg-type]
        else:
            passed = entry.passed
        if result is None:
            result = EvalResult(transition_id=transition.id, metric_id=entry.metric_id)
            db.add(result)
            existing[entry.metric_id] = result
        result.value_number = entry.value_number
        result.value_text = entry.value_text
        result.passed = passed
        result.evaluated_at = now
        result.source = "Manual"
        db.flush()
        after = _result_snapshot(result)
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="EvalResult",
            entity_id=entry.metric_id,
            action="updated",
            transition_id=transition.id,
            before=before,
            after=after,
        )
    db.flush()
    return eval_table(db, transition)


# --- mock import ----------------------------------------------------------------------------------
def _seed_results(transition: Transition) -> dict[str, float] | None:
    """The flagship's eval results from ``sample_transitions.json`` (None for other transitions)."""
    if not transition.is_flagship:
        return None
    path = get_settings().seed_dir / "sample_transitions.json"
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    for src in data.get("transitions", []):
        if src.get("id") == transition.id and src.get("eval_results"):
            return {k: float(v) for k, v in src["eval_results"].items()}
    return None


def _fraction(transition_id: str, metric_id: str) -> float:
    """Deterministic number in [0, 1) from the transition and metric ids."""
    digest = hashlib.sha256(f"{transition_id}:{metric_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


def plausible_value(transition_id: str, target: EvalTarget) -> float:
    """A deterministic value that passes the target with a small margin."""
    f = _fraction(transition_id, target.metric_id)
    margin = 0.2 + 0.4 * f  # 20-60 % of the available headroom
    op, goal = target.operator, float(target.value or 0.0)
    percent = (target.unit or "") == "%"
    if op in (">=", ">"):
        headroom = goal + (100.0 - goal) * margin
        value = headroom if percent else goal * (1.0 + 0.02 + 0.08 * f)
    elif op in ("<=", "<"):
        value = goal * (1.0 - margin) if goal else 0.0
    elif op == "abs<=":
        value = goal * (0.2 + 0.4 * f) * (1 if f >= 0.5 else -1)
    else:  # ==
        value = goal
    value = round(value, 1)
    if eval_passes(op, goal, value) is not True:
        value = goal  # rounding must never turn a pass into a fail
        if eval_passes(op, goal, value) is not True:
            value = goal + 1.0 if op == ">" else goal - 1.0
    return value


def import_results(db: Session, transition_id: str, user: User) -> EvalTableOut:
    transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.EDIT_EVAL_RESULTS)
    ensure_ai(db, transition)
    tier = transition_tier(db, transition)
    targets = _targets(db, tier)
    by_id = {t.metric_id: t for t in targets}
    seed_values = _seed_results(transition)

    values: dict[str, tuple[float | None, str | None, bool | None]] = {}
    if seed_values is not None:
        for metric_id, number in seed_values.items():
            target = by_id.get(metric_id)
            if target is None:
                continue
            passed = (
                eval_passes(target.operator, target.value, number)
                if is_machine_checked(target)
                else None
            )
            values[metric_id] = (number, None, passed)
    else:
        for target in targets:
            if is_machine_checked(target):
                number = plausible_value(transition.id, target)
                values[target.metric_id] = (
                    number,
                    None,
                    eval_passes(target.operator, target.value, number),
                )
            else:
                values[target.metric_id] = (None, "Meets target (mock import)", True)

    existing = _results(db, transition.id)
    now = clock.now()
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for metric_id, (number, text, passed) in values.items():
        result = existing.get(metric_id)
        before[metric_id] = _result_snapshot(result)
        if result is None:
            result = EvalResult(transition_id=transition.id, metric_id=metric_id)
            db.add(result)
        result.value_number = number
        result.value_text = text
        result.passed = passed
        result.evaluated_at = now
        result.source = "Imported (mock)"
        after[metric_id] = {
            "value_number": number,
            "value_text": text,
            "passed": passed,
            "source": "Imported (mock)",
        }
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="EvalResult",
        entity_id=transition.id,
        action="imported",
        transition_id=transition.id,
        before=before,
        after=after,
        note=f"Imported {len(values)} eval results (mock data) for tier "
        f"{tier if tier is not None else '-'}",
    )
    return eval_table(db, transition)
