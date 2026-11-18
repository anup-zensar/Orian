"""Permission matrix (spec §3.3, BR-001) as plain data.

Rows marked "derived" are not in the spec table; they follow the closest spec row and are recorded
in PLAN.md (A-28). Approving an approval-chain step is not here: it is checked dynamically
(the step's role must equal the user's role, BR-041).
"""

from __future__ import annotations

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


R = Role
MATRIX: dict[Perm, frozenset[Role]] = {
    Perm.VIEW: ALL_ROLES,
    Perm.CREATE_TRANSITION: frozenset({R.OR_FOCAL, R.PM, R.ADMIN}),
    Perm.PROPOSE_TIER: frozenset({R.OR_FOCAL}),
    Perm.CONFIRM_TIER: frozenset({R.IRM}),
    Perm.CONFIRM_SCOPE: frozenset({R.OR_FOCAL}),
    Perm.UPDATE_BT_STATUS: frozenset({R.OR_FOCAL, R.PM, R.ARCHITECT, R.OLM}),
    Perm.UPDATE_C_STATUS: frozenset({R.IRM}),
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
}

# Human-readable reasons shown as tooltips / 403 messages (spec §3.3 "Only IRM can set compliance status").
DENIAL_REASONS: dict[Perm, str] = {
    Perm.VIEW: "You do not have access to Orion",
    Perm.CREATE_TRANSITION: "Only an OR focal, PM or Admin can create a transition",
    Perm.PROPOSE_TIER: "Only the OR focal can propose the tier",
    Perm.CONFIRM_TIER: "Only IRM can confirm the tier",
    Perm.CONFIRM_SCOPE: "Only the OR focal can confirm scope and applicability",
    Perm.UPDATE_BT_STATUS: "Only the OR focal, PM, Architect or OLM can update Business/Technical items",
    Perm.UPDATE_C_STATUS: "Only IRM can set compliance status",
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
    Perm.GENERATE_LEADERSHIP_UPDATE: "Only the OR focal can generate and send leadership updates",
    Perm.RUN_REMINDERS: "Only the OR focal or Admin can run the reminder engine",
    Perm.EDIT_TRANSITION: "Only the OR focal of the transition or an Admin can edit it",
}


def has_perm(role: str, perm: Perm) -> bool:
    return role in MATRIX[perm]


def permissions_for(role: str) -> list[str]:
    return sorted(p.value for p in Perm if has_perm(role, p))


def denied_reasons_for(role: str) -> dict[str, str]:
    return {p.value: DENIAL_REASONS[p] for p in Perm if not has_perm(role, p)}
