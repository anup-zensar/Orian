"""Admin configuration + demo controls (FR-100). M9.

All endpoints require Perm.ADMIN (spec 3.3); /admin/demo/* also require DEMO_MODE=true (404
otherwise). Every write is audited (actor Human). Notice for the UI: "Changes affect new
transitions; existing transitions keep their items."
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require, require_demo_mode
from app.domain import cfg
from app.models import User
from app.permissions import Perm
from app.schemas.admin import (
    ApprovalCancelIn,
    ApprovalCancelOut,
    ApprovalChainsIn,
    ApprovalChainsOut,
    DemoResetOut,
    EvalTargetsIn,
    EvalTargetsOut,
    FastForwardIn,
    FastForwardOut,
    FlavourRulesIn,
    FlavourRulesOut,
    GoldenSetIn,
    GoldenSetOut,
    PlaybookItemAdminOut,
    PlaybookItemUpdateIn,
    ReminderRuleOut,
    ReminderRulesIn,
    TodayIn,
    TodayOut,
)
from app.schemas.common import ErrorOut

router = APIRouter(tags=["admin"], dependencies=[Depends(get_current_user)])

_E = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 422: {"model": ErrorOut}}
_DEMO = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}}


@router.get(
    "/admin/playbook-items",
    response_model=list[PlaybookItemAdminOut],
    responses=_E,
)
def list_playbook_items(
    source: str | None = Query(default=None, description="FRAMEWORK|AI_PLAYBOOK|PORTFOLIO|COMMON"),
    q: str | None = Query(default=None, description="Search id/title/description"),
    gate: str | None = None,
    lens: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> list[PlaybookItemAdminOut]:
    """Playbook library (spec 8.16). ADMIN only (403). All filters optional and combinable;
    ordered by id. Includes inactive items unless ``active`` is given. 422 on an invalid
    ``source``."""
    from app.domain import admin as domain

    return domain.list_playbook_items(db, source=source, q=q, gate=gate, lens=lens, active=active)


@router.get(
    "/admin/playbook-items/{item_id}",
    response_model=PlaybookItemAdminOut,
    responses=_E,
)
def get_playbook_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> PlaybookItemAdminOut:
    """One playbook item. 403 non-admin; 404 unknown id."""
    from app.domain import admin as domain

    return domain.get_playbook_item(db, item_id)


@router.put(
    "/admin/playbook-items/{item_id}",
    response_model=PlaybookItemAdminOut,
    responses=_E,
)
def update_playbook_item(
    item_id: str,
    body: PlaybookItemUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> PlaybookItemAdminOut:
    """Edit title, description, gate, lens, applicable_tiers, mandatory, active. A lens change
    clears ``lens_is_suggested`` (badge "lens suggested - confirm" disappears). Existing
    transitions keep their items. Audited (PlaybookItem, Human). 403; 404 unknown id; 422 unknown
    gate code, lens, or tier outside 1..4."""
    from app.domain import admin as domain

    result = domain.update_playbook_item(db, item_id, body, user)
    db.commit()
    return result


@router.get("/admin/flavour-rules", response_model=FlavourRulesOut, responses=_E)
def get_flavour_rules(
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> FlavourRulesOut:
    """Project type -> checklists + requires_tiering + note. 403 non-admin."""
    from app.domain import admin as domain

    return domain.get_flavour_rules(db)


@router.put("/admin/flavour-rules", response_model=FlavourRulesOut, responses=_E)
def put_flavour_rules(
    body: FlavourRulesIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> FlavourRulesOut:
    """Update the listed rules (project types are not created or deleted). Audited (FlavourRule).
    403; 422 unknown project_type or checklist source."""
    from app.domain import admin as domain

    result = domain.put_flavour_rules(db, body, user)
    db.commit()
    cfg.invalidate()
    return result


@router.get("/admin/portfolios/{name}/golden-set", response_model=GoldenSetOut, responses=_E)
def get_golden_set(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> GoldenSetOut:
    """Portfolio golden set (PORTFOLIO-source items) incl. deactivated rows. 403; 404 unknown
    portfolio."""
    from app.domain import admin as domain

    return domain.get_golden_set(db, name)


@router.put("/admin/portfolios/{name}/golden-set", response_model=GoldenSetOut, responses=_E)
def put_golden_set(
    name: str,
    body: GoldenSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> GoldenSetOut:
    """Replace the list: items without id are created as "<CODE>-NN"; items with an existing id are
    edited; existing items omitted are deactivated (active=false), never deleted (transitions may
    use them). Audited (PlaybookItem). 403; 404 unknown portfolio; 422 unknown gate/lens, or an id
    that is not in this portfolio."""
    from app.domain import admin as domain

    result = domain.put_golden_set(db, name, body, user)
    db.commit()
    cfg.invalidate()
    return result


@router.get("/admin/eval-targets", response_model=EvalTargetsOut, responses=_E)
def get_eval_targets(
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> EvalTargetsOut:
    """Grid metric x Tier 1-4 with parsed operator/value/unit and the "targets confirmed" flag.
    403 non-admin."""
    from app.domain import admin as domain

    return domain.get_eval_targets(db)


@router.put("/admin/eval-targets", response_model=EvalTargetsOut, responses=_E)
def put_eval_targets(
    body: EvalTargetsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> EvalTargetsOut:
    """Update targets and the confirmed flag. Audited (EvalTarget). 403; 422 unknown metric_id,
    tier outside 1..4, or a value without an operator."""
    from app.domain import admin as domain

    result = domain.put_eval_targets(db, body, user)
    db.commit()
    return result


@router.get("/admin/approval-chains", response_model=ApprovalChainsOut, responses=_E)
def get_approval_chains(
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> ApprovalChainsOut:
    """Steps (with their labels and mock flag) and the display name per approval type (OCET, AtD, AtO,
    SUPPORT_MODEL, EXCEPTION) plus the allowed roles (roles that can approve + CISO_BISO). 403
    non-admin."""
    from app.domain import admin as domain

    return domain.get_approval_chains(db)


@router.put("/admin/approval-chains", response_model=ApprovalChainsOut, responses=_E)
def put_approval_chains(
    body: ApprovalChainsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> ApprovalChainsOut:
    """Replace steps for the listed chain types (at least one step, numbered 1..n, role from the
    allowed list). New requests use the new chain; existing requests keep theirs. Audited
    (ApprovalChainConfig). 403; 422 invalid role / empty chain / bad numbering."""
    from app.domain import admin as domain

    result = domain.put_approval_chains(db, body, user)
    db.commit()
    return result


@router.post(
    "/admin/approvals/{request_id}/cancel",
    response_model=ApprovalCancelOut,
    responses={**_E, 409: {"model": ErrorOut}},
)
def cancel_approval(
    request_id: str,
    body: ApprovalCancelIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> ApprovalCancelOut:
    """Cancel a stuck Pending approval request (reason required, audited). ADMIN only (403);
    404 unknown request; 409 when already decided or cancelled. Admin has no other workflow
    override: decisions stay with the chain approvers."""
    from app.domain import admin as domain

    result = domain.cancel_approval_request(db, request_id, body, user)
    db.commit()
    return result


@router.get("/admin/reminder-rules", response_model=list[ReminderRuleOut], responses=_E)
def list_reminder_rules(
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> list[ReminderRuleOut]:
    """Reminder rules R1-R7 with thresholds (params), enabled and autonomous_eligible flags."""
    from app.domain import admin as domain

    return domain.list_reminder_rules(db)


@router.put("/admin/reminder-rules", response_model=list[ReminderRuleOut], responses=_E)
def put_reminder_rules(
    body: ReminderRulesIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> list[ReminderRuleOut]:
    """Update enabled + params per rule (R6 also item_ids / category) and switch autonomous_eligible
    OFF (never on). Name and description are read-only. Audited (ReminderRule). 403; 422 unknown
    rule id, unknown param key, non-positive threshold, or autonomy switched on."""
    from app.domain import admin as domain

    result = domain.put_reminder_rules(db, body, user)
    db.commit()
    return result


@router.post(
    "/admin/demo/reset",
    response_model=DemoResetOut,
    dependencies=[Depends(require_demo_mode)],
    responses=_DEMO,
)
def demo_reset(user: User = Depends(require(Perm.ADMIN))) -> DemoResetOut:
    """Re-seed all demo data (< 10 s, NFR-06) and clear the today override. 403 non-admin; 404
    when DEMO_MODE=false. Returns elapsed seconds and counts. The client must re-fetch everything.
    """
    from app.domain import demo

    return demo.reset_demo()


@router.post(
    "/admin/demo/fast-forward",
    response_model=FastForwardOut,
    dependencies=[Depends(require_demo_mode)],
    responses=_DEMO,
)
def demo_fast_forward(
    body: FastForwardIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> FastForwardOut:
    """Fast-forward the flagship (spec 8.16, 13 step 9): complete every open item due at or before
    the current gate except OCET/support-model-linked items and items under an exception, and
    re-import eval results with all metrics passing. Audit actor "System", note "Demo
    fast-forward". 403; 404 unknown transition or DEMO_MODE=false."""
    from app.domain import demo

    result = demo.fast_forward(db, body.transition_id, user)
    db.commit()
    return result


@router.get(
    "/admin/demo/today",
    response_model=TodayOut,
    dependencies=[Depends(require_demo_mode)],
    responses=_DEMO,
)
def demo_get_today(
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> TodayOut:
    """Current demo "today" with the active override and SEED_DATE. 403; 404 DEMO_MODE=false."""
    from app.domain import demo

    return demo.get_today(db)


@router.post(
    "/admin/demo/today",
    response_model=TodayOut,
    dependencies=[Depends(require_demo_mode)],
    responses=_E,
)
def demo_set_today(
    body: TodayIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.ADMIN)),
) -> TodayOut:
    """Set (date) or clear (null) the demo "today" override; persisted in AppSetting
    "today_override" and applied in-process. Audited. 403; 404 DEMO_MODE=false; 422 bad date."""
    from app.domain import demo

    result = demo.set_today(db, body.date, user)
    db.commit()
    return result
