"""Permission matrix (spec §3.3, BR-001) as plain data.

Rows marked "derived" are not in the spec table; they follow the closest spec row and are recorded
in PLAN.md (A-28). Approving an approval-chain step is not here: it is checked dynamically
(the step's role must equal the user's role, BR-041).

CR-01: ``MATRIX`` and ``DEFAULT_DENIAL_REASONS`` are the DEFAULTS (the seed copies them into
``role_permissions`` / ``permission_texts``). At run time ``has_perm`` / ``permissions_for`` /
``denied_reasons_for`` read an in-process cache built from those tables; with no rows (an empty or
unseeded database) they fall back to the defaults. The cache is rebuilt lazily after
``invalidate_cache()`` (called by ``app.domain.cfg.invalidate()``: every admin save, ``reset_and_seed``,
the ``fresh_seed`` test fixture). Inactive or unknown roles hold no permission. Orion is never a role
and has no row (BR-050).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    OR_FOCAL = "OR_FOCAL"
    PM = "PM"
    ARCHITECT = "ARCHITECT"
    OLM = "OLM"
    PLANNER = "PLANNER"
    IRM = "IRM"
    LEADERSHIP = "LEADERSHIP"
    ADMIN = "ADMIN"


ALL_ROLES = frozenset(Role)


class Perm(StrEnum):
    VIEW = "view"
    CREATE_TRANSITION = "create_transition"
    PROPOSE_TIER = "propose_tier"
    CONFIRM_TIER = "confirm_tier"
    CONFIRM_SCOPE = "confirm_scope"  # confirm scope / applicability, mark B/T items N/A
    UPDATE_BT_STATUS = "update_bt_status"
    UPDATE_T_STATUS = "update_t_status"  # Technical items only (Architect); B/T holders also pass
    UPDATE_C_STATUS = "update_c_status"  # compliance status + design effectiveness (+ N/A for C)
    MANAGE_EVIDENCE = "manage_evidence"  # upload / link evidence
    REVIEW_EVIDENCE_BT = "review_evidence_bt"
    REVIEW_EVIDENCE_C = "review_evidence_c"
    MANAGE_ACTIONS = "manage_actions"  # create / close actions
    RECORD_STAGE_REVIEW = "record_stage_review"
    RECORD_GATE_DECISION = "record_gate_decision"
    EDIT_OCET = "edit_ocet"
    EDIT_SUPPORT_MODEL = "edit_support_model"
    SEND_DRAFTS = "send_drafts"
    ADMIN = "admin"
    # --- derived (PLAN.md A-28) ---
    MANAGE_CONDITIONS = "manage_conditions"
    REQUEST_EXCEPTION = "request_exception"
    MANAGE_RISKS = "manage_risks"
    MANAGE_DEFECTS = "manage_defects"
    EDIT_EVAL_RESULTS = "edit_eval_results"
    EDIT_AI_PROFILE = "edit_ai_profile"
    TOGGLE_AUTONOMOUS = "toggle_autonomous"
    GENERATE_LEADERSHIP_UPDATE = "generate_leadership_update"
    RUN_REMINDERS = "run_reminders"
    EDIT_TRANSITION = "edit_transition"  # PATCH /transitions/{id}: its OR focal; Admin re-assigns
    # --- CR-01 (design 1.6): replace role-name checks in the code; callers switch to them later ---
    VIEW_ALL_APPROVALS = "view_all_approvals"  # GET /approvals?scope=all (OR focal, Admin today)
    SEE_MOCK_APPROVALS = (
        "see_mock_approvals"  # the mocked CISO/BISO step shows in my approvals (IRM)
    )
    SEE_ALL_TRANSITIONS = "see_all_transitions"  # whole-portfolio dashboard / metrics (Leadership)


R = Role
MATRIX: dict[Perm, frozenset[Role]] = {
    Perm.VIEW: ALL_ROLES,
    Perm.CREATE_TRANSITION: frozenset({R.OR_FOCAL, R.PM, R.ADMIN}),
    Perm.PROPOSE_TIER: frozenset({R.OR_FOCAL}),
    Perm.CONFIRM_TIER: frozenset({R.IRM}),
    Perm.CONFIRM_SCOPE: frozenset({R.OR_FOCAL}),
    Perm.UPDATE_BT_STATUS: frozenset({R.OR_FOCAL, R.PM, R.OLM}),
    Perm.UPDATE_T_STATUS: frozenset({R.ARCHITECT}),
    Perm.UPDATE_C_STATUS: frozenset({R.IRM, R.OLM, R.OR_FOCAL}),
    Perm.MANAGE_EVIDENCE: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT, R.OLM, R.IRM}),
    Perm.REVIEW_EVIDENCE_BT: frozenset({R.OR_FOCAL}),
    Perm.REVIEW_EVIDENCE_C: frozenset({R.IRM}),
    Perm.MANAGE_ACTIONS: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT, R.OLM, R.IRM}),
    Perm.RECORD_STAGE_REVIEW: frozenset({R.OR_FOCAL}),
    Perm.RECORD_GATE_DECISION: frozenset({R.OR_FOCAL}),
    Perm.EDIT_OCET: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT}),
    Perm.EDIT_SUPPORT_MODEL: frozenset({R.OR_FOCAL, R.ARCHITECT}),
    Perm.SEND_DRAFTS: frozenset({R.OR_FOCAL}),
    Perm.ADMIN: frozenset({R.ADMIN}),
    Perm.MANAGE_CONDITIONS: frozenset({R.OR_FOCAL, R.IRM}),
    Perm.REQUEST_EXCEPTION: frozenset({R.OR_FOCAL, R.IRM}),
    Perm.MANAGE_RISKS: frozenset({R.OR_FOCAL, R.IRM}),
    Perm.MANAGE_DEFECTS: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT, R.OLM}),
    Perm.EDIT_EVAL_RESULTS: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT}),
    Perm.EDIT_AI_PROFILE: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT}),
    Perm.TOGGLE_AUTONOMOUS: frozenset({R.OR_FOCAL}),
    Perm.GENERATE_LEADERSHIP_UPDATE: frozenset({R.OR_FOCAL, R.ADMIN}),
    Perm.RUN_REMINDERS: frozenset({R.OR_FOCAL, R.ADMIN}),
    Perm.EDIT_TRANSITION: frozenset({R.OR_FOCAL, R.ADMIN}),
    Perm.VIEW_ALL_APPROVALS: frozenset({R.OR_FOCAL, R.ADMIN}),
    Perm.SEE_MOCK_APPROVALS: frozenset({R.IRM}),
    Perm.SEE_ALL_TRANSITIONS: frozenset({R.LEADERSHIP}),
}

# Human-readable reasons shown as tooltips / 403 messages (spec §3.3 "Only IRM can set compliance status").
DEFAULT_DENIAL_REASONS: dict[Perm, str] = {
    Perm.VIEW: "You do not have access to Orion",
    Perm.CREATE_TRANSITION: "Only an OR focal, PM or Admin can create a transition",
    Perm.PROPOSE_TIER: "Only the OR focal can propose the tier",
    Perm.CONFIRM_TIER: "Only IRM can confirm the tier",
    Perm.CONFIRM_SCOPE: "Only the OR focal can confirm scope and applicability",
    Perm.UPDATE_BT_STATUS: "Only the OR focal, PM or OLM can update Business items",
    Perm.UPDATE_T_STATUS: "Only the Architect, PM, OLM or OR focal can update Technical items",
    Perm.UPDATE_C_STATUS: "Only IRM, OLM or the OR focal can set compliance status",
    Perm.MANAGE_EVIDENCE: "Your role cannot upload or link evidence",
    Perm.REVIEW_EVIDENCE_BT: "Only the OR focal can accept or reject Business/Technical evidence",
    Perm.REVIEW_EVIDENCE_C: "Only IRM can accept or reject Compliance evidence",
    Perm.MANAGE_ACTIONS: "Your role cannot create or close actions",
    Perm.RECORD_STAGE_REVIEW: "Only the OR focal can record stage reviews",
    Perm.RECORD_GATE_DECISION: "Only the OR focal can record gate decisions",
    Perm.EDIT_OCET: "Only the OR focal, PM or Architect can edit OCET lines",
    Perm.EDIT_SUPPORT_MODEL: "Only the OR focal or Architect can generate or edit the support model",
    Perm.SEND_DRAFTS: "Only the OR focal can send Orion drafts",
    Perm.ADMIN: "Only the Playbook admin can change configuration",
    Perm.MANAGE_CONDITIONS: "Only the OR focal or IRM can manage conditions",
    Perm.REQUEST_EXCEPTION: "Only the OR focal or IRM can request an exception",
    Perm.MANAGE_RISKS: "Only the OR focal or IRM can manage risks",
    Perm.MANAGE_DEFECTS: "Your role cannot manage hypercare defects",
    Perm.EDIT_EVAL_RESULTS: "Only the OR focal, PM or Architect can enter eval results",
    Perm.EDIT_AI_PROFILE: "Only the OR focal, PM or Architect can edit the AI profile",
    Perm.TOGGLE_AUTONOMOUS: "Only the OR focal can change autonomous mode",
    Perm.GENERATE_LEADERSHIP_UPDATE: "Only the OR focal or Admin can generate and send leadership updates",
    Perm.RUN_REMINDERS: "Only the OR focal or Admin can run the reminder engine",
    Perm.EDIT_TRANSITION: "Only the OR focal of the transition or an Admin can edit it",
    Perm.VIEW_ALL_APPROVALS: "Only the OR focal or Admin can see all approvals",
    Perm.SEE_MOCK_APPROVALS: "Only IRM can see the mocked approval steps",
    Perm.SEE_ALL_TRANSITIONS: "Only Leadership sees the whole portfolio on the dashboard",
}


# --- runtime cache (CR-01) -----------------------------------------------------------------------


@dataclass(frozen=True)
class PermissionCache:
    """What ``has_perm`` reads: perm value -> roles, perm value -> denial text, the active role codes."""

    matrix: dict[str, frozenset[str]]
    reasons: dict[str, str]
    active_roles: frozenset[str]
    from_db: bool


def _default_cache() -> PermissionCache:
    return PermissionCache(
        matrix={p.value: frozenset(r.value for r in rs) for p, rs in MATRIX.items()},
        reasons={p.value: t for p, t in DEFAULT_DENIAL_REASONS.items()},
        active_roles=frozenset(r.value for r in Role),
        from_db=False,
    )


_cache: PermissionCache | None = None


def build_cache(db) -> PermissionCache:  # noqa: ANN001 - Session; imported lazily to avoid cycles
    """Read ``role_permissions`` + ``permission_texts`` + ``roles``; defaults when there are no rows."""
    from sqlalchemy import select

    from app.models.reference import PermissionText, RolePermission
    from app.models.reference import Role as RoleRow

    rows = db.execute(select(RolePermission.perm, RolePermission.role_code)).all()
    if not rows:
        return _default_cache()
    matrix: dict[str, set[str]] = {p.value: set() for p in Perm}
    for perm, role_code in rows:
        matrix.setdefault(perm, set()).add(role_code)
    reasons = {p.value: t for p, t in DEFAULT_DENIAL_REASONS.items()}
    for perm, text in db.execute(select(PermissionText.perm, PermissionText.denial_reason)).all():
        if text:
            reasons[perm] = text
    role_rows = db.execute(select(RoleRow.code, RoleRow.active)).all()
    active = (
        frozenset(code for code, is_active in role_rows if is_active)
        if role_rows
        else frozenset(r.value for r in Role)
    )
    return PermissionCache(
        matrix={k: frozenset(v) for k, v in matrix.items()},
        reasons=reasons,
        active_roles=active,
        from_db=True,
    )


def load_cache(db) -> PermissionCache:  # noqa: ANN001
    """(Re)build the cache from ``db`` now (startup after seeding)."""
    global _cache
    _cache = build_cache(db)
    return _cache


def invalidate_cache() -> None:
    """Forget the cache; the next permission check rebuilds it from the database."""
    global _cache
    _cache = None


def current_cache() -> PermissionCache:
    """The cache, built on first use. A missing / unreadable database yields the defaults WITHOUT
    remembering them (the next call tries the database again)."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        from app.db import SessionLocal

        with SessionLocal() as db:
            _cache = build_cache(db)
    except Exception:  # tables not created yet, engine not configured, ...
        return _default_cache()
    return _cache


class _DenialReasons(Mapping[Perm, str]):
    """``DENIAL_REASONS[perm]`` - the current (admin-editable) reason text; same call sites as before."""

    def __getitem__(self, perm: Perm) -> str:
        key = Perm(perm).value
        return current_cache().reasons.get(key) or DEFAULT_DENIAL_REASONS[Perm(perm)]

    def __iter__(self) -> Iterator[Perm]:
        return iter(Perm)

    def __len__(self) -> int:
        return len(Perm)


DENIAL_REASONS: Mapping[Perm, str] = _DenialReasons()


def has_perm(role: str, perm: Perm) -> bool:
    cache = current_cache()
    return role in cache.active_roles and role in cache.matrix.get(Perm(perm).value, frozenset())


def roles_with(perm: Perm) -> frozenset[str]:
    """Active roles that currently hold ``perm``."""
    cache = current_cache()
    return frozenset(
        r for r in cache.matrix.get(Perm(perm).value, frozenset()) if r in cache.active_roles
    )


def permissions_for(role: str) -> list[str]:
    return sorted(p.value for p in Perm if has_perm(role, p))


def denied_reasons_for(role: str) -> dict[str, str]:
    return {p.value: DENIAL_REASONS[p] for p in Perm if not has_perm(role, p)}
