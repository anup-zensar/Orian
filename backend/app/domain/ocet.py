"""OCET domain operations (FR-060, BR-070). Implemented in M6.

Importing this module registers ``on_ocet_chain_completed`` with
``app.domain.approvals.register_completion_hook("OCET", ...)`` and an OCET Adaptive Card data
provider with ``approvals.register_card_data``. app.main (integration) must import
``app.domain.ocet`` so the hook is active. No function here commits; routers commit.

Status flow: Draft -> (Inputs pending) -> Submitted -> Planner approved -> Approved | Rejected.
"Planner approved" is derived while the request is Pending and its step 1 is Approved (set on
read in ``build_version_out``); the completion hook maps final Approved / Rejected.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import access, clock
from app.domain import approvals, audit, cfg, drafts
from app.domain.html_sanitize import escape_text
from app.errors import BadRequest, Conflict, NotFound
from app.models import (
    ApprovalRequest,
    OcetEstimate,
    OcetLine,
    OcetVersion,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import Perm
from app.rules import ocet as rules
from app.rules.constants import done_status_for, is_open_status
from app.schemas.common import PersonRef
from app.schemas.ocet import (
    CategoryTotalOut,
    CompareRowOut,
    CompareVersionRef,
    OcetApprovalOut,
    OcetApprovalStepOut,
    OcetCompareOut,
    OcetCurrentVersionOut,
    OcetEstimateOut,
    OcetLineIn,
    OcetLineOut,
    OcetOut,
    OcetSaveIn,
    OcetVersionOut,
    VarianceOut,
    VarianceRowOut,
    YearAmount,
)
from app.services.factory import get_ai_service

LINKED_MODULE = "OCET"  # checklist items with this linked_module complete when the OCET is approved
EDITABLE_STATUSES: tuple[str, ...] = ("Draft", "Inputs pending")


# --------------------------------------------------------------------------- helpers


def _reference_ocet(db: Session) -> dict[str, Any]:
    """The OCET dropdowns as configured under Forms & dropdowns: categories (with their default
    growth %), pricing bases, currencies, and the default horizon in years."""
    return {
        "categories": cfg.option_values(db, "ocet_categories"),
        "pricing_basis": cfg.option_values(db, "ocet_pricing_basis"),
        "currencies": cfg.option_values(db, "ocet_currencies"),
        "default_horizon_years": cfg.thresholds(db)["default_horizon_years"],
        "default_growth_pct": {
            o.value: o.meta.get("default_growth_pct", cfg.thresholds(db)["default_growth_pct"])
            for o in cfg.options(db, "ocet_categories")
        },
    }


def _person(db: Session, user_id: str | None) -> PersonRef | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    return PersonRef(id=user.id, name=user.name) if user else None


def _inputs(lines: list[OcetLine]) -> list[rules.OcetLineInput]:
    return [
        rules.OcetLineInput(
            line_key=ln.line_key,
            category=ln.category,
            base_amount=ln.base_amount,
            growth_pct=ln.growth_pct or 0.0,
            year_overrides=dict(ln.year_overrides or {}),
            description=ln.description or "",
        )
        for ln in lines
    ]


def _project(version: OcetVersion) -> rules.Projection:
    est = version.estimate
    return rules.project_version(_inputs(list(version.lines)), est.start_year, est.horizon_years)


def _previous_version(version: OcetVersion) -> OcetVersion | None:
    return next((v for v in version.estimate.versions if v.version == version.version - 1), None)


def _label(line: Any) -> str:
    text = (getattr(line, "description", "") or "").strip()
    return text or getattr(line, "category", "") or getattr(line, "line_key", "")


def effective_status(db: Session, version: OcetVersion) -> str:
    """Stored status, with "Planner approved" derived from the running chain (step 1 approved)."""
    if version.status == "Submitted" and version.approval_request_id:
        request = db.get(ApprovalRequest, version.approval_request_id)
        if request is not None and request.status == "Pending":
            first = min(request.steps, key=lambda s: s.step, default=None)
            if first is not None and first.status == "Approved" and first.role == "PLANNER":
                return "Planner approved"
    return version.status


def get_version(db: Session, version_id: int) -> OcetVersion:
    version = db.get(OcetVersion, version_id)
    if version is None:
        raise NotFound(f"OCET version {version_id} not found")
    return version


def _transition(db: Session, transition_id: str) -> Transition:
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


def _estimate(db: Session, transition_id: str) -> OcetEstimate:
    _transition(db, transition_id)
    estimate = db.scalars(
        select(OcetEstimate).where(OcetEstimate.transition_id == transition_id)
    ).first()
    if estimate is None:
        raise NotFound(f"Transition {transition_id} has no OCET yet")
    return estimate


def _yearly(amounts: dict[int, float]) -> list[YearAmount]:
    return [YearAmount(year=y, amount=a) for y, a in amounts.items()]


def _variance_rows(rows: list[rules.VarianceRow]) -> list[VarianceRowOut]:
    return [
        VarianceRowOut(
            key=r.key,
            category=r.category,
            description=r.description,
            previous_total=r.previous_total,
            current_total=r.current_total,
            abs_change=r.abs_change,
            pct_change=r.pct_change,
            status=r.status,  # type: ignore[arg-type]
        )
        for r in rows
    ]


def _missing_reasons(version: OcetVersion) -> list[str]:
    return [f"{_label(ln)}: base amount missing" for ln in version.lines if ln.base_amount is None]


def _variance_of(version: OcetVersion, proj: rules.Projection) -> rules.Variance:
    previous = _previous_version(version)
    return rules.variance(_project(previous) if previous else None, proj)


def _subject_label(version: OcetVersion, proj: rules.Projection, var: rules.Variance) -> str:
    est = version.estimate
    text = (
        f"OCET v{version.version} · {est.horizon_years}-year total "
        f"{rules.format_total_label(proj.total)} {est.currency}"
    )
    if _previous_version(version) is not None and var.total_pct is not None:
        text += f" ({var.total_pct:+.1f}% vs v{version.version - 1})"
    return text


def _diff_for_ai(
    version: OcetVersion, proj: rules.Projection, var: rules.Variance
) -> dict[str, Any]:
    by_key = {ln.line_key: ln for ln in version.lines}
    by_line = []
    for row in var.by_line:
        line = by_key.get(row.key)
        by_line.append(
            {
                "line_key": row.key,
                "category": row.category,
                "description": row.description,
                "abs_change": row.abs_change,
                "status": row.status,
                "growth_pct": line.growth_pct if line else 0.0,
                "year_overrides": dict(line.year_overrides or {}) if line else {},
                "override_reason": line.override_reason if line else None,
            }
        )
    previous = _previous_version(version)
    return {
        "version": version.version,
        "previous_version": previous.version if previous else None,
        "currency": version.estimate.currency,
        "total": proj.total,
        "total_abs": var.total_abs,
        "total_pct": var.total_pct,
        "by_category": [
            {
                "category": r.key,
                "abs_change": r.abs_change,
                "pct_change": r.pct_change,
                "current_total": r.current_total,
            }
            for r in var.by_category
        ],
        "by_line": by_line,
        "inputs_pending": proj.inputs_pending,
        "missing_lines": [_label(ln) for ln in version.lines if ln.base_amount is None],
    }


# --------------------------------------------------------------------------- views


def _version_out(db: Session, version: OcetVersion) -> OcetVersionOut:
    return OcetVersionOut(
        id=version.id,
        version=version.version,
        status=effective_status(db, version),  # type: ignore[arg-type]
        note=version.note or "",
        created_by=_person(db, version.created_by),
        created_at=version.created_at,
        submitted_at=version.submitted_at,
        approval_request_id=version.approval_request_id,
        total=_project(version).total,
    )


def _approval_out(db: Session, version: OcetVersion) -> OcetApprovalOut | None:
    if not version.approval_request_id:
        return None
    request = db.get(ApprovalRequest, version.approval_request_id)
    if request is None:
        return None
    steps = [
        OcetApprovalStepOut(
            step=s.step,
            role=s.role,
            label=s.label,
            approver=_person(db, s.approver_user_id),
            status=s.status,  # type: ignore[arg-type]
        )
        for s in sorted(request.steps, key=lambda s: s.step)
    ]
    return OcetApprovalOut(
        request_id=request.id,
        status=request.status,  # type: ignore[arg-type]
        steps=steps,
    )


def build_version_out(db: Session, version: OcetVersion, user: User) -> OcetOut:
    """Same as get_ocet_view but for an arbitrary version (used after mutations)."""
    est = version.estimate
    ref = _reference_ocet(db)
    proj = _project(version)
    var = _variance_of(version, proj)
    previous = _previous_version(version)
    status = effective_status(db, version)
    now = clock.now()

    trn = _transition(db, est.transition_id)
    editable = status in EDITABLE_STATUSES
    denied: str | None = access.transition_denial(db, user, trn, Perm.EDIT_OCET)
    if denied is None and trn.status == "Closed":
        denied = f"{est.transition_id} is closed - records can no longer be added or changed"
    if denied is None and not editable:
        denied = f"v{version.version} is {status} - create a new version to change it"
    can_edit = denied is None
    submit_reasons: list[str] = []
    if not can_edit:
        submit_reasons = [denied] if denied else []
    else:
        if not version.lines:
            submit_reasons.append("Add at least one cost line before submitting")
        submit_reasons.extend(_missing_reasons(version))
    can_submit = can_edit and status == "Draft" and not submit_reasons

    lines_out: list[OcetLineOut] = []
    for line, lp in zip(version.lines, proj.lines, strict=True):
        days = 0
        if line.input_status == "Requested" and line.input_requested_at:
            days = max((now - line.input_requested_at).days, 0)
        lines_out.append(
            OcetLineOut(
                id=line.id,
                line_key=line.line_key,
                category=line.category,
                description=line.description or "",
                vendor=line.vendor or "",
                pricing_basis=line.pricing_basis,
                base_amount=line.base_amount,
                growth_pct=line.growth_pct or 0.0,
                year_overrides={int(k): float(v) for k, v in (line.year_overrides or {}).items()},
                override_reason=line.override_reason,
                input_owner_role=line.input_owner_role,
                input_owner=_person(db, line.input_owner_user_id),
                input_status=line.input_status,  # type: ignore[arg-type]
                input_requested_at=line.input_requested_at,
                requested_days=days,
                yearly=_yearly(lp.yearly),
                total=lp.total,
            )
        )

    explanation = (
        get_ai_service().explain_ocet_change(_diff_for_ai(version, proj, var))
        if version.lines
        else None
    )
    current = OcetCurrentVersionOut(
        **_version_out(db, version).model_dump(),
        can_edit=can_edit,
        edit_denied_reason=None if can_edit else denied,
        can_submit=can_submit,
        submit_denied_reasons=[] if can_submit else submit_reasons,
        inputs_pending=proj.inputs_pending,
        missing_line_ids=[ln.id for ln in version.lines if ln.base_amount is None],
    )
    return OcetOut(
        transition_id=est.transition_id,
        estimate=OcetEstimateOut(
            id=est.id,
            currency=est.currency,
            start_year=est.start_year,
            horizon_years=est.horizon_years,
            current_version=est.current_version,
        ),
        years=proj.years,
        versions=[_version_out(db, v) for v in est.versions],
        version=current,
        lines=lines_out,
        category_totals=[
            CategoryTotalOut(category=cat, amounts=_yearly(amounts), total=proj.category_grand[cat])
            for cat, amounts in proj.category_totals.items()
        ],
        grand_total_by_year=_yearly(proj.grand_total_by_year),
        total=proj.total,
        total_label=rules.format_total_label(proj.total),
        variance=VarianceOut(
            previous_version=previous.version if previous else None,
            total_abs=var.total_abs,
            total_pct=var.total_pct,
            by_category=_variance_rows(var.by_category),
            by_line=_variance_rows(var.by_line),
        ),
        approval=_approval_out(db, version),
        explanation=explanation,
        categories=list(ref.get("categories", [])),
        pricing_bases=list(ref.get("pricing_basis", [])),
        currencies=list(ref.get("currencies", [])),
        default_growth_pct={k: float(v) for k, v in (ref.get("default_growth_pct") or {}).items()},
    )


def get_ocet_view(db: Session, transition_id: str, user: User) -> OcetOut:
    """Full OcetOut for the transition's current version. 404 without transition / estimate."""
    estimate = _estimate(db, transition_id)
    version = next((v for v in estimate.versions if v.version == estimate.current_version), None)
    if version is None and estimate.versions:
        version = estimate.versions[-1]
    if version is None:
        raise NotFound(f"Transition {transition_id} has no OCET yet")
    return build_version_out(db, version, user)


# --------------------------------------------------------------------------- mutations


def create_estimate(db: Session, transition: Transition, user: User) -> OcetEstimate:
    """Create the empty estimate (v1 Draft, no lines). 409 if one already exists."""
    access.ensure_transition_role(db, user, transition, Perm.EDIT_OCET)
    existing = db.scalars(
        select(OcetEstimate).where(OcetEstimate.transition_id == transition.id)
    ).first()
    if existing is not None:
        raise Conflict("OCET already exists", ["This transition already has an OCET estimate"])
    ref = _reference_ocet(db)
    estimate = OcetEstimate(
        transition_id=transition.id,
        currency=(ref["currencies"] or ["USD"])[0],
        start_year=clock.today().year + 1,
        horizon_years=int(ref["default_horizon_years"]),
        current_version=1,
    )
    estimate.versions = [OcetVersion(version=1, status="Draft", note="", created_by=user.id)]
    db.add(estimate)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OcetEstimate",
        entity_id=estimate.id,
        action="created",
        transition_id=transition.id,
        after={
            "start_year": estimate.start_year,
            "horizon_years": estimate.horizon_years,
            "currency": estimate.currency,
        },
        note="OCET v1 created",
    )
    return estimate


def _line_snapshot(version: OcetVersion) -> list[dict[str, Any]]:
    return [
        {
            "line_key": ln.line_key,
            "category": ln.category,
            "base_amount": ln.base_amount,
            "growth_pct": ln.growth_pct,
            "year_overrides": dict(ln.year_overrides or {}),
            "input_status": ln.input_status,
        }
        for ln in version.lines
    ]


def _validate_line(
    line: OcetLineIn,
    ref: dict[str, Any],
    years: list[int],
    position: int,
    kept: OcetLine | None = None,
) -> list[str]:
    """Problems of one line. ``kept`` is the stored line being edited: a category or pricing basis
    the admin has since retired stays valid on it (only new choices must be active)."""
    errors: list[str] = []
    tag = f"Line {position}"
    if line.category not in ref.get("categories", []) and not (
        kept and kept.category == line.category
    ):
        errors.append(f"{tag}: unknown category '{line.category}'")
    if line.pricing_basis not in ref.get("pricing_basis", []) and not (
        kept and kept.pricing_basis == line.pricing_basis
    ):
        errors.append(f"{tag}: unknown pricing basis '{line.pricing_basis}'")
    if not -100 <= line.growth_pct <= 1000:
        errors.append(f"{tag}: growth must be between -100 and 1000")
    if line.base_amount is not None and line.base_amount < 0:
        errors.append(f"{tag}: base amount cannot be negative")
    for year, pct in line.year_overrides.items():
        if year not in years:
            errors.append(f"{tag}: override year {year} is outside {years[0]}-{years[-1]}")
        if years and year == years[0]:
            errors.append(f"{tag}: growth applies from the second year - no override for {year}")
        if not -100 <= pct <= 1000:
            errors.append(f"{tag}: override growth for {year} must be between -100 and 1000")
    if line.year_overrides and not (line.override_reason or "").strip():
        errors.append(f"{tag}: a reason is required when a year growth is overridden")
    return errors


def _default_owner(transition: Transition, role: str) -> str | None:
    """The person holding ``role`` on the transition (None for a role without a slot)."""
    return access.assigned_user_id(transition, role)


def save_lines(db: Session, version: OcetVersion, payload: OcetSaveIn, user: User) -> OcetVersion:
    """Bulk save (spec 9)."""
    access.ensure_transition_role(
        db, user, _transition(db, version.estimate.transition_id), Perm.EDIT_OCET
    )
    if version.status not in EDITABLE_STATUSES:
        raise Conflict(
            f"v{version.version} cannot be edited",
            [f"v{version.version} is {version.status} - create a new version to change it"],
        )
    est = version.estimate
    ref = _reference_ocet(db)
    years = rules.years_for(est.start_year, est.horizon_years)
    by_id = {ln.id: ln for ln in version.lines}
    errors: list[str] = []
    keys_seen: set[str] = set()
    default_basis = cfg.thresholds(db)["default_pricing_basis"]
    for position, line in enumerate(payload.lines, start=1):
        line.pricing_basis = line.pricing_basis or default_basis
        errors.extend(_validate_line(line, ref, years, position, by_id.get(line.id)))
        if line.id is not None and line.id not in by_id:
            errors.append(f"Line {position}: id {line.id} does not belong to v{version.version}")
        key = line.line_key or (by_id[line.id].line_key if line.id in by_id else None)
        if key:
            if key in keys_seen:
                errors.append(f"Line {position}: duplicate line key {key}")
            keys_seen.add(key)
    for lid in payload.deleted_line_ids:
        if lid not in by_id:
            errors.append(f"Deleted line id {lid} does not belong to v{version.version}")
    if errors:
        raise BadRequest("Validation failed", errors)

    transition = _transition(db, est.transition_id)
    before = _line_snapshot(version)
    for lid in dict.fromkeys(payload.deleted_line_ids):
        version.lines.remove(by_id[lid])

    # Never reuse a key already used by ANY version of this estimate (incl. lines deleted now),
    # otherwise compare/variance (matched by line_key) mixes a removed and an added line.
    used = {ln.line_key for ln in version.lines} | keys_seen
    used |= {ln.line_key for v in est.versions for ln in v.lines}
    counter = 0

    def free_key() -> str:
        nonlocal counter
        while True:
            counter += 1
            if f"L{counter}" not in used:
                used.add(f"L{counter}")
                return f"L{counter}"

    now = clock.now()
    for order, line in enumerate(payload.lines):
        row = by_id.get(line.id) if line.id is not None else None
        is_new = row is None
        if row is None:
            row = OcetLine(line_key=line.line_key or free_key())
            version.lines.append(row)
        elif line.line_key:
            row.line_key = line.line_key
        previous_status = None if is_new else row.input_status
        row.category = line.category
        row.description = line.description
        row.vendor = line.vendor
        row.pricing_basis = line.pricing_basis
        row.base_amount = line.base_amount
        row.growth_pct = line.growth_pct
        row.year_overrides = {str(y): float(v) for y, v in sorted(line.year_overrides.items())}
        row.override_reason = (line.override_reason or "").strip() or None
        row.input_owner_role = line.input_owner_role
        row.input_owner_user_id = (
            line.input_owner_user_id
            or (None if is_new else row.input_owner_user_id)
            or _default_owner(transition, line.input_owner_role)
        )
        if line.base_amount is None:
            keep = line.input_status == "Requested" or previous_status == "Requested"
            row.input_status = "Requested" if keep else "Missing"
            if row.input_status == "Requested" and row.input_requested_at is None:
                row.input_requested_at = now
        else:
            row.input_status = "Provided"
        row.sort_order = order
    touched = {line.id for line in payload.lines if line.id is not None}
    for offset, row in enumerate(
        r for r in version.lines if r.id is not None and r.id not in touched
    ):
        row.sort_order = len(payload.lines) + offset  # lines absent from the payload follow
    version.status = (
        "Inputs pending" if any(ln.base_amount is None for ln in version.lines) else "Draft"
    )
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OcetVersion",
        entity_id=version.id,
        action="lines_saved",
        transition_id=est.transition_id,
        before={"lines": before},
        after={"lines": _line_snapshot(version), "status": version.status},
        note=f"OCET v{version.version} lines saved",
    )
    return version


def submit_version(db: Session, version: OcetVersion, user: User) -> OcetVersion:
    """Submit for approval: chain Planner -> OLM; previous version becomes Superseded."""
    access.ensure_transition_role(
        db, user, _transition(db, version.estimate.transition_id), Perm.EDIT_OCET
    )
    reasons: list[str] = []
    if version.status == "Inputs pending":
        reasons.append(f"v{version.version} still has missing inputs")
    elif version.status != "Draft":
        reasons.append(
            f"v{version.version} is {version.status}; only a Draft version can be submitted"
        )
    if not version.lines:
        reasons.append("Add at least one cost line before submitting")
    reasons.extend(_missing_reasons(version))
    if reasons:
        raise Conflict("OCET cannot be submitted", list(dict.fromkeys(reasons)))

    est = version.estimate
    transition = _transition(db, est.transition_id)
    proj = _project(version)
    var = _variance_of(version, proj)
    request = approvals.create_approval_request(
        db,
        type="OCET",
        transition=transition,
        created_by=user,
        created_source="Human",
        subject_id=str(version.id),
        subject_label=_subject_label(version, proj, var),
    )
    version.status = "Submitted"
    version.submitted_at = clock.now()
    version.approval_request_id = request.id
    for other in est.versions:
        if other.version < version.version and other.status in ("Approved", "Submitted"):
            old = other.status
            other.status = "Superseded"
            audit.record(
                db,
                actor=user,
                actor_type="Human",
                entity="OcetVersion",
                entity_id=other.id,
                action="status_changed",
                transition_id=est.transition_id,
                before={"status": old},
                after={"status": "Superseded"},
                note=f"OCET v{other.version} superseded by v{version.version}",
            )
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OcetVersion",
        entity_id=version.id,
        action="submitted",
        transition_id=est.transition_id,
        before={"status": "Draft"},
        after={"status": "Submitted", "approval_request_id": request.id},
        note=f"OCET v{version.version} submitted for approval ({request.id})",
    )
    return version


def create_new_version(db: Session, transition_id: str, user: User) -> OcetVersion:
    """Copy the current version's lines into vN+1 (Draft / Inputs pending)."""
    estimate = _estimate(db, transition_id)
    access.ensure_transition_role(db, user, _transition(db, transition_id), Perm.EDIT_OCET)
    current = next((v for v in estimate.versions if v.version == estimate.current_version), None)
    if current is None:
        raise NotFound(f"Transition {transition_id} has no OCET yet")
    status = effective_status(db, current)
    if status in EDITABLE_STATUSES:
        raise Conflict(
            "A new version is not needed",
            [f"v{current.version} is still {status}; edit it instead"],
        )
    if status in ("Submitted", "Planner approved"):
        raise Conflict(
            "Approval is running",
            [
                f"v{current.version} is {status}; wait for the decision before creating a new version"
            ],
        )
    new = OcetVersion(
        estimate_id=estimate.id,
        version=current.version + 1,
        status="Draft",
        note="",
        created_by=user.id,
    )
    for line in current.lines:
        new.lines.append(
            OcetLine(
                line_key=line.line_key,
                category=line.category,
                description=line.description,
                vendor=line.vendor,
                pricing_basis=line.pricing_basis,
                base_amount=line.base_amount,
                growth_pct=line.growth_pct,
                year_overrides=dict(line.year_overrides or {}),
                override_reason=line.override_reason,
                input_owner_role=line.input_owner_role,
                input_owner_user_id=line.input_owner_user_id,
                input_status="Provided" if line.base_amount is not None else "Missing",
                input_requested_at=None,
                sort_order=line.sort_order,
            )
        )
    if any(ln.base_amount is None for ln in new.lines):
        new.status = "Inputs pending"
    estimate.versions.append(new)
    estimate.current_version = new.version
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OcetVersion",
        entity_id=new.id,
        action="created",
        transition_id=transition_id,
        after={"version": new.version, "status": new.status, "copied_from": current.version},
        note=f"OCET v{new.version} created from v{current.version}",
    )
    return new


def request_inputs(
    db: Session, version: OcetVersion, line_ids: list[int], user: User
) -> tuple[list[int], list[int]]:
    """Mark lines Requested and create one Orion draft per input owner (nothing is sent)."""
    access.ensure_transition_role(
        db, user, _transition(db, version.estimate.transition_id), Perm.EDIT_OCET
    )
    if version.status not in EDITABLE_STATUSES:
        raise Conflict(
            f"v{version.version} cannot be edited",
            [f"v{version.version} is {version.status} - create a new version to change it"],
        )
    if not line_ids:
        raise BadRequest("No lines selected", ["Select at least one line to request"])
    by_id = {ln.id: ln for ln in version.lines}
    errors: list[str] = []
    for lid in line_ids:
        line = by_id.get(lid)
        if line is None:
            errors.append(f"Line {lid} does not belong to v{version.version}")
        elif line.base_amount is not None:
            errors.append(f"{_label(line)}: nothing to request, a base amount exists")
    if errors:
        raise BadRequest("Validation failed", errors)

    est = version.estimate
    transition = _transition(db, est.transition_id)
    now = clock.now()
    by_owner: dict[str, list[OcetLine]] = {}
    for lid in dict.fromkeys(line_ids):
        line = by_id[lid]
        before = line.input_status
        line.input_status = "Requested"
        line.input_requested_at = now
        owner_id = (
            line.input_owner_user_id
            or _default_owner(transition, line.input_owner_role)
            or transition.or_focal_user_id
        )
        by_owner.setdefault(owner_id, []).append(line)
        audit.record(
            db,
            actor=user,
            actor_type="Human",
            entity="OcetLine",
            entity_id=line.id,
            action="input_requested",
            transition_id=transition.id,
            before={"input_status": before},
            after={"input_status": "Requested"},
            note=f"Input requested for {_label(line)}",
        )
    db.flush()

    link = approvals.absolute(f"/transitions/{transition.id}/ocet")
    draft_ids: list[int] = []
    for owner_id, lines in by_owner.items():
        owner = db.get(User, owner_id)
        if owner is None:
            continue
        items = "".join(f"<li>{escape_text(_label(ln))}</li>" for ln in lines)
        body = (
            f"<p>Hi {escape_text(owner.name)},</p>"
            f"<p>Please provide the base amount for the following OCET line(s) of "
            f"<strong>{escape_text(transition.name)}</strong> (v{version.version}):</p>"
            f"<ul>{items}</ul>"
            f'<p><a href="{escape_text(link)}">Open the OCET in Orion</a></p>'
            "<p>Orion, on behalf of the OR team</p>"
        )
        draft = drafts.create_draft(
            db,
            kind="Input request",
            transition=transition,
            to=[owner.email],
            cc=[user.email],
            subject=f"OCET inputs needed: {transition.name}",
            body_html=body,
            created_source="Orion agent",
            related_ids=[transition.id],
        )
        draft_ids.append(draft.id)
    return draft_ids, [ln.id for lines in by_owner.values() for ln in lines]


def compare_versions(
    db: Session, from_version_id: int, to_version_id: int, user: User
) -> OcetCompareOut:
    """Compare two versions of the same estimate."""
    old = get_version(db, from_version_id)
    new = get_version(db, to_version_id)
    if old.estimate_id != new.estimate_id:
        raise BadRequest(
            "Versions are not comparable", ["The versions belong to different estimates"]
        )
    est = new.estimate
    p_old, p_new = _project(old), _project(new)
    var = rules.variance(p_old, p_new)
    old_lines = {p.line_key: p for p in p_old.lines}
    new_lines = {p.line_key: p for p in p_new.lines}

    def rows(src: list[rules.VarianceRow], cats: bool) -> list[CompareRowOut]:
        out = []
        for r in src:
            if cats:
                f = p_old.category_totals.get(r.key)
                t = p_new.category_totals.get(r.key)
            else:
                f = old_lines[r.key].yearly if r.key in old_lines else None
                t = new_lines[r.key].yearly if r.key in new_lines else None
            out.append(
                CompareRowOut(
                    key=r.key,
                    category=r.category,
                    description=r.description,
                    from_total=r.previous_total,
                    to_total=r.current_total,
                    abs_change=r.abs_change,
                    pct_change=r.pct_change,
                    status=r.status,  # type: ignore[arg-type]
                    from_yearly=_yearly(f) if f else [],
                    to_yearly=_yearly(t) if t else [],
                )
            )
        return out

    def ref(v: OcetVersion, p: rules.Projection) -> CompareVersionRef:
        return CompareVersionRef(
            id=v.id,
            version=v.version,
            status=effective_status(db, v),  # type: ignore[arg-type]
            total=p.total,
        )

    return OcetCompareOut(
        transition_id=est.transition_id,
        currency=est.currency,
        from_version=ref(old, p_old),
        to_version=ref(new, p_new),
        years=p_new.years,
        rows=rows(var.by_line, False),
        category_rows=rows(var.by_category, True),
        from_total=p_old.total,
        to_total=p_new.total,
        total_abs=var.total_abs,
        total_pct=var.total_pct,
    )


# --------------------------------------------------------------------------- approval wiring


def _version_of_request(db: Session, request: ApprovalRequest) -> OcetVersion | None:
    sid = request.subject_id or ""
    if not sid.isdigit():
        return None
    version = db.get(OcetVersion, int(sid))
    if version is None or version.estimate.transition_id != request.transition_id:
        return None
    return version


def on_ocet_chain_completed(db: Session, request: ApprovalRequest) -> None:
    """Completion hook for type OCET (same transaction)."""
    version = _version_of_request(db, request)
    if version is None or request.status not in ("Approved", "Rejected"):
        return
    transition_id = request.transition_id
    before = version.status
    version.status = request.status
    audit.record(
        db,
        actor=None,
        actor_type="Workflow rule",
        entity="OcetVersion",
        entity_id=version.id,
        action="status_changed",
        transition_id=transition_id,
        before={"status": before},
        after={"status": version.status},
        note=f"OCET v{version.version} {request.status.lower()} (chain {request.id})",
    )
    if request.status != "Approved":
        return
    items = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition_id,
            TransitionItem.linked_module == LINKED_MODULE,
        )
    ).all()
    for item in items:
        # Same rule as the support-model hook (BR-030/BR-051): only open, applicable items.
        if item.applicability == "Not applicable" or not is_open_status(item.status):
            continue
        old = item.status
        done = done_status_for(item.playbook_item.lens)
        item.status = done
        item.last_updated_source = "Workflow rule"
        item.last_updated_by = None
        audit.record(
            db,
            actor=None,
            actor_type="Workflow rule",
            entity="TransitionItem",
            entity_id=item.id,
            action="updated",
            transition_id=transition_id,
            before={"status": old},
            after={"status": done},
            note=f"OCET v{version.version} approved",
        )
    db.flush()


def _card_data(db: Session, request: ApprovalRequest) -> dict[str, Any]:
    version = _version_of_request(db, request)
    if version is None:
        return {}
    proj = _project(version)
    var = _variance_of(version, proj)
    previous = _previous_version(version)
    if previous is not None and var.total_pct is not None:
        variance_text = f"{var.total_pct:+.1f}% vs v{previous.version}"
    else:
        variance_text = "First estimate"
    top = sorted(proj.category_grand.items(), key=lambda kv: -kv[1])[:3]
    return {
        "version": f"v{version.version}",
        "total_5y": rules.format_total_label(proj.total),
        "currency": version.estimate.currency,
        "variance_text": variance_text,
        "top_categories": [
            {"category": cat, "amount": rules.format_total_label(amount)} for cat, amount in top
        ],
    }


approvals.register_completion_hook("OCET", on_ocet_chain_completed)
approvals.register_card_data("OCET", _card_data)
