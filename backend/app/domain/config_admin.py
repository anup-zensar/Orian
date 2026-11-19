"""CR-01 admin configuration: the WRITES behind ``routers/config_admin.py`` (reads: ``config_admin_read``).

Layout: first the guardrails (one small pure function per rule, each returns a list of plain-language
reasons and is unit-tested in ``tests/test_config_guardrails.py``), then one block of functions per
admin section. Every section function

* checks the guardrails and raises ``BadRequest`` (422, one reason per problem), ``Conflict`` (409,
  "Used by N transitions - deactivate instead") or ``NotFound`` (404);
* changes the rows and flushes (the router commits and then calls ``cfg.invalidate()``);
* writes an AuditEvent: actor Human, entity ``config:<section>``, before / after.

Principle: codes are immutable, labels are editable, rows in use are deactivated instead of deleted.
Orion is never a role and has no permission row (BR-050); it only drafts, a permitted human clicks.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import access, permissions
from app.domain import audit, cfg, cfg_defaults
from app.domain import config_admin_read as read
from app.domain.ids import next_id
from app.errors import BadRequest, Conflict, NotFound
from app.models import (
    AppSetting,
    Checklist,
    EvalTarget,
    FlavourRule,
    IntakeField,
    MessageTemplate,
    OptionItem,
    OptionList,
    PermissionText,
    PlaybookItem,
    Portfolio,
    Role,
    RolePermission,
    TierQuestion,
    Transition,
    User,
)
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN, GATES
from app.schemas import config_admin as dto

# Words nobody may be called: they would make a person or role look like the Orion agent (BR-050).
RESERVED_WORDS = frozenset({"orion", "agent", "bot", "ai"})
PROJECT_TYPE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &_.-]{1,39}$")
# Portfolio names and project type codes travel in URLs, so these characters are not allowed.
URL_UNSAFE = re.compile(r"[/%?#]")
CUSTOM_FIELD_KEY = re.compile(r"^cf_[a-z][a-z0-9_]{1,40}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EVIDENCE_NEEDS = ("file", "url", "text", "none")
STRUCTURAL_REASON = "Behaviour depends on these values - only the labels can change"
BUILTIN_FIELD_REASON = "Built-in field: only its label, help text and visibility can change"
UNSAFE_MARKUP = re.compile(
    r"<\s*(script|iframe|object|embed|svg|style|link|meta|form|base)\b|javascript:|&#|[\s/\"']on\w+\s*=",
    re.I,
)


# =========================================================================== guardrails
# Each function is pure: it gets plain data and returns the list of reasons (empty = fine).


def check_permission_matrix(
    matrix: Mapping[str, Collection[str]],
    perm_codes: Collection[str],
    role_codes: Collection[str],
    active_user_roles: Collection[str],
) -> list[str]:
    """Guardrail 1 (and 3): the grid names only known permissions and roles; the Admin role keeps
    ``admin``, at least one ACTIVE user still holds it, and ``view`` includes every role."""
    reasons: list[str] = []
    for perm in sorted(set(matrix) - set(perm_codes)):
        reasons.append(f"Unknown permission '{perm}'")
    for perm in sorted(set(perm_codes) - set(matrix)):
        reasons.append(f"Permission '{perm}' is missing from the grid")
    for perm, roles in matrix.items():
        for role in sorted(set(roles) - set(role_codes)):
            reasons.append(f"'{perm}': unknown role '{role}'")
    admin_roles = set(matrix.get(Perm.ADMIN.value, ()))
    if "ADMIN" not in admin_roles:
        reasons.append("The Admin role must keep the right to change configuration")
    if not admin_roles & set(active_user_roles):
        reasons.append("At least one active user must keep the right to change configuration")
    missing_view = sorted(set(role_codes) - set(matrix.get(Perm.VIEW.value, ())))
    if missing_view:
        reasons.append(f"Every role must be able to use Orion (view): {', '.join(missing_view)}")
    return reasons


def _plain(text: str) -> str:
    """Lower case, accents removed, look-alike digits mapped ("0rion" -> "orion")."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return ascii_text.translate(str.maketrans("01", "oi"))


def check_reserved_words(what: str, *names: str) -> list[str]:
    """Guardrail 2 (BR-050): no person, role or permission is called Orion, agent, bot or AI."""
    reasons: list[str] = []
    for name in names:
        plain = _plain(name or "")
        words = set(re.split(r"[^a-z]+", plain))  # "Orion-bot" -> orion, bot
        words |= {re.sub(r"[^a-z]", "", token) for token in plain.split()}  # "O-r-i-o-n" -> orion
        hit = sorted(words & RESERVED_WORDS)
        if hit:
            reasons.append(
                f"{what} '{name}' uses the reserved word '{hit[0]}': Orion is not a person or a role"
            )
    return reasons


def check_user_deactivation(
    target_id: str,
    actor_id: str,
    users: Sequence[tuple[str, str, bool]],
    admin_roles: Collection[str],
) -> list[str]:
    """Guardrail 4: you cannot deactivate yourself or the last active user who can change
    configuration. ``users`` = (id, role, active) of everybody."""
    reasons: list[str] = []
    if target_id == actor_id:
        reasons.append("You cannot deactivate yourself")
    target_role = next((role for uid, role, _ in users if uid == target_id), None)
    if target_role in admin_roles:
        others = [
            u for u, role, active in users if active and role in admin_roles and u != target_id
        ]
        if not others:
            reasons.append("This is the last active Admin: someone else must keep the admin right")
    return reasons


def check_user_role_change(
    target_id: str,
    actor_id: str,
    new_role: str,
    users: Sequence[tuple[str, str, bool]],
    admin_roles: Collection[str],
) -> list[str]:
    """Guardrail 4: you cannot move yourself, or the last active Admin, away from an admin role."""
    target_role = next((role for uid, role, _ in users if uid == target_id), None)
    if target_role not in admin_roles or new_role in admin_roles:
        return []
    if target_id == actor_id:
        return ["You cannot change your own role away from Admin"]
    others = [u for u, role, active in users if active and role in admin_roles and u != target_id]
    return [] if others else ["This is the last active Admin: its role cannot change"]


def check_keep_one_active(what: str, remaining_active: int) -> list[str]:
    """Guardrail 5: the last active project type, portfolio or region cannot be switched off."""
    if remaining_active >= 1:
        return []
    return [f"At least one {what} must stay active"]


def check_one_critical(items: Sequence[tuple[bool, Mapping[str, Any]]]) -> list[str]:
    """Guardrail 6: exactly one ACTIVE severity counts as critical. ``items`` = (active, meta)."""
    n = sum(1 for active, meta in items if active and meta.get("counts_as_critical"))
    if n == 1:
        return []
    return [f"Exactly one active severity must count as critical (found {n})"]


def check_structural_items(
    structural: bool,
    existing: Mapping[str, tuple[bool, Mapping[str, Any]]],
    submitted: Sequence[tuple[str, bool, Mapping[str, Any]]],
) -> list[str]:
    """Guardrail 3: a structural list keeps its values, their active flag and meta; only labels and
    descriptions change. ``existing`` = value -> (active, meta); ``submitted`` = (value, active, meta).
    """
    if not structural:
        return []
    reasons: list[str] = []
    values = [value for value, _, _ in submitted]
    for value in values:
        if value not in existing:
            reasons.append(f"'{value}' cannot be added: {STRUCTURAL_REASON}")
    for value in existing:
        if value not in values:
            reasons.append(f"'{value}' cannot be removed: {STRUCTURAL_REASON}")
    for value, active, meta in submitted:
        if value in existing and (
            active != existing[value][0] or dict(meta) != dict(existing[value][1])
        ):
            reasons.append(f"'{value}' can only be relabelled: {STRUCTURAL_REASON}")
    return reasons


def check_item_meta(
    meta_fields: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any],
    role_codes: Collection[str],
) -> list[str]:
    """Meta values must match the types the list declares (token / text / number / boolean /
    select / list / role / gate); keys the list does not declare are refused."""
    declared = {m["key"]: m for m in meta_fields}
    reasons: list[str] = []
    for key, value in meta.items():
        spec = declared.get(key)
        if spec is None:
            reasons.append(f"'{key}' is not a column of this list")
            continue
        kind = spec.get("type")
        if value in (None, ""):
            continue
        ok = {
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "select": value in (spec.get("options") or []),
            "list": isinstance(value, list) and all(isinstance(v, str) for v in value),
            "role": value in role_codes,
            "gate": value in GATES,
        }.get(kind, isinstance(value, str))
        if not ok:
            reasons.append(f"'{key}': '{value}' is not a valid {spec.get('label') or kind}")
    return reasons


def check_thresholds(
    doc: Mapping[str, Any], tier_numbers: Collection[int], pricing_bases: Collection[str]
) -> list[str]:
    """Guardrail 8: amber is never stricter than red; the default tier and pricing basis exist.
    (Ranges are checked by the request model.)"""
    rag = doc["rag"]
    reasons: list[str] = []
    if rag["amber_critical_gaps"] > rag["red_critical_gaps"]:
        reasons.append("Amber cannot need more critical gaps than Red")
    if rag["amber_lens_below"] < rag["red_lens_below"]:
        reasons.append("Amber lens readiness must be at least the Red value")
    if doc["default_tier"] not in tier_numbers:
        reasons.append(f"Default tier {doc['default_tier']} is not a defined tier")
    if doc["default_pricing_basis"] not in pricing_bases:
        reasons.append(f"'{doc['default_pricing_basis']}' is not an active pricing basis")
    return reasons


def check_custom_field_key(key: str, existing_keys: Collection[str]) -> list[str]:
    """Guardrail 9: custom field keys are ``cf_<slug>``, slug-safe and unique."""
    if not CUSTOM_FIELD_KEY.match(key):
        return [f"'{key}' is not a valid field key (cf_ + lowercase letters, digits, underscores)"]
    return [f"A field with the key '{key}' already exists"] if key in existing_keys else []


def check_field_type_change(old_type: str, new_type: str, used_by: int) -> list[str]:
    """Guardrail 9: the type of a custom field is fixed once any transition holds a value."""
    if old_type != new_type and used_by > 0:
        return [f"{used_by} transitions hold a value, so the type cannot change - add a new field"]
    return []


def check_template(key: str, subject: str, body: str, allowed: Collection[str]) -> list[str]:
    """Guardrail 7: a template uses only its own placeholders and no scripts. (Who receives a message
    and when it is sent are not part of a template, so they cannot change here.)"""
    reasons = [
        f"{key}: '{{{{{name}}}}}' is not a placeholder of this message"
        for name in cfg_defaults.placeholders_in(subject, body)
        if name not in allowed
    ]
    if UNSAFE_MARKUP.search(subject + body):
        reasons.append(f"{key}: scripts and event handlers are not allowed in a message")
    return reasons


def check_autonomy_lowered(rule_id: str, was: bool, now: bool) -> list[str]:
    """Guardrail 7: a reminder may be made LESS autonomous, never more (R4 and approval requests are
    never autonomous)."""
    if now and not was:
        return [f"{rule_id}: autonomous sending can only be switched off, not on"]
    return []


def check_same_ids(what: str, existing: Collection[Any], submitted: Collection[Any]) -> list[str]:
    """Guardrail 3/6: tier numbers and tier question ids are fixed (BR-011 reads them)."""
    reasons: list[str] = []
    if len(set(submitted)) != len(list(submitted)):
        reasons.append(f"Each {what} may appear only once")
    for missing in sorted(set(existing) - set(submitted)):
        reasons.append(f"{what} {missing} cannot be removed")
    for extra in sorted(set(submitted) - set(existing)):
        reasons.append(f"{what} {extra} cannot be added")
    return reasons


def check_checklist_deactivation(code: str, listing_types: Collection[str]) -> list[str]:
    """Guardrail 5: a checklist that an active project type still lists cannot be switched off."""
    if listing_types:
        return [
            f"Used by project types: {', '.join(sorted(listing_types))} - remove it there first"
        ]
    return []


# =========================================================================== shared helpers


def _audit(
    db: Session,
    user: User,
    section: str,
    entity_id: str | int,
    action: str,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    note: str = "",
) -> None:
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity=f"config:{section}",
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        note=note,
    )


def _refuse(detail: str, reasons: list[str]) -> None:
    if reasons:
        raise BadRequest(detail, list(dict.fromkeys(reasons)))


def _used_by_conflict(what: str, n: int) -> Conflict:
    return Conflict(
        f"Used by {n} transitions - deactivate instead",
        [f"{what} is used by {n} transitions - deactivate it instead of deleting it"],
    )


def _used_transitions(db: Session, column: Any, value: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Transition).where(column == value)) or 0)


def _next_sort(db: Session, column: Any) -> int:
    top = db.scalar(select(func.max(column)))
    return (top if top is not None else -1) + 1


def _clean(values: Sequence[str]) -> list[str]:
    """Trimmed, non-empty, unique (case-insensitive) values in the given order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = value.strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out


def _set(row: Any, changes: Mapping[str, Any]) -> None:
    for name, value in changes.items():
        setattr(row, name, value)


def _pick(row: Any, fields: Sequence[str]) -> dict[str, Any]:
    return audit.snapshot(row, fields)


def _changes(body: Any) -> dict[str, Any]:
    """The fields a PATCH body actually sent."""
    return body.model_dump(exclude_unset=True)


# =========================================================================== project types

TYPE_FIELDS = (
    "label",
    "description",
    "active",
    "sort_order",
    "checklists",
    "requires_tiering",
    "has_ai_profile",
    "has_eval_metrics",
    "required_intake_fields",
    "synonyms",
    "color",
    "note",
)


def _project_type_row(db: Session, code: str) -> FlavourRule:
    row = db.get(FlavourRule, code)
    if row is None:
        raise NotFound(f"Project type '{code}' not found")
    return row


def _check_type_links(
    db: Session,
    checklists: Sequence[str],
    required_fields: Sequence[str],
    already_listed: Collection[str] = (),
) -> list[str]:
    """Checklists must be active library checklists (one the type already lists is left alone);
    required fields must exist."""
    defs = {c.code: c for c in cfg.checklist_defs(db, active_only=False)}
    reasons: list[str] = []
    if not checklists:
        reasons.append("Pick at least one checklist (a type without items is unusable)")
    for code in checklists:
        found = defs.get(code)
        if found is None:
            reasons.append(f"Unknown checklist '{code}'")
        elif code in already_listed:
            continue
        elif not found.active:
            reasons.append(f"Checklist '{code}' is inactive")
        elif found.kind != "library":
            reasons.append(f"'{code}' is added automatically; pick the library checklists only")
    known = {f.key for f in cfg.intake_fields(db, form=None, active_only=False)}
    for key in required_fields:
        if key not in known:
            reasons.append(f"Unknown intake field '{key}'")
    return reasons


def write_type_requirements(db: Session, row: FlavourRule, keys: Sequence[str]) -> None:
    """Make ``keys`` the fields required for project type ``row`` - on BOTH sides: the type's
    ``required_intake_fields`` and each field's ``required_for_project_types`` (so they cannot
    diverge). A field that was never required becomes "required by project type"."""
    wanted = list(dict.fromkeys(keys))
    fields = list(db.scalars(select(IntakeField)))
    for f in fields:
        types = [t for t in (f.required_for_project_types or []) if t != row.project_type]
        if f.key in wanted:
            types.append(row.project_type)
            if f.required_mode == "never":
                f.required_mode = "by_project_type"
        f.required_for_project_types = types
    row.required_intake_fields = [k for k in wanted if k in {f.key for f in fields}]


def write_field_requirements(
    db: Session, field: IntakeField, mode: str, types: Sequence[str]
) -> None:
    """Set when ``field`` is required (never / always / by project type) and mirror it into the
    project types' ``required_intake_fields`` - the other half of ``write_type_requirements``."""
    chosen = list(dict.fromkeys(types)) if mode == "by_project_type" else []
    field.required_mode = mode
    field.required_for_project_types = chosen
    for rule in db.scalars(select(FlavourRule)):
        keys = [k for k in (rule.required_intake_fields or []) if k != field.key]
        if rule.project_type in chosen:
            keys.append(field.key)
        rule.required_intake_fields = keys


def create_project_type(db: Session, user: User, body: dto.ProjectTypeCreateIn) -> str:
    """New project type, no code change needed. 409 when the code exists (any letter case)."""
    code = body.code.strip()
    reasons = (
        []
        if PROJECT_TYPE_CODE.match(code)
        else [f"'{code}': use letters, digits, spaces and - _ & . (2-40 characters)"]
    )
    if any(p.code.lower() == code.lower() for p in cfg.project_types(db, active_only=False)):
        raise Conflict(f"Project type '{code}' already exists", [f"'{code}' already exists"])
    checklists = list(dict.fromkeys(body.checklists))
    reasons += _check_type_links(db, checklists, body.required_intake_fields)
    _refuse("Invalid project type", reasons)
    row = FlavourRule(
        project_type=code,
        checklists=checklists,
        requires_tiering=body.requires_tiering,
        note=body.note,
        label=body.label.strip() or code,
        description=body.description,
        active=True,
        sort_order=_next_sort(db, FlavourRule.sort_order),
        has_ai_profile=body.has_ai_profile,
        has_eval_metrics=body.has_eval_metrics,
        required_intake_fields=[],
        synonyms=_clean(body.synonyms),
    )
    db.add(row)
    db.flush()
    write_type_requirements(db, row, body.required_intake_fields)
    db.flush()
    _audit(db, user, "project_types", code, "created", None, _pick(row, TYPE_FIELDS))
    return code


def update_project_type(db: Session, user: User, code: str, body: dto.ProjectTypeUpdateIn) -> None:
    """Edit a project type (never its code). Existing transitions keep their items."""
    row = _project_type_row(db, code)
    changes = _changes(body)
    before = _pick(row, TYPE_FIELDS)
    reasons: list[str] = []
    if "checklists" in changes or "required_intake_fields" in changes:
        reasons += _check_type_links(
            db,
            changes.get("checklists", row.checklists),
            changes.get("required_intake_fields", []),
            already_listed=row.checklists or [],
        )
    if changes.get("active") is False and row.active:
        others = [p for p in cfg.project_types(db) if p.code != code]
        reasons += check_keep_one_active("project type", len(others))
    _refuse("Invalid project type", reasons)
    required = changes.pop("required_intake_fields", None)
    if "label" in changes:
        changes["label"] = changes["label"].strip() or code
    if "synonyms" in changes:
        changes["synonyms"] = _clean(changes["synonyms"])
    if "checklists" in changes:
        changes["checklists"] = list(dict.fromkeys(changes["checklists"]))
    for name in (
        "label",
        "active",
        "sort_order",
        "requires_tiering",
        "has_ai_profile",
        "has_eval_metrics",
    ):
        if name in changes and changes[name] is None:
            changes.pop(name)
    _set(row, changes)
    if required is not None:
        write_type_requirements(db, row, required)
    db.flush()
    _audit(db, user, "project_types", code, "updated", before, _pick(row, TYPE_FIELDS))


def delete_project_type(db: Session, user: User, code: str) -> None:
    """Delete a project type no transition uses (409 otherwise)."""
    row = _project_type_row(db, code)
    n = _used_transitions(db, Transition.project_type, code)
    if n:
        raise _used_by_conflict(f"Project type '{code}'", n)
    if row.active:
        _refuse(
            "Invalid project type",
            check_keep_one_active("project type", len(cfg.project_types(db)) - 1),
        )
    before = _pick(row, TYPE_FIELDS)
    write_type_requirements(db, row, [])
    db.delete(row)
    db.flush()
    _audit(db, user, "project_types", code, "deleted", before, None)


# =========================================================================== checklists

CHECKLIST_FIELDS = ("label", "description", "active", "sort_order", "tier_filtered", "kind")


def _checklist_row(db: Session, code: str) -> Checklist:
    row = db.get(Checklist, code)
    if row is None:
        raise NotFound(f"Checklist '{code}' not found")
    return row


def _types_listing(db: Session, code: str, active_only: bool = False) -> list[str]:
    return [p.code for p in cfg.project_types(db, active_only=active_only) if code in p.checklists]


def create_checklist(db: Session, user: User, body: dto.ChecklistCreateIn) -> str:
    """New library checklist; project types include it by listing it."""
    if db.get(Checklist, body.code) is not None:
        raise Conflict(f"Checklist '{body.code}' already exists", [f"'{body.code}' already exists"])
    row = Checklist(
        code=body.code,
        label=body.label.strip() or body.code,
        description=body.description,
        active=True,
        sort_order=_next_sort(db, Checklist.sort_order),
        is_builtin=False,
        tier_filtered=body.tier_filtered,
        kind="library",
    )
    db.add(row)
    db.flush()
    _audit(db, user, "checklists", row.code, "created", None, _pick(row, CHECKLIST_FIELDS))
    return row.code


def update_checklist(db: Session, user: User, code: str, body: dto.ChecklistUpdateIn) -> None:
    """Edit label, description, order, tier filter, active. The kind never changes."""
    row = _checklist_row(db, code)
    changes = {k: v for k, v in _changes(body).items() if v is not None}
    before = _pick(row, CHECKLIST_FIELDS)
    reasons: list[str] = []
    if "tier_filtered" in changes and row.kind != "library":
        reasons.append("The tier filter applies to library checklists only")
    if changes.get("active") is False and row.active:
        listing = _types_listing(db, code, active_only=True)
        if listing:
            raise Conflict("Checklist is in use", check_checklist_deactivation(code, listing))
    _refuse("Invalid checklist", reasons)
    if "label" in changes:
        changes["label"] = changes["label"].strip() or code
    _set(row, changes)
    db.flush()
    _audit(db, user, "checklists", code, "updated", before, _pick(row, CHECKLIST_FIELDS))


def delete_checklist(db: Session, user: User, code: str) -> None:
    """Delete a custom checklist that has no items and no project type."""
    row = _checklist_row(db, code)
    if row.is_builtin:
        raise Conflict("Built-in checklist", [f"'{code}' is built in and cannot be deleted"])
    items = int(
        db.scalar(select(func.count()).select_from(PlaybookItem).where(PlaybookItem.source == code))
        or 0
    )
    reasons = []
    if items:
        reasons.append(f"It still has {items} items - deactivate the checklist instead")
    listing = _types_listing(db, code)
    if listing:
        reasons.append(f"Listed by project types: {', '.join(listing)}")
    if reasons:
        raise Conflict("Checklist is in use", reasons)
    before = _pick(row, CHECKLIST_FIELDS)
    db.delete(row)
    db.flush()
    _audit(db, user, "checklists", code, "deleted", before, None)


def _short_prefix(code: str) -> str:
    """Item ids are at most 20 characters: a long checklist code is shortened to its initials."""
    if len(code) <= 12:
        return code
    return "".join(part[0] for part in code.split("_") if part) or code[:12]


def create_playbook_item(db: Session, user: User, body: dto.PlaybookItemCreateIn) -> PlaybookItem:
    """New library item in ANY checklist; affects NEW transitions only."""
    checklist = db.get(Checklist, body.source)
    reasons: list[str] = []
    if checklist is None:
        raise NotFound(f"Checklist '{body.source}' not found")
    if not checklist.active:
        reasons.append(f"Checklist '{body.source}' is inactive")
    if checklist.kind == "portfolio_golden":
        if not body.portfolio or db.get(Portfolio, body.portfolio) is None:
            reasons.append("Pick the portfolio this golden-set item belongs to")
    elif body.portfolio:
        reasons.append("Only portfolio golden-set items belong to a portfolio")
    if body.gate not in GATES:
        reasons.append(f"Unknown gate '{body.gate}'")
    tiers = cfg.tier_numbers(db)
    if any(t not in tiers for t in body.applicable_tiers):
        reasons.append(f"Applicable tiers must be within {tiers[0]}..{tiers[-1]}")
    owner = body.default_owner_role
    if owner and (cfg.role(db, owner) is None or not cfg.role(db, owner).active):  # type: ignore[union-attr]
        reasons.append(f"Unknown or inactive role '{owner}'")
    for code in body.applies_to_project_types:
        if cfg.project_type(db, code) is None:
            reasons.append(f"Unknown project type '{code}'")
    item_id = body.id or next_item_id(db, body.source)
    if db.get(PlaybookItem, item_id) is not None:
        raise Conflict(f"Item {item_id} already exists", [f"Item id '{item_id}' is already used"])
    _refuse("Invalid playbook item", reasons)
    row = PlaybookItem(
        id=item_id,
        source=body.source,
        source_label=checklist.label,
        portfolio=body.portfolio,
        title=body.title,
        description=body.description,
        detail=body.detail,
        gate=body.gate,
        lens=body.lens,
        secondary_lens=body.secondary_lens,
        category=body.category,
        kind=body.kind or "Deliverable",
        applicable_tiers=sorted(set(body.applicable_tiers)),
        mandatory=body.mandatory,
        mandatory_rule=body.mandatory_rule if body.mandatory else None,
        applies_to_project_types=list(dict.fromkeys(body.applies_to_project_types)),
        owner_role_hint=body.owner_role_hint,
        default_owner_role=owner,
        linked_module=body.linked_module,
        is_compliance_control=body.lens == "Compliance",
        active=True,
        sort_order=int(
            db.scalar(
                select(func.coalesce(func.max(PlaybookItem.sort_order), -1)).where(
                    PlaybookItem.source == body.source
                )
            )
            + 1
        ),
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        user,
        "playbook_items",
        item_id,
        "created",
        None,
        _pick(row, ("source", "title", "gate", "lens", "portfolio", "mandatory")),
    )
    return row


def next_item_id(db: Session, source: str) -> str:
    """The next free "<PREFIX>-NNN" id for a checklist."""
    prefix = _short_prefix(source)
    existing = db.scalars(select(PlaybookItem.id).where(PlaybookItem.id.like(f"{prefix}-%"))).all()
    numbers = [int(i[len(prefix) + 1 :]) for i in existing if i[len(prefix) + 1 :].isdigit()]
    return f"{prefix}-{(max(numbers) + 1 if numbers else 1):03d}"


# =========================================================================== portfolios

PORTFOLIO_FIELDS = (
    "code",
    "label",
    "description",
    "focus_areas",
    "active",
    "sort_order",
    "requires_sites",
    "sites_label",
    "synonyms",
)


def _portfolio_row(db: Session, name: str) -> Portfolio:
    row = db.get(Portfolio, name)
    if row is None:
        raise NotFound(f"Portfolio '{name}' not found")
    return row


def _check_portfolio_code(db: Session, code: str, own_name: str | None) -> list[str]:
    clash = [
        p.name
        for p in cfg.portfolios(db, active_only=False)
        if p.code.lower() == code.lower() and p.name != own_name
    ]
    return [f"The code '{code}' is already used by portfolio '{clash[0]}'"] if clash else []


def create_portfolio(db: Session, user: User, body: dto.PortfolioCreateIn) -> str:
    """New portfolio; add its golden set afterwards with PUT /admin/portfolios/{name}/golden-set."""
    name = body.name.strip()
    if any(p.name.lower() == name.lower() for p in cfg.portfolios(db, active_only=False)):
        raise Conflict(f"Portfolio '{name}' already exists", [f"'{name}' already exists"])
    reasons = _check_portfolio_code(db, body.code, None)
    if URL_UNSAFE.search(name):
        reasons.append("A portfolio name cannot contain / % ? or #")
    reasons += check_reserved_words("Label", body.label)
    _refuse("Invalid portfolio", reasons)
    row = Portfolio(
        name=name,
        code=body.code.strip(),
        focus_areas=_clean(body.focus_areas),
        intake_extra_fields=[],
        label=body.label.strip() or name,
        description=body.description,
        active=True,
        sort_order=_next_sort(db, Portfolio.sort_order),
        requires_sites=body.requires_sites,
        sites_label=body.sites_label,
        synonyms=_clean(body.synonyms),
    )
    db.add(row)
    db.flush()
    _audit(db, user, "portfolios", name, "created", None, _pick(row, PORTFOLIO_FIELDS))
    return name


def update_portfolio(db: Session, user: User, name: str, body: dto.PortfolioUpdateIn) -> None:
    row = _portfolio_row(db, name)
    changes = {k: v for k, v in _changes(body).items() if v is not None}
    before = _pick(row, PORTFOLIO_FIELDS)
    reasons: list[str] = []
    if "code" in changes:
        reasons += _check_portfolio_code(db, changes["code"], name)
    reasons += check_reserved_words("Label", changes.get("label", ""))
    if changes.get("active") is False and row.active:
        others = [p for p in cfg.portfolios(db) if p.name != name]
        reasons += check_keep_one_active("portfolio", len(others))
    _refuse("Invalid portfolio", reasons)
    for key in ("focus_areas", "synonyms"):
        if key in changes:
            changes[key] = _clean(changes[key])
    if "label" in changes:
        changes["label"] = changes["label"].strip() or name
    _set(row, changes)
    db.flush()
    _audit(db, user, "portfolios", name, "updated", before, _pick(row, PORTFOLIO_FIELDS))


def delete_portfolio(db: Session, user: User, name: str) -> None:
    """Delete a portfolio no transition uses, together with its golden set."""
    row = _portfolio_row(db, name)
    n = _used_transitions(db, Transition.portfolio, name)
    if n:
        raise _used_by_conflict(f"Portfolio '{name}'", n)
    if row.active:
        _refuse(
            "Invalid portfolio", check_keep_one_active("portfolio", len(cfg.portfolios(db)) - 1)
        )
    before = _pick(row, PORTFOLIO_FIELDS)
    db.execute(
        delete(PlaybookItem).where(
            PlaybookItem.source == "PORTFOLIO", PlaybookItem.portfolio == name
        )
    )
    db.delete(row)
    db.flush()
    _audit(db, user, "portfolios", name, "deleted", before, None)


# =========================================================================== option lists


def _list_row(db: Session, key: str) -> OptionList:
    row = db.get(OptionList, key)
    if row is None:
        raise NotFound(f"Option list '{key}' not found")
    return row


def create_option_list(db: Session, user: User, body: dto.OptionListCreateIn) -> str:
    """New custom list (used by custom fields of type select / multiselect)."""
    if db.get(OptionList, body.key) is not None:
        raise Conflict(f"List '{body.key}' already exists", [f"'{body.key}' already exists"])
    row = OptionList(
        key=body.key,
        label=body.label.strip() or body.key,
        description=body.description,
        is_builtin=False,
        structural=False,
        meta_fields=[m.model_dump() for m in body.meta_fields],
        group=body.group or "Custom lists",
        sort_order=_next_sort(db, OptionList.sort_order),
    )
    db.add(row)
    db.flush()
    _audit(db, user, "option_lists", row.key, "created", None, _pick(row, ("label", "group")))
    return row.key


def update_option_list(db: Session, user: User, key: str, body: dto.OptionListUpdateIn) -> None:
    """Edit label, description, group, meta columns; a structural list accepts label and description only."""
    row = _list_row(db, key)
    changes = {k: v for k, v in _changes(body).items() if v is not None}
    if row.structural and set(changes) - {"label", "description"}:
        raise BadRequest("Locked list", [STRUCTURAL_REASON])
    if "meta_fields" in changes:
        changes["meta_fields"] = [m.model_dump() for m in body.meta_fields or []]
    fields = ("label", "description", "group", "meta_fields")
    before = _pick(row, fields)
    _set(row, changes)
    db.flush()
    _audit(db, user, "option_lists", key, "updated", before, _pick(row, fields))


def delete_option_list(db: Session, user: User, key: str) -> None:
    """Delete a custom list no field uses."""
    row = _list_row(db, key)
    if row.is_builtin or row.structural:
        raise Conflict("Built-in list", [f"'{key}' is built in and cannot be deleted"])
    users = [
        f.label for f in cfg.intake_fields(db, form=None, active_only=False) if f.option_list == key
    ]
    if users:
        raise Conflict("List is in use", [f"Used by the fields: {', '.join(users)}"])
    db.execute(delete(OptionItem).where(OptionItem.list_key == key))
    before = _pick(row, ("label", "group"))
    db.delete(row)
    db.flush()
    _audit(db, user, "option_lists", key, "deleted", before, None)


def _items_snapshot(items: Sequence[OptionItem]) -> list[dict[str, Any]]:
    return [{"value": i.value, "label": i.label, "active": i.active} for i in items]


def _check_critical_kept(
    db: Session, existing: Mapping[str, OptionItem], submitted: Sequence[Any]
) -> list[str]:
    """The critical severity cannot be switched off, removed or recoded while a gap holds it: those
    gaps would silently stop counting as critical. (Moving the critical flag to another value is an
    explicit choice and stays allowed.)"""
    used = read.option_usage(db, "severities")
    kept = {i.value.strip(): i for i in submitted}
    reasons: list[str] = []
    for value, row in existing.items():
        if not (row.meta or {}).get("counts_as_critical") or not used.get(value):
            continue
        now = kept.get(value)
        if now is None or not now.active:
            reasons.append(
                f"'{value}' is the critical severity and {used[value]} gaps hold it: "
                "only its label can change (or move the critical flag to another value)"
            )
    return reasons


def put_option_items(db: Session, user: User, key: str, body: dto.OptionItemsIn) -> list[str]:
    """Replace the ordered values of a list; returns warnings (values that were deactivated).

    A used value that is missing or sent inactive is DEACTIVATED, an unused one is removed. Values
    never change: a new spelling is a new value."""
    ol = _list_row(db, key)
    existing = {
        i.value: i for i in db.scalars(select(OptionItem).where(OptionItem.list_key == key))
    }
    submitted = [(i.value.strip(), i.active, i.meta) for i in body.items]
    values = [v for v, _, _ in submitted]
    reasons: list[str] = []
    if len({v.lower() for v in values}) != len(values):
        reasons.append(
            "A value appears twice in the list (capital letters do not make it different)"
        )
    reasons += check_structural_items(
        ol.structural, {v: (r.active, r.meta or {}) for v, r in existing.items()}, submitted
    )
    if not ol.structural:
        role_codes = [r.code for r in cfg.roles(db, active_only=False)]
        for item in body.items:
            reasons += check_item_meta(ol.meta_fields or [], item.meta, role_codes)
        if key == "severities":
            reasons += check_one_critical([(i.active, i.meta) for i in body.items])
            reasons += _check_critical_kept(db, existing, body.items)
        if ol.is_builtin and not any(i.active for i in body.items):
            reasons += [f"{ol.label or key}: at least one value must stay active"]
    if key == "evidence_types":
        for item in body.items:
            needs = item.meta.get("needs")
            if needs and needs not in EVIDENCE_NEEDS:
                reasons.append(f"'{item.value}': needs must be one of {', '.join(EVIDENCE_NEEDS)}")
    _refuse("Invalid list", reasons)

    before = _items_snapshot(sorted(existing.values(), key=lambda i: i.sort_order))
    used = read.option_usage(db, key)
    can_delete = read.usage_is_tracked(db, key)
    warnings: list[str] = []
    for position, item in enumerate(body.items):
        value = item.value.strip()
        row = existing.get(value)
        if row is None:
            db.add(
                OptionItem(
                    list_key=key,
                    value=value,
                    label=item.label.strip() or value,
                    description=item.description,
                    meta=dict(item.meta),
                    active=item.active,
                    sort_order=position,
                )
            )
            continue
        row.label = item.label.strip() or value
        row.description = item.description
        if not ol.structural:
            row.meta = dict(item.meta)
            row.sort_order = position
            if row.active and not item.active and used.get(value):
                warnings.append(
                    f"'{value}' is used by {used[value]} records: it is hidden from new records only"
                )
            row.active = item.active
    if not ol.structural:
        for value, row in existing.items():
            if value in values:
                continue
            if can_delete and not used.get(value):
                db.delete(row)
            else:
                row.active = False
                warnings.append(
                    f"'{value}' is in use (or cannot be checked): deactivated, not removed"
                )
    db.flush()
    after = _items_snapshot(
        list(
            db.scalars(
                select(OptionItem).where(OptionItem.list_key == key).order_by(OptionItem.sort_order)
            )
        )
    )
    _audit(db, user, "option_lists", key, "updated", {"items": before}, {"items": after})
    return warnings


# =========================================================================== intake fields

FIELD_FIELDS = (
    "label",
    "help",
    "type",
    "option_list",
    "visible",
    "required_mode",
    "required_for_project_types",
    "applies_to_project_types",
    "applies_to_portfolios",
    "section",
    "sort_order",
    "show_on_overview",
    "filterable",
    "form",
    "min",
    "max",
    "max_length",
    "active",
)
BUILTIN_EDITABLE = {"label", "help", "visible"}


def _field_row(db: Session, key: str) -> IntakeField:
    row = db.get(IntakeField, key)
    if row is None:
        raise NotFound(f"Field '{key}' not found")
    return row


def slug_key(label: str, taken: Collection[str]) -> str:
    """``cf_<slug>`` from a label, made unique with a numeric suffix."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:34] or "field"
    if not slug[0].isalpha():
        slug = f"f_{slug}"
    key, n = f"cf_{slug}", 2
    while key in taken:
        key, n = f"cf_{slug}_{n}", n + 1
    return key


def _check_field_settings(
    db: Session,
    type_: str,
    option_list: str | None,
    required_mode: str,
    required_types: Sequence[str],
    applies_types: Sequence[str],
    applies_portfolios: Sequence[str],
    minimum: float | None,
    maximum: float | None,
    max_length: int | None,
) -> list[str]:
    reasons: list[str] = []
    if type_ in ("select", "multiselect"):
        if not option_list or not cfg.option_list_exists(db, option_list):
            reasons.append("Pick the dropdown list this field offers")
    elif type_ == "user":
        if option_list and cfg.role(db, option_list) is None:
            reasons.append(f"Unknown role '{option_list}'")
    elif option_list:
        reasons.append("Only dropdown and people fields use a list")
    if type_ != "number" and (minimum is not None or maximum is not None):
        reasons.append("Minimum and maximum are for number fields")
    if minimum is not None and maximum is not None and minimum > maximum:
        reasons.append("The minimum is above the maximum")
    if max_length is not None and type_ not in ("text", "textarea"):
        reasons.append("Maximum length is for text fields")
    if required_mode == "by_project_type" and not required_types:
        reasons.append("Pick the project types that require this field")
    for code in [*required_types, *applies_types]:
        if cfg.project_type(db, code) is None:
            reasons.append(f"Unknown project type '{code}'")
    for name in applies_portfolios:
        if cfg.portfolio(db, name) is None:
            reasons.append(f"Unknown portfolio '{name}'")
    return reasons


def create_intake_field(db: Session, user: User, body: dto.IntakeFieldCreateIn) -> str:
    """New custom field; its value is stored on the transition (``custom_fields``)."""
    taken = {f.key for f in db.scalars(select(IntakeField))}
    key = body.key or slug_key(body.label, taken)
    reasons = check_custom_field_key(key, taken)
    reasons += _check_field_settings(
        db,
        body.type,
        body.option_list,
        body.required_mode,
        body.required_for_project_types,
        body.applies_to_project_types,
        body.applies_to_portfolios,
        body.min,
        body.max,
        body.max_length,
    )
    _refuse("Invalid field", reasons)
    row = IntakeField(
        key=key,
        label=body.label.strip(),
        help=body.help,
        builtin=False,
        structural=False,
        type=body.type,
        option_list=body.option_list,
        visible=True,
        required_mode="never",
        required_for_project_types=[],
        applies_to_project_types=list(dict.fromkeys(body.applies_to_project_types)),
        applies_to_portfolios=list(dict.fromkeys(body.applies_to_portfolios)),
        section=body.section or "Additional details",
        sort_order=_next_sort(db, IntakeField.sort_order),
        show_on_overview=body.show_on_overview,
        filterable=body.filterable,
        form=body.form,
        min=body.min,
        max=body.max,
        max_length=body.max_length,
        active=True,
    )
    db.add(row)
    db.flush()
    write_field_requirements(db, row, body.required_mode, body.required_for_project_types)
    db.flush()
    _audit(db, user, "intake_fields", key, "created", None, _pick(row, FIELD_FIELDS))
    return key


# Built-in fields the tier rules read: hiding them would stop AI transitions from being tiered.
TIER_INPUT_FIELDS = ("audience", "write_actions", "sensitive_data")


def _check_field_not_needed(db: Session, row: IntakeField) -> list[str]:
    """A field that is required (always, or for a project type) or read by the tier rules cannot be
    hidden: the form could not show it while the server still asks for it. (Retiring a custom
    field is allowed: it stops being required, see ``update_intake_field``.)"""
    reasons: list[str] = []
    if row.required_mode == "always":
        reasons.append(f"'{row.label}' is required for every project: make it optional first")
    types = [
        rule.label or rule.project_type
        for rule in db.scalars(select(FlavourRule))
        if rule.active and row.key in (rule.required_intake_fields or [])
    ]
    if types:
        reasons.append(
            f"'{row.label}' is required for {', '.join(types)}: remove the requirement first"
        )
    if row.key in TIER_INPUT_FIELDS:
        reasons.append(f"'{row.label}' is used to work out the tier and must stay on the form")
    return reasons


def update_intake_field(db: Session, user: User, key: str, body: dto.IntakeFieldUpdateIn) -> None:
    """Edit a field. Built-in fields: label, help and (optional ones) visibility. Custom fields: all
    settings, but the type is fixed once a transition holds a value."""
    row = _field_row(db, key)
    changes = {
        k: v
        for k, v in _changes(body).items()
        if v is not None or k in ("min", "max", "max_length")
    }
    before = _pick(row, FIELD_FIELDS)
    reasons: list[str] = []
    if row.builtin and set(changes) - BUILTIN_EDITABLE:
        reasons.append(BUILTIN_FIELD_REASON)
    if row.structural and (changes.get("visible") is False or changes.get("active") is False):
        reasons.append(f"'{row.label}' is always on the form and cannot be hidden")
    if "label" in changes and not changes["label"].strip():
        reasons.append("The label cannot be empty")
    if changes.get("visible") is False:
        reasons += _check_field_not_needed(db, row)
    used = read.custom_field_usage(db).get(key, 0)
    if "type" in changes:
        reasons += check_field_type_change(row.type, changes["type"], used)
    _refuse("Invalid field", reasons)
    if not row.builtin:
        merged = {**{f: getattr(row, f) for f in FIELD_FIELDS}, **changes}
        reasons = _check_field_settings(
            db,
            merged["type"],
            merged["option_list"],
            merged["required_mode"],
            merged["required_for_project_types"],
            merged["applies_to_project_types"],
            merged["applies_to_portfolios"],
            merged["min"],
            merged["max"],
            merged["max_length"],
        )
        _refuse("Invalid field", reasons)
    if "label" in changes:
        changes["label"] = changes["label"].strip()
    mode = changes.pop("required_mode", None)
    types = changes.pop("required_for_project_types", None)
    if changes.get("active") is False and not row.builtin:
        mode, types = "never", []  # a retired field is no longer required anywhere
    _set(row, changes)
    if mode is not None or types is not None:
        write_field_requirements(
            db,
            row,
            mode or row.required_mode,
            types if types is not None else (row.required_for_project_types or []),
        )
    db.flush()
    _audit(db, user, "intake_fields", key, "updated", before, _pick(row, FIELD_FIELDS))


def order_intake_fields(db: Session, user: User, body: dto.IntakeFieldOrderIn) -> None:
    """Set the form order: every field key exactly once."""
    rows = {f.key: f for f in db.scalars(select(IntakeField))}
    reasons = check_same_ids("field", rows, body.keys)
    _refuse("Invalid field order", reasons)
    before = {k: r.sort_order for k, r in rows.items()}
    for position, key in enumerate(body.keys):
        rows[key].sort_order = position
    db.flush()
    _audit(
        db,
        user,
        "intake_fields",
        "order",
        "updated",
        {"order": before},
        {"order": {k: r.sort_order for k, r in rows.items()}},
    )


def delete_intake_field(db: Session, user: User, key: str) -> None:
    """Delete an unused custom field (a used one is deactivated instead)."""
    row = _field_row(db, key)
    if row.builtin:
        raise Conflict("Built-in field", [f"'{row.label}' is built in and cannot be deleted"])
    used = read.custom_field_usage(db).get(key, 0)
    if used:
        raise _used_by_conflict(f"Field '{row.label}'", used)
    before = _pick(row, FIELD_FIELDS)
    write_field_requirements(db, row, "never", [])
    db.delete(row)
    db.flush()
    _audit(db, user, "intake_fields", key, "deleted", before, None)


# =========================================================================== roles and users

ROLE_FIELDS = ("label", "short_label", "phrase_label", "description")
USER_FIELDS = ("name", "email", "role", "focal_label", "title", "active")


def update_role(db: Session, user: User, code: str, body: dto.RoleUpdateIn) -> None:
    """Rename one of the eight roles (label, short label, phrase, description)."""
    row = db.get(Role, code)
    if row is None:
        raise NotFound(f"Role '{code}' not found")
    changes = {k: v for k, v in _changes(body).items() if v is not None}
    _refuse(
        "Invalid role",
        check_reserved_words(
            "Role name",
            *(changes[k] for k in ("label", "short_label", "phrase_label") if k in changes),
        ),
    )
    if "label" in changes and not changes["label"].strip():
        raise BadRequest("Invalid role", ["The label cannot be empty"])
    before = _pick(row, ROLE_FIELDS)
    _set(row, changes)
    db.flush()
    _audit(db, user, "roles", code, "updated", before, _pick(row, ROLE_FIELDS))


def _user_row(db: Session, user_id: str) -> User:
    row = db.get(User, user_id)
    if row is None:
        raise NotFound(f"User '{user_id}' not found")
    return row


def _all_users(db: Session) -> list[tuple[str, str, bool]]:
    return [(u.id, u.role, bool(u.active)) for u in db.scalars(select(User))]


def _check_user_fields(
    db: Session, name: str | None, email: str | None, role: str | None, own_id: str | None
) -> list[str]:
    reasons: list[str] = []
    if name is not None:
        reasons += check_reserved_words("Name", name)
    if email is not None:
        if not EMAIL.match(email):
            reasons.append(f"'{email}' is not an e-mail address")
        elif db.scalar(
            select(User.id).where(
                func.lower(User.email) == email.lower(), User.id != (own_id or "")
            )
        ):
            reasons.append(f"The e-mail '{email}' is already used by another user")
    if role is not None:
        found = cfg.role(db, role)
        if found is None or not found.active:
            reasons.append(f"'{role}' is not an active role")
    return reasons


def _open_slots(db: Session, person: User) -> tuple[str | None, list[Transition]]:
    """(transition column for the person's role, their open transitions in that column)."""
    column = access.TRANSITION_ROLE_COLUMN.get(person.role)
    if not column:
        return None, []
    rows = db.scalars(
        select(Transition).where(
            getattr(Transition, column) == person.id, Transition.status != "Closed"
        )
    )
    return column, list(rows)


def create_user(db: Session, user: User, body: dto.UserCreateIn) -> str:
    """New user (next id U17, U18 ...). The role must be one of the active roles."""
    reasons = _check_user_fields(db, body.name, body.email, body.role, None)
    reasons += check_reserved_words("Label", body.focal_label or "", body.title or "")
    _refuse("Invalid user", reasons)
    row = User(
        id=next_id(db, User.id, "U"),
        name=body.name.strip(),
        email=body.email.strip(),
        role=body.role,
        focal_label=body.focal_label,
        title=body.title,
        active=True,
    )
    db.add(row)
    db.flush()
    _audit(db, user, "users", row.id, "created", None, _pick(row, USER_FIELDS))
    return row.id


def update_user(db: Session, actor: User, user_id: str, body: dto.UserUpdateIn) -> None:
    """Edit a person. ``active=true`` re-activates; switching off goes through ``deactivate_user``."""
    row = _user_row(db, user_id)
    changes = {k: v for k, v in _changes(body).items() if v is not None}
    reasons = _check_user_fields(
        db, changes.get("name"), changes.get("email"), changes.get("role"), user_id
    )
    reasons += check_reserved_words(
        "Label", changes.get("focal_label") or "", changes.get("title") or ""
    )
    if changes.get("active") is False:
        reasons.append("Use 'Deactivate' to switch a person off (it can reassign their work)")
    if "role" in changes and changes["role"] != row.role:
        _, slots = _open_slots(db, row)
        if slots:
            names = ", ".join(t.id for t in slots[:5])
            reasons.append(
                f"{row.name} is assigned on {len(slots)} open transitions ({names}): "
                "give those transitions to someone else (Deactivate and reassign) before changing the role"
            )
    if "role" in changes:
        reasons += check_user_role_change(
            user_id, actor.id, changes["role"], _all_users(db), permissions.roles_with(Perm.ADMIN)
        )
    _refuse("Invalid user", reasons)
    before = _pick(row, USER_FIELDS)
    _set(row, changes)
    db.flush()
    _audit(db, actor, "users", user_id, "updated", before, _pick(row, USER_FIELDS))


def deactivate_user(
    db: Session, actor: User, user_id: str, reassign_to: str | None
) -> tuple[int, int, list[str]]:
    """Switch a person off (never delete) and optionally hand their slots on active transitions to
    ``reassign_to`` in the same audited action. Returns (assigned, reassigned, warnings)."""
    row = _user_row(db, user_id)
    if not row.active:
        raise Conflict("Already inactive", [f"{row.name} is already inactive"])
    reasons = check_user_deactivation(
        user_id, actor.id, _all_users(db), permissions.roles_with(Perm.ADMIN)
    )
    _refuse("Cannot deactivate", reasons)
    column, slots = _open_slots(db, row)
    if slots and not reassign_to:
        raise BadRequest(
            "Choose who takes over",
            [
                f"{row.name} is assigned on {len(slots)} open transitions: "
                "pick a replacement with the same role"
            ],
        )
    target = None
    if reassign_to:
        target = db.get(User, reassign_to)
        if target is None or not target.active or target.role != row.role or target.id == user_id:
            raise BadRequest(
                "Invalid replacement",
                ["The replacement must be another active user with the same role"],
            )
    before = _pick(row, USER_FIELDS)
    row.active = False
    warnings: list[str] = []
    moved = 0
    for t in slots:
        if target is not None and column:
            audit.record(
                db,
                actor=actor,
                actor_type=ACTOR_HUMAN,
                entity="Transition",
                entity_id=t.id,
                transition_id=t.id,
                action="reassigned",
                before={column: user_id},
                after={column: target.id},
                note=f"{row.name} was deactivated; {target.name} takes over",
            )
            setattr(t, column, target.id)
            moved += 1
    db.flush()
    _audit(
        db,
        actor,
        "users",
        user_id,
        "deactivated",
        before,
        {**_pick(row, USER_FIELDS), "reassigned_to": reassign_to, "reassigned": moved},
    )
    return len(slots), moved, warnings


# =========================================================================== permissions


def put_permissions(db: Session, user: User, body: dto.PermissionsPutIn) -> None:
    """Replace the permission grid and, optionally, the permission wording.

    A denial text that nobody edited is regenerated from the role names, so it never names a role
    that lost the right. Takes effect at once (the router clears the permission cache)."""
    perm_codes = [p.value for p in Perm]
    role_codes = [r.code for r in cfg.roles(db)]
    active_roles = {u.role for u in db.scalars(select(User).where(User.active.is_(True)))}
    reasons = check_permission_matrix(body.matrix, perm_codes, role_codes, active_roles)
    reasons += check_reserved_words(
        "Permission name", *(t.label for t in body.texts.values() if t.label)
    )
    for perm in body.texts:
        if perm not in perm_codes:
            reasons.append(f"Unknown permission '{perm}'")
    _refuse("Invalid permissions", reasons)

    before = read.permission_matrix_out(db)
    old = {row.perm: [r for r in row.roles] for row in before.permissions}
    db.execute(delete(RolePermission))
    for perm, roles in body.matrix.items():
        for code in sorted(set(roles)):
            db.add(RolePermission(perm=perm, role_code=code))
    texts = {t.perm: t for t in db.scalars(select(PermissionText))}
    for perm in Perm:
        roles = sorted(set(body.matrix[perm.value]), key=role_codes.index)
        generated = read.default_denial_text(db, perm, roles)
        row = texts.get(perm.value)
        if row is None:
            row = PermissionText(perm=perm.value, label=perm.value)
            db.add(row)
        edit = body.texts.get(perm.value)
        if edit and edit.label:
            row.label = edit.label
        if edit and edit.description is not None:
            row.description = edit.description
        wanted = edit.denial_reason if edit and edit.denial_reason else None
        if wanted and wanted != generated:
            row.denial_reason, row.is_custom = wanted, True
        elif wanted == generated or not row.is_custom:
            row.denial_reason, row.is_custom = generated, False
    db.flush()
    changed = {
        p: roles for p, roles in body.matrix.items() if sorted(old.get(p, [])) != sorted(roles)
    }
    _audit(
        db,
        user,
        "permissions",
        "matrix",
        "updated",
        {"matrix": {p: old.get(p, []) for p in changed}},
        {"matrix": {p: sorted(r) for p, r in changed.items()}, "texts_edited": sorted(body.texts)},
    )


# =========================================================================== tiering and thresholds


def put_tiering(db: Session, user: User, body: dto.TieringConfigIn) -> None:
    """New wording for the tier definitions and the tiering questions (BR-011 itself stays in code)."""
    tiers = cfg.tiers(db)
    questions = {q.id: q for q in db.scalars(select(TierQuestion))}
    reasons = check_same_ids("Tier", [t["tier"] for t in tiers], [t.tier for t in body.tiers])
    reasons += check_same_ids("Question", list(questions), [q.id for q in body.questions])
    _refuse("Invalid tiering", reasons)
    before = {
        "tiers": tiers,
        "questions": {k: {"text": q.text, "hint": q.hint} for k, q in questions.items()},
    }
    new_tiers = [t.model_dump() for t in sorted(body.tiers, key=lambda t: t.tier)]
    setting = db.get(AppSetting, "cfg.tiers")
    if setting is None:
        db.add(AppSetting(key="cfg.tiers", value=new_tiers))
    else:
        setting.value = new_tiers
    for q in body.questions:
        questions[q.id].text = q.text
        questions[q.id].hint = q.hint
    db.flush()
    after = {
        "tiers": new_tiers,
        "questions": {q.id: {"text": q.text, "hint": q.hint} for q in body.questions},
    }
    _audit(db, user, "tiering", "tiering", "updated", before, after)


def put_thresholds(db: Session, user: User, body: dto.ThresholdsIn) -> None:
    """Save the RAG numbers and the other thresholds; applies to all active transitions at once."""
    doc = body.thresholds.model_dump()
    reasons = check_thresholds(
        doc,
        cfg.tier_numbers(db),
        cfg.option_values(db, "ocet_pricing_basis") or [doc["default_pricing_basis"]],
    )
    _refuse("Invalid thresholds", reasons)
    before = cfg.thresholds(db)
    setting = db.get(AppSetting, "cfg.thresholds")
    if setting is None:
        db.add(AppSetting(key="cfg.thresholds", value=doc))
    else:
        setting.value = doc
    db.flush()
    _audit(db, user, "thresholds", "thresholds", "updated", before, doc)


# =========================================================================== eval metrics


def _metric_rows(db: Session, metric_id: str) -> list[EvalTarget]:
    rows = list(db.scalars(select(EvalTarget).where(EvalTarget.metric_id == metric_id)))
    if not rows:
        raise NotFound(f"Eval metric '{metric_id}' not found")
    return rows


TARGET_TEXT = re.compile(r"^\s*(abs<=|>=|<=|==|<|>)\s*(-?\d+(?:\.\d+)?)\s*(\S*)\s*$")


def _parse_target(text: str) -> tuple[str, float, str] | None:
    """ "<= 5%" -> ("<=", 5.0, "%"); None when the text is not an operator and a number."""
    found = TARGET_TEXT.match(text)
    return (found.group(1), float(found.group(2)), found.group(3)) if found else None


def create_eval_metric(db: Session, user: User, body: dto.EvalMetricCreateIn) -> str:
    """New metric EV-nn with a target text per tier."""
    tiers = cfg.tier_numbers(db)
    reasons = check_same_ids("Tier target", [str(t) for t in tiers], list(body.targets_by_tier))
    parsed: dict[str, tuple[str, float, str] | None] = {}
    if body.evaluation == "auto" and (body.operator is None or body.value is None):
        # one text box per tier is enough: "<= 5%" gives the operator, the value and the unit
        for tier, text in body.targets_by_tier.items():
            parsed[tier] = _parse_target(text)
            if parsed[tier] is None:
                reasons.append(
                    f"Tier {tier} target '{text}': an automatic metric needs an operator and a "
                    "number, for example '<= 5%'"
                )
    if body.evaluation == "manual" and (body.operator or body.value is not None):
        reasons.append("Only automatic metrics have an operator and a value")
    _refuse("Invalid metric", reasons)
    metric_id = f"EV-{_next_metric_number(db):02d}"
    order = _next_sort(db, EvalTarget.sort_order)
    for tier in tiers:
        operator, value, unit = body.operator, body.value, body.unit
        found = parsed.get(str(tier))
        if found is not None:
            operator, value, unit = found[0], found[1], unit or found[2] or None
        db.add(
            EvalTarget(
                metric_id=metric_id,
                metric=body.metric.strip(),
                tier=tier,
                target_text=body.targets_by_tier[str(tier)],
                operator=operator,
                value=value,
                unit=unit,
                evaluation=body.evaluation,
                confirmed=False,
                active=True,
                sort_order=order,
            )
        )
    db.flush()
    _audit(
        db,
        user,
        "eval_metrics",
        metric_id,
        "created",
        None,
        {"metric": body.metric, "evaluation": body.evaluation, "targets": body.targets_by_tier},
    )
    return metric_id


def _next_metric_number(db: Session) -> int:
    ids = db.scalars(select(EvalTarget.metric_id).distinct()).all()
    numbers = [int(i[3:]) for i in ids if i.startswith("EV-") and i[3:].isdigit()]
    return (max(numbers) + 1) if numbers else 1


def update_eval_metric(
    db: Session, user: User, metric_id: str, body: dto.EvalMetricUpdateIn
) -> None:
    """Rename, change the unit, switch automatic / manual, or deactivate a metric (all tiers)."""
    rows = _metric_rows(db, metric_id)
    changes = {k: v for k, v in _changes(body).items() if v is not None or k == "unit"}
    reasons: list[str] = []
    if changes.get("evaluation") == "auto" and any(
        r.operator is None or r.value is None for r in rows
    ):
        reasons.append("This metric has no operator and value, so it cannot be automatic")
    _refuse("Invalid metric", reasons)
    fields = ("metric", "evaluation", "unit", "active")
    before = _pick(rows[0], fields)
    for row in rows:
        for name, value in changes.items():
            setattr(row, name, value)
    db.flush()
    _audit(db, user, "eval_metrics", metric_id, "updated", before, _pick(rows[0], fields))


# =========================================================================== message templates


def put_message_templates(db: Session, user: User, body: dto.MessageTemplatesPutIn) -> None:
    """Save the wording of Orion's drafts. Who receives a message and when it is sent are not part of
    a template, so they cannot change here."""
    reasons: list[str] = []
    keys = [t.key for t in body.templates]
    reasons += [
        f"Message '{k}' appears twice" for k in sorted({k for k in keys if keys.count(k) > 1})
    ]
    for t in body.templates:
        if t.key not in cfg_defaults.DEFAULT_TEMPLATES:
            reasons.append(f"Unknown message '{t.key}'")
            continue
        allowed = {p["name"] for p in cfg_defaults.placeholder_specs(t.key)}
        reasons += check_template(t.key, t.subject, t.body, allowed)
    _refuse("Invalid message templates", reasons)
    for t in body.templates:
        name = cfg_defaults.DEFAULT_TEMPLATES[t.key][0]
        row = db.get(MessageTemplate, t.key)
        old = cfg.template(db, t.key)
        before = {"subject": old.subject, "body": old.body, "enabled": old.enabled} if old else None
        if row is None:
            row = MessageTemplate(key=t.key, name=name)
            db.add(row)
        row.name = row.name or name
        row.subject, row.body, row.enabled = t.subject, t.body, t.enabled
        row.placeholders = cfg_defaults.placeholder_specs(t.key)
        after = {"subject": t.subject, "body": t.body, "enabled": t.enabled}
        if before != after:
            _audit(db, user, "message_templates", t.key, "updated", before, after)
    db.flush()
