"""Seed loader (spec §11.2, PLAN.md M1.7). Loads ``/seed/*.json`` into an empty database.

Order (spec §11.2): reference -> users -> playbook items -> portfolios -> eval targets ->
transitions (+ tier assessments) -> items via BR-010 -> synthesised statuses (§11.3) -> flagship
overrides -> conditions, exceptions, risks, gate history, actions, evidence, eval results ->
OCET -> "Seeded" audit events.

Public functions (used by app.main, the admin demo controls and the tests):

* ``seed_all(db)``      - load everything into an EMPTY database (caller commits; one flush for speed).
* ``seed_if_empty(db)`` - run ``seed_all`` + commit when the users table is empty; True if it seeded.
* ``reset_and_seed()``  - drop + recreate all tables, then seed in a new session (NFR-06, < 10 s).

Assumptions used here: A-05 (IRM U14), A-06 (tier assessments), A-07 (flagship critical gap
S45-014), A-08/A-36 (pinned items in synthesis), A-10 (linked modules), A-29 (seeded scope is
confirmed), A-30 (OCET history).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app import db as database
from app.config import get_settings
from app.domain import audit
from app.models import (
    Action,
    AIProfile,
    ApprovalChainConfig,
    ApprovalRequest,
    ApprovalStep,
    AppSetting,
    Condition,
    EvalResult,
    EvalTarget,
    Evidence,
    ExceptionRecord,
    FlavourRule,
    GateReview,
    OcetEstimate,
    OcetLine,
    OcetVersion,
    PlaybookItem,
    Portfolio,
    ReferenceData,
    ReminderRule,
    Risk,
    TierAssessment,
    Transition,
    TransitionItem,
    User,
)
from app.rules.checklist import (
    LibraryItem,
    PlannedItem,
    TransitionRoles,
    assemble_checklist,
)
from app.rules.constants import (
    ACTOR_SYSTEM,
    AI_PROJECT_TYPES,
    APPLIES,
    GAP_STATUSES,
    GATE_ORDER,
    GATE_TYPE,
    OCET_LINKED_ITEMS,
    SUPPORT_MODEL_LINKED_FW,
    SUPPORT_MODEL_SHEET,
    TO_CONFIRM,
)
from app.rules.synthesis import Pin, Snapshot, SynthItem, synthesize

ALL_PROJECT_TYPES = ["Agentic AI", "Normal", "Combined", "Infrastructure"]
IRM_USER_ID = "U14"  # A-05: the only IRM
ORION_SOURCE_LABEL = "Portfolio golden set (client prototype, approximate)"
FW_SHEET = "Operate Readiness Framework"

# Reminder rules R1-R7 (spec §7.8 table) with default thresholds.
REMINDER_RULES: list[tuple[str, str, str, bool, dict[str, Any]]] = [
    (
        "R1",
        "Items due soon",
        "Open items due at the current gate and next decision within 14 days; one digest per owner "
        "per transition.",
        True,
        {"days_before_decision": 14},
    ),
    (
        "R2",
        "Overdue actions",
        "Action past its due date and not done; to the owner, cc OR focal.",
        True,
        {},
    ),
    (
        "R3",
        "Pending approval",
        "Approval step pending more than 2 days: reminder to the approver; more than 5 days: "
        "escalation to the OR focal.",
        True,
        {"reminder_after_days": 2, "escalate_after_days": 5},
    ),
    (
        "R4",
        "Gate ready",
        "All items due at the current decision gate are done (or conditioned) and no chain is open: "
        "OR focal is asked to send the approval request.",
        False,
        {},
    ),
    (
        "R5",
        "Missing inputs",
        "OCET line input requested for more than 3 days; to the input owner.",
        True,
        {"requested_for_days": 3},
    ),
    (
        "R6",
        "Monitoring trigger",
        "Transition reaches SG2: ask the Architect for monitoring requirements (FW-048 to FW-054).",
        False,
        {},
    ),
    (
        "R7",
        "Support model prompt",
        "Architecture walkthrough evidence (FW-006) accepted and no support model exists: "
        "OR focal is asked to create the support model.",
        False,
        {},
    ),
]


def _read(seed_dir: Path, name: str) -> Any:
    with (seed_dir / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def _linked_module(item_id: str, source_sheet: str, lens: str) -> str | None:
    """A-10: OCET and Support-model linked items (Compliance support-model items stay IRM-owned)."""
    if item_id in OCET_LINKED_ITEMS:
        return "OCET"
    if item_id in SUPPORT_MODEL_LINKED_FW:
        return "SUPPORT_MODEL"
    if source_sheet == SUPPORT_MODEL_SHEET and lens != "Compliance":
        return "SUPPORT_MODEL"
    return None


# --- reference, users, library -----------------------------------------------------------------


def _reference_rows(ref: dict[str, Any]) -> list[Any]:
    rows: list[Any] = [ReferenceData(key="reference", data=ref)]
    for pt in ref["project_types"]:
        rows.append(
            FlavourRule(
                project_type=pt["code"],
                checklists=list(pt["checklists"]),
                requires_tiering=bool(pt.get("requires_tiering", False)),
                note=pt.get("note"),
            )
        )
    for chain_type, steps in ref["approval_chains"].items():
        rows.append(ApprovalChainConfig(type=chain_type, steps=steps))
    for order, (rid, name, desc, autonomous, params) in enumerate(REMINDER_RULES):
        rows.append(
            ReminderRule(
                id=rid,
                name=name,
                description=desc,
                enabled=True,
                autonomous_eligible=autonomous,
                params=params,
                sort_order=order,
            )
        )
    return rows


def _library_rows(
    framework: list[dict[str, Any]],
    ai_items: list[dict[str, Any]],
    portfolios: dict[str, Any],
) -> list[PlaybookItem]:
    """PlaybookItem rows for every source, in source-file order (``sort_order``)."""
    rows: list[PlaybookItem] = []
    for order, fw in enumerate(framework):
        signoff = (fw.get("som_signoff") or "").strip()
        rows.append(
            PlaybookItem(
                id=fw["id"],
                source="FRAMEWORK",
                source_label=fw["source"],
                title=fw["activity"],
                description=fw["description"],
                detail=fw["comments"],
                gate=fw["gate"],
                lens=fw["lens"],
                lens_is_suggested=fw["lens_is_suggested"],
                category=fw["category"],
                kind="Deliverable",
                applicable_tiers=[],
                mandatory=fw["mandatory"],
                mandatory_rule="always",
                applies_to_project_types=list(fw["applies_to_project_types"]),
                owner_role_hint=fw["action_owner"],
                automation_tag=fw.get("automation_tag", ""),
                phase_window=fw.get("phase_window", ""),
                source_sheet=FW_SHEET,
                note=f"SOM sign-off: {signoff}" if signoff else "",
                is_compliance_control=fw["lens"] == "Compliance",
                linked_module=_linked_module(fw["id"], FW_SHEET, fw["lens"]),
                active=True,
                sort_order=order,
            )
        )
    for order, ai in enumerate(ai_items):
        rows.append(
            PlaybookItem(
                id=ai["id"],
                source="AI_PLAYBOOK",
                source_label=ai["source"],
                title=ai["item"],
                description=ai["detail"],
                detail=ai["assessor_input"],
                gate=ai["gate"],
                lens=ai["lens"],
                secondary_lens=ai.get("secondary_lens", ""),
                category=ai["section"],
                kind=ai["kind"],
                applicable_tiers=list(ai["applicable_tiers"]),
                tier_label=ai.get("tier_label", ""),
                tier_unspecified=ai["tier_unspecified"],
                mandatory=ai["mandatory"],
                mandatory_rule="always",
                applies_to_project_types=list(ai["applies_to_project_types"]),
                source_sheet=ai["source_sheet"],
                source_cell=ai["source_cell"],
                note=ai.get("note", ""),
                is_compliance_control=ai["is_compliance_control"],
                linked_module=_linked_module(ai["id"], ai["source_sheet"], ai["lens"]),
                active=True,
                sort_order=order,
            )
        )
    order = 0
    for portfolio in portfolios["portfolios"]:
        for gs in portfolio["golden_set"]:
            rows.append(
                PlaybookItem(
                    id=gs["id"],
                    source="PORTFOLIO",
                    source_label=ORION_SOURCE_LABEL,
                    portfolio=portfolio["name"],
                    title=gs["title"],
                    gate=gs["gate"],
                    lens=gs["lens"],
                    lens_is_suggested=gs.get("lens_is_suggested", False),
                    category="Portfolio golden set",
                    kind="Deliverable",
                    mandatory=gs["mandatory"],
                    mandatory_rule="always" if gs["mandatory"] else None,
                    applies_to_project_types=list(ALL_PROJECT_TYPES),
                    owner_role_hint=gs.get("owner_role_hint", ""),
                    active=True,
                    sort_order=order,
                )
            )
            order += 1
    for order, common in enumerate(portfolios["common_items"]):
        rows.append(
            PlaybookItem(
                id=common["id"],
                source="COMMON",
                source_label="Common items (all portfolios)",
                title=common["title"],
                gate=common["gate"],
                lens=common["lens"],
                category="Common items",
                kind="Deliverable",
                mandatory=common["mandatory"],
                mandatory_rule=common["mandatory_rule"],
                applies_to_project_types=list(ALL_PROJECT_TYPES),
                owner_role_hint=common.get("owner_role_hint", ""),
                active=True,
                sort_order=order,
            )
        )
    return rows


def _to_library_item(row: PlaybookItem) -> LibraryItem:
    """Plain-value view of a library row for the pure rules (tolerates unflushed column defaults)."""
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


def _eval_target_rows(metrics: list[dict[str, Any]]) -> list[EvalTarget]:
    rows: list[EvalTarget] = []
    for order, metric in enumerate(metrics):
        check = metric.get("machine_check") or {}
        for tier in (1, 2, 3, 4):
            rows.append(
                EvalTarget(
                    metric_id=metric["id"],
                    metric=metric["metric"],
                    tier=tier,
                    target_text=metric["targets_by_tier"][str(tier)],
                    operator=check.get("operator"),
                    value=check.get("value"),
                    unit=check.get("unit"),
                    evaluation=metric["evaluation"],
                    confirmed=bool(metric.get("tier_targets_confirmed", False)),
                    sort_order=order,
                )
            )
    return rows


def eval_passes(operator: str | None, target: float | None, value: float) -> bool | None:
    """Machine check of an eval result against a target (None = not machine-checkable)."""
    if operator is None or target is None:
        return None
    checks = {
        ">=": value >= target,
        "<=": value <= target,
        "<": value < target,
        ">": value > target,
        "==": value == target,
        "abs<=": abs(value) <= target,
    }
    return checks[operator]


# --- transitions -------------------------------------------------------------------------------


def _transition_row(src: dict[str, Any], today: date, now: datetime) -> Transition:
    intake = src.get("intake") or {}
    snapshot = src["snapshot"]
    return Transition(
        id=src["id"],
        name=src["name"],
        servicenow_project_id=src.get("servicenow_project_id"),
        description=src.get("description", ""),
        portfolio=src["portfolio"],
        region=src["region"],
        market=src.get("market", ""),
        project_type=src["project_type"],
        investment_type=intake.get("investment_type"),
        delivery_method=intake.get("delivery_method"),
        audience=intake.get("audience"),
        write_actions=intake.get("write_actions"),
        sensitive_data=intake.get("sensitive_data"),
        target_gate=intake.get("target_gate"),
        current_gate=src["current_gate"],
        risk_tier=src.get("risk_tier"),
        tier_status=src.get("tier_status"),
        or_focal_user_id=src["or_focal_user_id"],
        pm_user_id=src.get("pm_user_id"),
        architect_user_id=src.get("architect_user_id"),
        olm_user_id=src.get("olm_user_id"),
        irm_user_id=IRM_USER_ID,  # A-05
        next_decision_date=today + timedelta(days=snapshot["days_to_next_decision"]),
        autonomous_mode=False,
        status="Active",
        sites=[],
        blocker_note=snapshot.get("blocker") or None,
        is_flagship=bool(src.get("is_flagship", False)),
        assessment_launched_at=now,
        hypercare_no_defects_confirmed=False,
    )


def _tier_rows(src: dict[str, Any], now: datetime) -> list[Any]:
    """TierAssessment (+ empty AIProfile) for an AI transition (flagship: from seed, others A-06)."""
    tid, focal = src["id"], src["or_focal_user_id"]
    tiering = src.get("tiering")
    if tiering:
        rationale = tiering["rationale"]
        assessment = TierAssessment(
            transition_id=tid,
            answers=dict(tiering["answers"]),
            proposed_tier=tiering["proposed_tier"],
            rationale=[rationale] if isinstance(rationale, str) else list(rationale),
            proposed_by=focal,
            confirmed_tier=tiering["confirmed_tier"],
            confirmed_by_or_focal=tiering["confirmed_by"][0],
            confirmed_by_irm=tiering["confirmed_by"][1],
            confirmed_at=now,
        )
    else:
        assessment = TierAssessment(
            transition_id=tid,
            answers={},
            proposed_tier=src["risk_tier"],
            rationale=["Tier confirmed before Orion (seeded)"],
            proposed_by=focal,
            confirmed_tier=src["risk_tier"],
            confirmed_by_or_focal=focal,
            confirmed_by_irm=IRM_USER_ID,
            confirmed_at=now,
        )
    return [assessment, AIProfile(transition_id=tid)]


def _build_items(
    src: dict[str, Any],
    library: list[LibraryItem],
    flavour: dict[str, list[str]],
) -> list[TransitionItem]:
    """BR-010 assembly -> A-29 -> synthesis (§11.3) -> flagship overrides, as TransitionItem rows."""
    tid = src["id"]
    roles = TransitionRoles(
        or_focal=src["or_focal_user_id"],
        pm=src.get("pm_user_id"),
        architect=src.get("architect_user_id"),
        olm=src.get("olm_user_id"),
        irm=IRM_USER_ID,
    )
    planned = assemble_checklist(
        library,
        src["project_type"],
        src["portfolio"],
        src.get("risk_tier"),
        flavour[src["project_type"]],
        roles,
    )
    # A-29: scope of seeded transitions was confirmed before Orion.
    planned = [
        replace(p, applicability=APPLIES) if p.applicability == TO_CONFIRM else p for p in planned
    ]
    by_id: dict[str, PlannedItem] = {p.playbook_item_id: p for p in planned}

    snap = src["snapshot"]
    overrides = {o["item_id"]: o for o in src.get("item_overrides", [])}
    conditions = src.get("conditions", [])
    pins: dict[str, Pin] = {}
    for cond in conditions:  # A-36: items of seeded open conditions are pinned like overrides
        plan = by_id[cond["item_id"]]
        status = "Compliant with conditions" if plan.lens == "Compliance" else "In progress"
        pins[cond["item_id"]] = Pin(
            status=status, design_effectiveness="Yes" if plan.lens == "Compliance" else None
        )
    for item_id, override in overrides.items():
        pins[item_id] = Pin(
            status=override["status"], design_effectiveness=override.get("design_effectiveness")
        )
        if by_id[item_id].applicability != APPLIES:
            raise ValueError(f"{tid}: override item {item_id} is not applicable to this transition")
    covered = {
        c["item_id"]
        for c in conditions
        if c["status"] == "Open" and GATE_ORDER[c["due_gate"]] > GATE_ORDER[src["current_gate"]]
    }
    results = synthesize(
        [SynthItem(p.playbook_item_id, p.lens, p.due_gate, p.applicability) for p in planned],
        src["current_gate"],
        Snapshot(snap["readiness_pct"], snap["open_gaps"], snap["critical_gaps"]),
        pinned=pins,
        covered_item_ids=covered,
        preferred_critical_ids=["S45-014"] if src.get("is_flagship") else [],
    )

    rows: list[TransitionItem] = []
    for p in planned:
        res = results.get(p.playbook_item_id)
        rows.append(
            TransitionItem(
                transition_id=tid,
                playbook_item_id=p.playbook_item_id,
                applicability=p.applicability,
                excluded_by=p.excluded_by,
                status=res.status if res else p.status,
                gap_severity=res.gap_severity if res else None,
                owner_user_id=p.owner_user_id,
                due_gate=p.due_gate,
                design_effectiveness=res.design_effectiveness if res else None,
                note="",
                linked_module=p.linked_module,
                last_updated_by=None,
                last_updated_source="System",
            )
        )

    # Spec §11.3 step 5: the blocker is attached to the first critical gap item's note.
    blocker = snap.get("blocker")
    if blocker:
        critical = sorted(
            (r for r in rows if r.gap_severity == "Critical" and r.status in GAP_STATUSES),
            key=lambda r: (GATE_ORDER[r.due_gate], r.playbook_item_id),
        )
        if critical:
            critical[0].note = f"Blocker: {blocker}"

    # Spec §11.3 step 6: flagship overrides are applied exactly.
    row_by_id = {r.playbook_item_id: r for r in rows}
    for item_id, override in overrides.items():
        row = row_by_id[item_id]
        row.status = override["status"]
        row.note = override["note"]
        if "design_effectiveness" in override:
            row.design_effectiveness = override["design_effectiveness"]
        if "linked_module" in override:
            row.linked_module = override["linked_module"]
    return rows


def _first_critical_item_id(rows: list[TransitionItem]) -> str | None:
    critical = [r for r in rows if r.gap_severity == "Critical" and r.status in GAP_STATUSES]
    if not critical:
        return None
    critical.sort(key=lambda r: (GATE_ORDER[r.due_gate], r.playbook_item_id))
    return critical[0].playbook_item_id


# --- flagship records --------------------------------------------------------------------------


def _flagship_records(
    src: dict[str, Any],
    item_pk: dict[str, int],
    items: dict[str, TransitionItem],
    lens_by_id: dict[str, str],
    chain_exception: list[dict[str, Any]],
    eval_targets: dict[str, EvalTarget],
    today: date,
    now: datetime,
) -> list[Any]:
    """Conditions, exception + approval, risks, gate history, actions, evidence, eval results."""
    tid = src["id"]
    rows: list[Any] = []

    for cond in src["conditions"]:
        rows.append(
            Condition(
                id=cond["id"],
                transition_id=tid,
                transition_item_id=item_pk[cond["item_id"]],
                set_at_gate=cond["set_at_gate"],
                due_gate=cond["due_gate"],
                owner_user_id=cond["owner_user_id"],
                text=cond["text"],
                status=cond["status"],
            )
        )

    approval_id = "APR-0001"
    for exc in src["exceptions"]:
        steps = []
        for step in chain_exception:
            first = step["step"] == 1
            steps.append(
                ApprovalStep(
                    step=step["step"],
                    role=step["role"],
                    label=step.get("label", ""),
                    approver_user_id=IRM_USER_ID if first else None,
                    status="Pending" if first else "Waiting",
                    activated_at=now - timedelta(days=1) if first else None,
                )
            )
        rows.append(
            ApprovalRequest(
                id=approval_id,
                type="EXCEPTION",
                transition_id=tid,
                subject_id=exc["ref"],
                subject_label=f"{exc['ref']}: {exc['text']}",
                status="Pending",
                created_by=src["or_focal_user_id"],
                created_source="Human",
                steps=steps,
            )
        )
        rows.append(
            ExceptionRecord(
                ref=exc["ref"],
                transition_id=tid,
                transition_item_id=item_pk[exc["item_id"]],
                text=exc["text"],
                status=exc["status"],
                approval_request_id=approval_id,
                requested_by=src["or_focal_user_id"],
            )
        )

    for risk in src["risks"]:
        rows.append(
            Risk(
                id=risk["id"],
                transition_id=tid,
                title=risk["title"],
                rating=risk["rating"],
                decision=risk["decision"],
                item_ids=list(risk["item_ids"]),
            )
        )

    # Days ago derive from the gate order (45 days per gate, last reviewed gate = 30 days ago):
    # SG0/SG2/SG3 -> 120/75/30, and a different gate set in the seed data cannot raise.
    last_order = max((GATE_ORDER[r["gate"]] for r in src["gate_history"]), default=0)
    for review in src["gate_history"]:
        gate = review["gate"]
        days_ago = 30 + 45 * (last_order - GATE_ORDER[gate])
        rows.append(
            GateReview(
                transition_id=tid,
                gate=gate,
                gate_type=GATE_TYPE[gate],
                outcome=review["outcome"],
                decided_by=review["by"],
                decided_at=datetime.combine(today - timedelta(days=days_ago), time(10, 0)),
                note=review["note"],
                conditions_created=[c["id"] for c in src["conditions"] if c["set_at_gate"] == gate],
            )
        )

    priorities = {"ACT-001": "High", "ACT-002": "Medium", "ACT-003": "High"}
    for act in src["actions"]:
        rows.append(
            Action(
                id=act["id"],
                transition_id=tid,
                title=act["title"],
                item_ids=list(act["item_ids"]),
                owner_user_id=act["owner_user_id"],
                due_date=today + timedelta(days=act["due_in_days"]),
                status=act["status"],
                priority=priorities.get(act["id"], "Medium"),
                origin="Human",
                created_by="U01",
            )
        )

    for evd in src["evidence"]:
        item = items[evd["item_id"]]
        accepted = evd["status"] == "Accepted"
        reviewer = (
            IRM_USER_ID if lens_by_id[evd["item_id"]] == "Compliance" else src["or_focal_user_id"]
        )
        rows.append(
            Evidence(
                id=evd["id"],
                transition_id=tid,
                transition_item_id=item_pk[evd["item_id"]],
                title=evd["title"],
                type=evd["type"],
                url=evd["url"],
                submitted_by=item.owner_user_id,
                status=evd["status"],
                reviewed_by=reviewer if accepted else None,
                reviewed_at=now if accepted else None,
            )
        )

    tier = src["risk_tier"]
    for metric_id, value in src["eval_results"].items():
        target = eval_targets[f"{metric_id}:{tier}"]
        rows.append(
            EvalResult(
                transition_id=tid,
                metric_id=metric_id,
                value_number=float(value),
                passed=eval_passes(target.operator, target.value, float(value)),
                evaluated_at=now,
                source="Imported (mock)",
            )
        )
    return rows


def _ocet_rows(ocet: dict[str, Any], transition: dict[str, Any], now: datetime) -> list[Any]:
    """OCET estimate with v1 (Superseded, A-30) and v2 (Inputs pending) lines."""
    owner_by_role = {
        "ARCHITECT": transition.get("architect_user_id"),
        "PM": transition.get("pm_user_id"),
    }

    def line(src: dict[str, Any], order: int, *, v1: bool) -> OcetLine:
        requested = src["input_status"] == "Requested"
        overrides = {} if v1 else dict(src["year_overrides"])
        return OcetLine(
            line_key=src["id"],
            category=src["category"],
            description=src["description"],
            vendor=src["vendor"],
            pricing_basis=src["pricing_basis"],
            base_amount=src["base_amount"],
            growth_pct=src["growth_pct"],
            year_overrides=overrides,
            override_reason=None if v1 else src.get("override_reason"),
            input_owner_role=src["input_owner_role"],
            input_owner_user_id=owner_by_role.get(src["input_owner_role"]),
            input_status=src["input_status"],
            input_requested_at=now - timedelta(days=2) if requested and not v1 else None,
            sort_order=order,
        )

    seed_lines = ocet["lines"]
    v1_lines = [line(s, i, v1=True) for i, s in enumerate(seed_lines) if s["id"] != "L6"]
    v2_lines = [line(s, i, v1=False) for i, s in enumerate(seed_lines)]
    versions = {v["version"]: v for v in ocet["versions"]}
    estimate = OcetEstimate(
        transition_id=ocet["transition_id"],
        currency=ocet["currency"],
        start_year=ocet["start_year"],
        horizon_years=ocet["horizon_years"],
        current_version=2,
        versions=[
            OcetVersion(
                version=1,
                status="Superseded",
                note=versions[1]["note"],
                created_by=versions[1]["created_by"],
                lines=v1_lines,
            ),
            OcetVersion(
                version=2,
                status="Inputs pending",
                note=versions[2]["note"],
                created_by=versions[2]["created_by"],
                lines=v2_lines,
            ),
        ],
    )
    return [estimate]


# --- public API --------------------------------------------------------------------------------


def seed_all(db: Session) -> None:
    """Load all demo data into an empty database. The caller commits."""
    seed_dir = Path(get_settings().seed_dir)
    today = clock.today()
    now = clock.now()

    ref = _read(seed_dir, "reference.json")
    users = _read(seed_dir, "demo_users.json")["users"]
    framework = _read(seed_dir, "framework_activities.json")
    ai_items = _read(seed_dir, "ai_playbook_items.json")
    portfolios = _read(seed_dir, "portfolios.json")
    metrics = _read(seed_dir, "eval_metrics.json")
    transitions = _read(seed_dir, "sample_transitions.json")["transitions"]
    ocet = _read(seed_dir, "ocet_sample.json")
    flavour = {pt["code"]: list(pt["checklists"]) for pt in ref["project_types"]}

    # 1. reference + users + library + portfolios + eval targets
    db.add_all(_reference_rows(ref))
    db.add_all(
        User(
            id=u["id"],
            name=u["name"],
            email=u["email"],
            role=u["role"],
            focal_label=u.get("focal_label"),
        )
        for u in users
    )
    library_rows = _library_rows(framework, ai_items, portfolios)
    db.add_all(library_rows)
    db.add_all(
        Portfolio(
            name=p["name"],
            code=p["code"],
            focus_areas=list(p["focus_areas"]),
            intake_extra_fields=list(p.get("intake_extra_fields", [])),
        )
        for p in portfolios["portfolios"]
    )
    target_rows = _eval_target_rows(metrics)
    db.add_all(target_rows)
    eval_targets = {f"{t.metric_id}:{t.tier}": t for t in target_rows}

    # 2. transitions, tier assessments, items
    db.flush()  # column defaults (lists, strings) are applied at flush
    library = [_to_library_item(r) for r in library_rows]
    lens_by_id = {r.id: r.lens for r in library_rows}
    # NOTE: the unit of work only orders inserts along relationship() links, so every group of
    # tables that others reference by foreign key is flushed first.
    db.add_all(_transition_row(t, today, now) for t in transitions)
    db.flush()
    items_by_transition: dict[str, list[TransitionItem]] = {}
    for src in transitions:
        if src["project_type"] in AI_PROJECT_TYPES:
            db.add_all(_tier_rows(src, now))
        rows = _build_items(src, library, flavour)
        items_by_transition[src["id"]] = rows
        db.add_all(rows)
    db.flush()  # items get their integer ids (needed by conditions, evidence, exceptions)

    # 3. blocker risks (continue the CR-NN sequence after the flagship's) and flagship records
    flagship_risks = sum(len(t.get("risks", [])) for t in transitions)
    risk_seq = flagship_risks
    for src in transitions:
        blocker = src["snapshot"].get("blocker")
        if not blocker:
            continue
        risk_seq += 1
        first_critical = _first_critical_item_id(items_by_transition[src["id"]])
        db.add(
            Risk(
                id=f"CR-{risk_seq:02d}",
                transition_id=src["id"],
                title=blocker,
                rating="High",
                decision="Escalated",
                item_ids=[first_critical] if first_critical else [],
            )
        )

    for src in transitions:
        if not src.get("is_flagship"):
            continue
        items = {r.playbook_item_id: r for r in items_by_transition[src["id"]]}
        item_pk = {pid: r.id for pid, r in items.items()}
        records = _flagship_records(
            src,
            item_pk,
            items,
            lens_by_id,
            ref["approval_chains"]["EXCEPTION"],
            eval_targets,
            today,
            now,
        )
        # the approval request must exist before the exception that points at it
        db.add_all([r for r in records if isinstance(r, ApprovalRequest)])
        db.flush()
        db.add_all([r for r in records if not isinstance(r, ApprovalRequest)])
        if ocet["transition_id"] == src["id"]:
            db.add_all(_ocet_rows(ocet, src, now))

    # 4. audit events "Seeded"
    for src in transitions:
        audit.record(
            db,
            actor=None,
            actor_type=ACTOR_SYSTEM,
            entity="Transition",
            entity_id=src["id"],
            action="seeded",
            transition_id=src["id"],
            note="Seeded",
        )
    audit.record(
        db,
        actor=None,
        actor_type=ACTOR_SYSTEM,
        entity="System",
        entity_id="seed",
        action="seeded",
        note="Seeded demo data",
    )
    db.flush()


def seed_if_empty(db: Session) -> bool:
    """Seed (and commit) when the users table is empty. Returns True when it seeded."""
    if (db.scalar(select(func.count()).select_from(User)) or 0) > 0:
        return False
    seed_all(db)
    db.commit()
    return True


def reset_and_seed() -> None:
    """Drop and recreate every table, then seed (NFR-06). Clears the demo "today" override."""
    clock.set_today_override(None)  # seed relative to SEED_DATE / real date, not an old override
    database.drop_all()
    database.create_all()
    with database.SessionLocal() as db:
        seed_all(db)
        # the dropped tables took the persisted "today_override" setting with them; make it explicit
        db.merge(AppSetting(key="today_override", value=None))
        db.commit()
