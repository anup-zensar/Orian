"""Demo controls (spec 8.16, 11.2, 13 step 9; DEMO_MODE only). M9."""

from __future__ import annotations

import re
import shutil
import time
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.config import get_settings
from app.domain import audit
from app.errors import BadRequest, NotFound
from app.models import (
    AppSetting,
    EvalResult,
    ExceptionRecord,
    Transition,
    TransitionItem,
    User,
)
from app.rules.constants import (
    ACTOR_HUMAN,
    ACTOR_SYSTEM,
    APPLIES,
    GATE_ORDER,
    done_status_for,
    is_open_status,
)
from app.schemas.admin import DemoResetOut, FastForwardOut, TodayOut

SKIP_MODULES = ("OCET", "SUPPORT_MODEL")
ITEM_FIELDS = ("status", "gap_severity", "design_effectiveness", "na_reason")


def _clear_storage() -> None:
    """Remove stale uploads / generated files (per-transition folders TR-nnnn only)."""
    root = get_settings().storage_dir
    if not root.is_dir():
        return
    for child in root.iterdir():
        if child.is_dir() and re.fullmatch(r"TR-\d{4,}", child.name):
            shutil.rmtree(child, ignore_errors=True)


def reset_demo() -> DemoResetOut:
    """Re-seed everything (NFR-06) and report elapsed seconds plus counts."""
    from app import db as database
    from app.seed.loader import reset_and_seed

    started = time.perf_counter()
    _clear_storage()
    reset_and_seed()
    elapsed = time.perf_counter() - started
    with database.SessionLocal() as session:
        transitions = session.scalar(select(func.count()).select_from(Transition)) or 0
        items = session.scalar(select(func.count()).select_from(TransitionItem)) or 0
    return DemoResetOut(seconds=round(elapsed, 2), transitions=transitions, items=items)


def get_today(db: Session) -> TodayOut:
    """Current demo today, the active override and SEED_DATE."""
    return TodayOut(
        today=clock.today(),
        override=clock.get_today_override(),
        seed_date=get_settings().seed_date,
    )


def set_today(db: Session, value: date | None, user: User | None = None) -> TodayOut:
    """Persist AppSetting "today_override", apply in-process and audit."""
    if value is not None and not date(2000, 1, 1) <= value <= date(2100, 12, 31):
        raise BadRequest("Invalid date", ["The demo date must be between 2000 and 2100"])
    row = db.get(AppSetting, "today_override")
    before = row.value if row is not None else None
    new_value = value.isoformat() if value else None
    if row is None:
        db.add(AppSetting(key="today_override", value=new_value))
    else:
        row.value = new_value
    clock.set_today_override(value)
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="AppSetting",
        entity_id="today_override",
        action="updated",
        before={"value": before},
        after={"value": new_value},
        note="Demo today set" if value else "Demo today override cleared",
    )
    db.flush()
    return get_today(db)


def _passing_evals(db: Session, transition: Transition) -> int:
    """Re-import eval results so every metric of the tier passes. Returns metrics written."""
    from app.domain import eval as ev

    if transition.project_type not in ev.AI_PROJECT_TYPES:
        return 0
    targets = ev._targets(db, ev.transition_tier(db, transition))
    existing = ev._results(db, transition.id)
    now = clock.now()
    for target in targets:
        result = existing.get(target.metric_id)
        if result is None:
            result = EvalResult(transition_id=transition.id, metric_id=target.metric_id)
            db.add(result)
        if ev.is_machine_checked(target):
            result.value_number = ev.plausible_value(transition.id, target)
            result.value_text = None
        else:
            result.value_number = None
            result.value_text = "Meets target (demo fast-forward)"
        result.passed = True
        result.evaluated_at = now
        result.source = "Imported (mock)"
    db.flush()
    return len(targets)


def fast_forward(db: Session, transition_id: str, user: User) -> FastForwardOut:
    """Complete open items due at or before the current gate (except OCET/support-model-linked and
    excepted items) and re-import passing eval results."""
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    gate_no = GATE_ORDER[transition.current_gate]
    excepted = set(
        db.scalars(
            select(ExceptionRecord.transition_item_id).where(
                ExceptionRecord.transition_id == transition.id,
                ExceptionRecord.transition_item_id.is_not(None),
            )
        ).all()
    )
    items = db.scalars(
        select(TransitionItem)
        .where(TransitionItem.transition_id == transition.id)
        .order_by(TransitionItem.id)
    ).all()
    completed = skipped_linked = skipped_exception = 0
    for item in items:
        if (
            item.applicability != APPLIES
            or not is_open_status(item.status)
            or GATE_ORDER.get(item.due_gate, 99) > gate_no
        ):
            continue
        if item.linked_module in SKIP_MODULES:
            skipped_linked += 1
            continue
        if item.id in excepted:
            skipped_exception += 1
            continue
        lens = item.playbook_item.lens
        before = audit.snapshot(item, ITEM_FIELDS)
        item.status = done_status_for(lens)
        item.gap_severity = None
        item.na_reason = None
        if lens == "Compliance":
            item.design_effectiveness = "Yes"
        item.last_updated_by = None
        item.last_updated_source = "System"
        audit.record(
            db,
            actor=None,
            actor_type=ACTOR_SYSTEM,
            entity="TransitionItem",
            entity_id=item.id,
            action="updated",
            transition_id=transition.id,
            before=before,
            after=audit.snapshot(item, ITEM_FIELDS),
            note=f"Demo fast-forward - {item.playbook_item_id}",
        )
        completed += 1
    evals = _passing_evals(db, transition)
    audit.record(
        db,
        actor=None,
        actor_type=ACTOR_SYSTEM,
        entity="Transition",
        entity_id=transition.id,
        action="fast_forward",
        transition_id=transition.id,
        after={
            "items_completed": completed,
            "skipped_linked": skipped_linked,
            "skipped_exception": skipped_exception,
            "evals_passing": evals,
            "requested_by": user.id,
        },
        note="Demo fast-forward",
    )
    db.flush()
    verdict: str | None = None
    try:
        from app.domain.readiness_check import compute_readiness_check

        verdict = compute_readiness_check(db, transition, transition.current_gate, user).verdict
    except Exception:  # noqa: BLE001 - the verdict text is informational only
        verdict = None
    # Storyline step 9: once the items are done, rule R4 drafts "Ready for AtD" in the OR focal's
    # queue (To = OLM, Cc = OR focal; a draft only, nothing is sent).
    # Other rules are left to the scheduler / Run engine now.
    r4_drafts = 0
    try:
        from app.domain.reminders import run_reminders

        run = run_reminders(
            db, user=None, rules=["R4"], transition_id=transition.id, triggered_by="fast-forward"
        )
        r4_drafts = run.created.get("R4", 0)
    except Exception:  # noqa: BLE001 - the demo helper must not fail because of the reminder engine
        r4_drafts = 0
    return FastForwardOut(
        r4_drafts=r4_drafts,
        transition_id=transition.id,
        items_completed=completed,
        skipped_linked=skipped_linked,
        skipped_exception=skipped_exception,
        evals_passing=evals,
        readiness=verdict,
    )
