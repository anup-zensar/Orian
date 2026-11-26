"""AI playbook tab: eval targets/results, import eval results (mock) (FR-037). M4."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.eval import EvalResultIn, EvalTableOut

router = APIRouter(tags=["ai-playbook"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/eval-metrics", response_model=EvalTableOut)
def get_eval_metrics(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvalTableOut:
    """Eval metrics table for the transition's tier (spec 7.5, 8.7 j).

    * 404 unknown transition. 409 when the project type has no eval metrics (its "Has eval metrics"
      switch is off; Agentic AI has it on): "Eval metrics apply to AI flavours only".
    * Tier = confirmed tier if confirmed, else the proposed tier, else ``null`` (then the lowest tier's
      targets are shown and ``tier`` is null). Rows = EvalTarget for that tier ordered by sort_order, joined
      with the EvalResult of the transition.
    * ``status``: "not evaluated" when no result; for ``evaluation == "auto"`` pass/fail is computed from
      ``operator`` / ``value`` vs ``result_number`` (abs<= means absolute value <= value); for manual
      metrics from the stored ``passed`` toggle.
    * ``banner`` = "Targets currently identical for all tiers - tier-specific thresholds to be confirmed
      by the S&T team (editable in Admin)." while ``targets_confirmed`` is false, else "".
    * ``failed_count`` counts fail rows (Technical blockers at SG4_ATD), ``not_evaluated_count`` the rest
      (warning only).
    """
    from app.domain import eval as eval_domain

    return eval_domain.get_eval_table(db, transition_id)


@router.put("/transitions/{transition_id}/eval-results", response_model=EvalTableOut)
def put_eval_results(
    transition_id: str,
    body: Annotated[list[EvalResultIn], Body(max_length=200)],
    user: User = Depends(require(Perm.EDIT_EVAL_RESULTS)),
    db: Session = Depends(get_db),
) -> EvalTableOut:
    """Upsert results for the listed metrics (spec 8.7 j). Source "Manual", ``evaluated_at`` =
    clock.now().

    * 403 without ``Perm.EDIT_EVAL_RESULTS`` (OR focal, PM, Architect); 404 unknown transition.
    * 409 for non-AI flavours.
    * 422: ``metric_id`` not an EvalTarget; auto metric without ``value_number``; manual metric with
      neither ``passed`` nor a value.
    * Auto metrics: ``passed`` is computed server-side and any client ``passed`` is ignored. One AuditEvent
      per changed metric (entity "EvalResult", entity_id metric id, action "updated", before/after, Human).
    Returns the refreshed table (same as GET).
    """
    from app.domain import eval as eval_domain

    result = eval_domain.put_results(db, transition_id, body, user)
    db.commit()
    return result


@router.post("/transitions/{transition_id}/eval-results/import", response_model=EvalTableOut)
def import_eval_results(
    transition_id: str,
    user: User = Depends(require(Perm.EDIT_EVAL_RESULTS)),
    db: Session = Depends(get_db),
) -> EvalTableOut:
    """ "Import eval results (mock)" (spec 8.7 j). Overwrites results for every metric of the tier with
    source "Imported (mock)", ``evaluated_at`` = clock.now().

    * Flagship transition: values from ``sample_transitions.json`` ``eval_results`` (e.g. hallucination
      rate 3.1 vs <= 2 target, which fails). Others: deterministic plausible values (seeded by
      transition id and metric id) that pass auto targets with a small margin.
    * 403 without ``Perm.EDIT_EVAL_RESULTS``; 404 unknown transition; 409 for non-AI flavours.
    * AuditEvent (entity "EvalResult", entity_id transition id, action "imported", Human; the import is
      triggered by a person, the data is mock). Returns the refreshed table.
    """
    from app.domain import eval as eval_domain

    result = eval_domain.import_results(db, transition_id, user)
    db.commit()
    return result
