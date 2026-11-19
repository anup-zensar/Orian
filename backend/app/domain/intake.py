"""Intake: create / edit transitions, ServiceNow prefill, autonomous mode (FR-020, FR-081; AC-05).

Validation produces one reason per problem (422 ``reasons``). Everything an Admin can change comes from
configuration (``app.domain.cfg``): the project types and portfolios on offer, the dropdown lists, which
intake fields are required for which project type, and the custom "Additional details" fields (stored
in ``Transition.custom_fields``).
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import ensure_admin_or_assigned, ensure_open, ensure_transition_role
from app.deps import ensure
from app.domain import audit, cfg
from app.domain import scope as scope_domain
from app.domain.ids import next_id
from app.errors import BadRequest, Conflict, Forbidden, NotFound
from app.models import Transition, User
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN
from app.schemas.intake import (
    ServiceNowProjectOut,
    TransitionCreateIn,
    TransitionUpdateIn,
)
from app.services.factory import get_servicenow_service

# Built-in fields that must always be filled in (the Admin cannot make them optional).
REQUIRED_FIELDS = ("name", "project_type", "portfolio", "region", "or_focal_user_id")
# Longest text an Additional-details text field accepts unless the Admin sets another limit.
DEFAULT_TEXT_LIMIT = 2000
# Built-in dropdown fields: the field key is also the key of its dropdown list.
OPTION_FIELDS = (
    "audience",
    "write_actions",
    "sensitive_data",
    "target_gate",
    "investment_type",
    "delivery_method",
)
# Role pickers: Transition column -> (required user role, default label). The label shown in messages
# is the role's phrase label from configuration (``cfg.role_phrase_label``).
ROLE_FIELDS: dict[str, tuple[str, str]] = {
    "or_focal_user_id": ("OR_FOCAL", "OR focal"),
    "pm_user_id": ("PM", "Project manager"),
    "architect_user_id": ("ARCHITECT", "Architect"),
    "olm_user_id": ("OLM", "OLM"),
    "irm_user_id": ("IRM", "IRM"),
}
# PATCH field groups (BE#2): who may change what.
DESCRIPTIVE_FIELDS = (
    "name",
    "servicenow_project_id",
    "portfolio",
    "region",
    "market",
    "sites",
    "target_gate",
    "investment_type",
    "delivery_method",
    "description",
    "next_decision_date",
    "blocker_note",
    "custom_fields",
)
ASSIGN_LOW_FIELDS = ("pm_user_id", "architect_user_id", "olm_user_id")  # the OR focal (or an Admin)
ASSIGN_HIGH_FIELDS = ("or_focal_user_id", "irm_user_id")  # Admin only
TIER_ANSWER_FIELDS = (
    "audience",
    "write_actions",
    "sensitive_data",
)  # changing them voids a proposal
TIER_INPUT_FIELDS = (*TIER_ANSWER_FIELDS, "project_type")  # OR focal only, locked once confirmed
EDITABLE_FIELDS = (
    *DESCRIPTIVE_FIELDS,
    *TIER_INPUT_FIELDS,
    *ASSIGN_HIGH_FIELDS,
    *ASSIGN_LOW_FIELDS,
)
AUDIT_FIELDS = (*EDITABLE_FIELDS, "current_gate", "status", "autonomous_mode")


# --- helpers -------------------------------------------------------------------------------------


def get_transition(db: Session, transition_id: str) -> Transition:
    t = db.get(Transition, transition_id)
    if t is None:
        raise NotFound("Transition not found")
    return t


def _clean(value: Any) -> Any:
    """Trim strings; blank -> None."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _normalise_sites(
    db: Session, raw: list[dict[str, str]], portfolio: str | None
) -> list[dict[str, str]]:
    """Sites are only kept for portfolios that require sites (e.g. Retail Site Systems)."""
    return [dict(row) for row in raw] if cfg.portfolio_requires_sites(db, portfolio) else []


def _label(db: Session, key: str) -> str:
    """The label of an intake field as the Admin configured it."""
    field = cfg.intake_field(db, key)
    return field.label if field is not None else key


def _check_choice(
    reasons: list[str], name: str, allowed: list[str], value: Any, current: Any
) -> None:
    """One reason when ``value`` is not on offer. An unchanged value stays valid (it may have been
    deactivated since the record was saved)."""
    if value and allowed and value != current and value not in allowed:
        reasons.append(f"{name} '{value}' is not one of: {', '.join(allowed)}")


def _clean_custom_value(
    db: Session, field: cfg.IntakeFieldCfg, value: Any, current: Any
) -> tuple[Any, str | None]:
    """(clean value, problem) for one custom field. Blank values become None (= clear the field)."""
    if value is None or value == "" or value == []:
        return None, None
    name = field.label
    kind = field.type
    if kind in ("text", "textarea"):
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            return None, f"{name} must be text"
        text = str(value).strip()
        limit = field.max_length or DEFAULT_TEXT_LIMIT
        if len(text) > limit:
            return None, f"{name} is longer than {limit} characters"
        return text or None, None
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            try:
                value = float(str(value))
            except ValueError:
                return None, f"{name} must be a number"
        if not math.isfinite(value):
            return None, f"{name} must be a number"
        if field.min is not None and value < field.min:
            return None, f"{name} must be at least {field.min:g}"
        if field.max is not None and value > field.max:
            return None, f"{name} must be at most {field.max:g}"
        return value, None
    if kind == "date":
        try:
            return date.fromisoformat(str(value)).isoformat(), None
        except ValueError:
            return None, f"{name} must be a date (YYYY-MM-DD)"
    if kind == "boolean":
        if not isinstance(value, bool):
            return None, f"{name} must be Yes or No"
        return value, None
    if kind in ("select", "multiselect"):
        allowed = cfg.option_values(db, field.option_list or "")
        chosen = value if kind == "multiselect" and isinstance(value, list) else [value]
        kept = current if isinstance(current, list) else [current]
        for one in chosen:
            if one not in allowed and one not in kept:
                return None, f"{name} '{one}' is not one of: {', '.join(allowed)}"
        return (list(chosen) if kind == "multiselect" else value), None
    if kind == "user":
        person = db.get(User, str(value))
        if person is None:
            return None, f"{name}: unknown user '{value}'"
        if field.option_list and person.role != field.option_list:
            return None, f"{name}: {person.name} does not have the {field.option_list} role"
        return person.id, None
    return None, f"{name} has an unsupported type '{kind}'"


def _merge_custom_fields(
    db: Session, sent: dict[str, Any] | None, stored: dict[str, Any] | None
) -> tuple[dict[str, Any], set[str], list[str]]:
    """Overlay the custom values in ``sent`` on the ``stored`` ones.

    Returns (merged values, keys that were sent, reasons). A blank value clears the field; keys of
    unknown or retired fields are refused.
    """
    fields = {f.key: f for f in cfg.intake_fields(db) if not f.builtin}
    merged = dict(stored or {})
    reasons: list[str] = []
    for key, value in (sent or {}).items():
        field = fields.get(key)
        if field is None:
            reasons.append(f"'{key}' is not an additional detail field of this form")
            continue
        clean, problem = _clean_custom_value(db, field, value, merged.get(key))
        if problem:
            reasons.append(problem)
        elif clean is None:
            merged.pop(key, None)
        else:
            merged[key] = clean
    return merged, set(sent or {}), reasons


def _required_keys(db: Session, project_type: str | None) -> list[str]:
    """Fields that must be filled in for ``project_type``: the always-required built-ins plus what the
    Admin required for this type (field rules and the type's own required list)."""
    keys = list(REQUIRED_FIELDS)
    if cfg.project_type(db, project_type) is not None:
        keys += [k for k in cfg.required_fields_for(db, project_type) if k not in keys]
    return keys


def _validate(
    db: Session,
    values: dict[str, Any],
    touched: set[str],
    *,
    raw_sites: list[dict[str, str]],
    custom: dict[str, Any],
    current: Transition | None = None,
) -> list[str]:
    """Reasons for the merged ``values`` (+ ``custom`` values); only ``touched`` fields get option /
    conditional checks (so unrelated edits on legacy seeded rows never fail). ``current`` is the saved
    record on an update: an unchanged value stays valid even if it was deactivated since."""

    def saved(field: str) -> Any:
        return getattr(current, field, None) if current is not None else None

    reasons: list[str] = []
    project_type = values.get("project_type")
    portfolio = values.get("portfolio")

    # Changing the project type or portfolio re-checks every required field.
    retest = bool(touched & {"project_type", "portfolio"})
    for key in _required_keys(db, project_type):
        field = cfg.intake_field(db, key)
        if field is not None and not (
            field.active and cfg.field_applies(field, project_type, portfolio)
        ):
            continue
        if key not in touched and not retest:
            continue
        value = values[key] if key in values else custom.get(key)
        if value is None or value == "" or value == []:
            reason = f"{_label(db, key)} is required"
            if key not in REQUIRED_FIELDS:
                reason += f" for {cfg.project_type_label(db, project_type)}"
            reasons.append(reason)

    if project_type and "project_type" in touched:
        codes = [p.code for p in cfg.project_types(db)]
        _check_choice(reasons, "Project type", codes, project_type, saved("project_type"))
    if portfolio and "portfolio" in touched:
        names = [p.name for p in cfg.portfolios(db)]
        _check_choice(reasons, "Portfolio", names, portfolio, saved("portfolio"))
    if values.get("region") and "region" in touched:
        regions = cfg.option_values(db, "regions")
        _check_choice(reasons, "Region", regions, values["region"], saved("region"))
    for key in OPTION_FIELDS:
        if key not in touched:
            continue
        field = cfg.intake_field(db, key)
        list_key = (field.option_list if field is not None else None) or key
        _check_choice(reasons, key, cfg.option_values(db, list_key), values.get(key), saved(key))

    if cfg.portfolio_requires_sites(db, portfolio) and touched & {"portfolio", "sites"}:
        label = cfg.portfolio_label(db, portfolio)
        if not raw_sites:
            reasons.append(f"Add at least one site (Site ID and Site key) for {label}")
        for index, row in enumerate(raw_sites, start=1):
            if not row["site_id"] or not row["site_key"]:
                reasons.append(f"Site row {index}: both Site ID and Site key are required")

    for field, (role, default_label) in ROLE_FIELDS.items():
        user_id = values.get(field)
        if field not in touched or not user_id:
            continue
        phrase = cfg.role_phrase_label(db, role) or default_label
        label = phrase[:1].upper() + phrase[1:]
        user = db.get(User, user_id)
        if user is None:
            reasons.append(f"{label}: unknown user '{user_id}'")
        elif user.role != role:
            reasons.append(f"{label}: {user.name} does not have the {role} role")
        elif user.active is False and user_id != saved(field):
            reasons.append(f"{label}: {user.name} is deactivated")
    return reasons


def _default_role_user(db: Session, role: str) -> str | None:
    return db.scalar(
        select(User.id).where(User.role == role, User.active.isnot(False)).order_by(User.id)
    )


# --- create --------------------------------------------------------------------------------------


def create_transition(db: Session, user: User, body: TransitionCreateIn) -> Transition:
    ensure(user, Perm.CREATE_TRANSITION)
    data = body.model_dump()
    confirm_duplicate = data.pop("confirm_duplicate", False)
    sent_custom = data.pop("custom_fields", None)
    values: dict[str, Any] = {k: _clean(v) for k, v in data.items() if k != "sites"}
    # An OR focal creates only transitions they will own (default: themselves); PM / Admin pick any.
    if user.role == "OR_FOCAL":
        if not values.get("or_focal_user_id"):
            values["or_focal_user_id"] = user.id
        elif values["or_focal_user_id"] != user.id:
            raise Forbidden(
                "An OR focal can only create transitions they will own - pick yourself as OR focal"
            )
    values["market"] = values.get("market") or ""
    if values.get("servicenow_project_id"):
        values["servicenow_project_id"] = str(values["servicenow_project_id"]).upper()
    values["description"] = (data.get("description") or "").strip()
    for field, (role, _label) in ROLE_FIELDS.items():
        if field != "or_focal_user_id" and field not in body.model_fields_set:
            values[field] = _default_role_user(db, role)
    raw_sites = _normalise_sites_raw(data["sites"])
    custom, custom_keys, custom_reasons = _merge_custom_fields(db, sent_custom, None)
    reasons = custom_reasons + _validate(
        db, values, set(EDITABLE_FIELDS) | custom_keys, raw_sites=raw_sites, custom=custom
    )
    if reasons:
        raise BadRequest("Validation failed", reasons)

    duplicate = (
        db.scalars(
            select(Transition.id).where(
                Transition.servicenow_project_id == values["servicenow_project_id"],
                Transition.status == "Active",
            )
        ).first()
        if values.get("servicenow_project_id")
        else None
    )
    if duplicate and not confirm_duplicate:
        raise Conflict(
            "A transition already exists for this ServiceNow project",
            [
                f"{duplicate} is already active for {values['servicenow_project_id']} - open it, "
                "or confirm to create a second transition for the same project"
            ],
        )

    t = Transition(
        id=next_id(db, Transition.id, "TR-"),
        current_gate="SG0",
        status="Active",
        autonomous_mode=False,
        assessment_launched_at=None,
        scope_decisions={},
        created_by=user.id,
        is_flagship=False,
        **{
            k: values.get(k)
            for k in EDITABLE_FIELDS
            if k not in ("sites", "blocker_note", "description", "market", "custom_fields")
        },
        description=values["description"],
        market=values["market"],
        sites=_normalise_sites(db, raw_sites, values["portfolio"]),
        custom_fields=custom or None,
    )
    db.add(t)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action="Transition created",
        transition_id=t.id,
        after=audit.snapshot(t, AUDIT_FIELDS),
        note=f"{t.project_type} / {t.portfolio} / {t.region}",
    )
    return t


def _normalise_sites_raw(raw: Any) -> list[dict[str, str]]:
    """Trimmed rows with fully blank rows dropped (validation sees the rows the user typed)."""
    rows: list[dict[str, str]] = []
    for row in raw or []:
        site_id = str(row.get("site_id") or "").strip()
        site_key = str(row.get("site_key") or "").strip()
        if site_id or site_key:
            rows.append({"site_id": site_id, "site_key": site_key})
    return rows


# --- update --------------------------------------------------------------------------------------


def _person_name(db: Session, user_id: str | None) -> str:
    person = db.get(User, user_id) if user_id else None
    return person.name if person is not None else "none"


def _saved(t: Transition, field: str) -> Any:
    """The stored value of an editable field (custom fields: an empty dict when nothing is stored)."""
    return (t.custom_fields or {}) if field == "custom_fields" else getattr(t, field)


def _check_update_access(
    db: Session,
    user: User,
    t: Transition,
    values: dict[str, Any],
    sent: set[str],
    raw_sites: list[dict[str, str]],
) -> None:
    """Per-group access of PATCH (BE#2). Only fields whose value really changes are checked."""
    changing = {f for f in sent - {"sites"} if values[f] != _saved(t, f)}
    if "sites" in sent and _normalise_sites(db, raw_sites, values["portfolio"]) != (t.sites or []):
        changing.add("sites")  # sites are workflow data: an Admin may not edit them (A-75)
    people = set(ASSIGN_LOW_FIELDS) | set(ASSIGN_HIGH_FIELDS)
    if user.role == "ADMIN" and changing - people:
        # R-01: an Admin may re-assign people and configure, never edit workflow data (dates, blocker
        # note, target gate, description ...) - those belong to the OR focal of the transition.
        ensure_transition_role(db, user, t, Perm.EDIT_TRANSITION, phrase="edit this transition")
    ensure_admin_or_assigned(db, user, t, Perm.EDIT_TRANSITION, phrase="edit this transition")
    if changing & set(ASSIGN_HIGH_FIELDS) and user.role != "ADMIN":
        raise Forbidden(
            f"Only an Admin can change the OR focal or IRM of {t.id} - an OR focal cannot pick "
            "who confirms the tier or hand the transition away"
        )
    if changing & set(TIER_INPUT_FIELDS):
        # Admin has no workflow rights: the tier inputs belong to the OR focal who proposes the tier.
        ensure_transition_role(
            db, user, t, Perm.PROPOSE_TIER, phrase="change the tier inputs of this transition"
        )
        if t.tier_status == "Confirmed":
            raise Conflict(
                "Tier inputs are locked",
                [
                    f"Tier inputs are locked after the IRM confirmed Tier {t.risk_tier} - "
                    "ask the IRM to change the tier (Tiering page, Change tier with a reason)"
                ],
            )


def _clear_tier_proposal(db: Session, user: User, t: Transition) -> None:
    """Tier inputs changed while the tier was only proposed: the proposal no longer matches, so it is
    cleared and the OR focal proposes again (the IRM never confirms stale answers)."""
    assessment = scope_domain.get_assessment(db, t.id)
    if assessment is None or assessment.proposed_tier is None or t.tier_status != "Proposed":
        return
    old = assessment.proposed_tier
    assessment.proposed_tier = None
    assessment.rationale = []
    assessment.proposed_by = None
    t.risk_tier = None
    t.tier_status = None
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="TierAssessment",
        entity_id=t.id,
        action="Tier proposal cleared",
        transition_id=t.id,
        before={"proposed_tier": old},
        after={"proposed_tier": None},
        note=f"Tier inputs changed - the proposed Tier {old} must be proposed again",
    )
    if t.assessment_launched_at is not None:
        scope_domain.reassemble_transition(
            db,
            t,
            user,
            action="Checklist re-assembled",
            note=f"Proposed Tier {old} cleared",
        )


def update_transition(db: Session, user: User, t: Transition, body: TransitionUpdateIn) -> None:
    sent = {f for f in body.model_fields_set if f in EDITABLE_FIELDS}
    data = body.model_dump()

    values: dict[str, Any] = {f: _saved(t, f) for f in EDITABLE_FIELDS}
    custom, custom_keys, custom_reasons = _merge_custom_fields(
        db, data["custom_fields"] if "custom_fields" in sent else None, t.custom_fields
    )
    values["custom_fields"] = custom
    for field in sent - {"sites", "custom_fields"}:
        value = _clean(data[field])
        if field in ("description", "market"):
            value = (data[field] or "").strip()
        if field == "servicenow_project_id" and value:
            value = str(value).upper()
        values[field] = value
    if "sites" in sent:
        raw_sites = _normalise_sites_raw(data["sites"])
    else:
        raw_sites = _normalise_sites_raw(t.sites)

    _check_update_access(db, user, t, values, sent, raw_sites)
    ensure_open(t)

    reasons = custom_reasons + _validate(
        db,
        values,
        (sent - {"custom_fields"}) | custom_keys,
        raw_sites=raw_sites,
        custom=custom,
        current=t,
    )
    if reasons:
        raise BadRequest("Validation failed", reasons)

    before = audit.snapshot(t, AUDIT_FIELDS)
    old_flavour = (t.project_type, t.portfolio)
    changed: list[str] = []
    people: list[str] = []
    for field in sent:
        new_value = (
            _normalise_sites(db, raw_sites, values["portfolio"])
            if field == "sites"
            else values[field]
        )
        old_value = _saved(t, field)
        if old_value != new_value:
            if field in ROLE_FIELDS:
                people.append(
                    f"{ROLE_FIELDS[field][1]}: {_person_name(db, old_value)} -> "
                    f"{_person_name(db, new_value)}"
                )
            setattr(t, field, (new_value or None) if field == "custom_fields" else new_value)
            changed.append(field)
    if (
        "portfolio" in changed
        and "sites" not in sent
        and not cfg.portfolio_requires_sites(db, t.portfolio)
    ):
        t.sites = []
        changed.append("sites")
    if not changed:
        return
    db.flush()
    note = "Changed: " + ", ".join(changed)
    if people:
        note += " (" + "; ".join(people) + ")"
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action="Transition updated",
        transition_id=t.id,
        before=before,
        after=audit.snapshot(t, AUDIT_FIELDS),
        note=note,
    )
    if set(changed) & set(TIER_ANSWER_FIELDS):
        _clear_tier_proposal(db, user, t)
    if t.assessment_launched_at is not None and (t.project_type, t.portfolio) != old_flavour:
        scope_domain.reassemble_transition(
            db,
            t,
            user,
            action="Checklist re-assembled",
            note=(f"{old_flavour[0]} / {old_flavour[1]} -> {t.project_type} / {t.portfolio}"),
        )


# --- autonomous mode -----------------------------------------------------------------------------


def set_autonomous_mode(db: Session, user: User, t: Transition, enabled: bool) -> None:
    ensure_transition_role(db, user, t, Perm.TOGGLE_AUTONOMOUS)
    if t.autonomous_mode == enabled:
        return
    before = {"autonomous_mode": t.autonomous_mode}
    t.autonomous_mode = enabled
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action=f"Autonomous mode {'on' if enabled else 'off'}",
        transition_id=t.id,
        before=before,
        after={"autonomous_mode": enabled},
    )


# --- ServiceNow ----------------------------------------------------------------------------------


def lookup_servicenow(db: Session, project_id: str) -> ServiceNowProjectOut:
    wanted = (project_id or "").strip().upper()
    record = get_servicenow_service().get_project(wanted)
    if record is None:
        raise NotFound("Not found in ServiceNow (mock) – enter manually")
    pm_name = record.get("pm")
    pm_user_id: str | None = None
    if pm_name:
        for u in db.scalars(select(User).where(User.role == "PM").order_by(User.id)):
            if u.name.strip().lower() == str(pm_name).strip().lower():
                pm_user_id = u.id
                break
    return ServiceNowProjectOut(
        project_id=str(record.get("project_id") or wanted),
        name=record.get("name") or "",
        project_type=record.get("project_type"),
        investment_type=record.get("investment_type"),
        delivery_method=record.get("delivery_method"),
        portfolio=record.get("portfolio"),
        region=record.get("region"),
        market=record.get("market"),
        description=record.get("description") or "",
        pm_name=pm_name,
        pm_user_id=pm_user_id,
    )
