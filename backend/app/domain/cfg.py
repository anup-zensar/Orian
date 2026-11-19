"""Runtime configuration service (CR-01 design 6): the READ API of everything an Admin can edit.

Callers use these helpers instead of constants::

    from app.domain import cfg
    cfg.project_type(db, "Security Review").has_ai_profile
    cfg.option_label(db, "severities", "Critical")
    cfg.validate_option(db, "evidence_types", value, current=row.type)

* Every function takes the SQLAlchemy ``db`` session first and returns plain, immutable data
  (frozen dataclasses, tuples, copies of dicts) - never ORM rows - so results can be cached.
* A section is read from the database once and kept in an in-process cache until ``invalidate()``.
  ``invalidate()`` is called by every admin writer, ``reset_and_seed`` / ``seed_if_empty`` and the
  ``fresh_seed`` test fixture. It also resets the permission cache of ``app.permissions``.
* When a table has no rows (empty or partly seeded database) the code defaults apply
  (``app.domain.cfg_defaults``: seed/config.json, code constants), so nothing crashes before seeding.
* Structural values (gate codes and order, the three lenses, status buckets, chain types,
  permission codes, reminder ids) are NOT here: they stay in code (``app.rules.constants``).
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import permissions
from app.domain import cfg_defaults as defaults
from app.errors import BadRequest
from app.models import (
    AppSetting,
    Checklist,
    FlavourRule,
    IntakeField,
    MessageTemplate,
    OptionItem,
    OptionList,
    Portfolio,
    Role,
    TierQuestion,
)

# --- value objects ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectTypeCfg:
    code: str
    label: str
    description: str
    checklists: tuple[str, ...]
    requires_tiering: bool
    has_ai_profile: bool
    has_eval_metrics: bool
    required_intake_fields: tuple[str, ...]
    synonyms: tuple[str, ...]
    note: str | None
    active: bool
    sort_order: int


@dataclass(frozen=True)
class PortfolioCfg:
    name: str
    code: str
    label: str
    description: str
    focus_areas: tuple[str, ...]
    requires_sites: bool
    sites_label: str
    synonyms: tuple[str, ...]
    active: bool
    sort_order: int


@dataclass(frozen=True)
class ChecklistDef:
    code: str
    label: str
    description: str
    kind: str  # library | portfolio_golden | common
    tier_filtered: bool
    is_builtin: bool
    active: bool
    sort_order: int


@dataclass(frozen=True)
class OptionCfg:
    value: str
    label: str  # never empty: falls back to the value
    description: str
    meta: dict[str, Any]
    active: bool
    sort_order: int


@dataclass(frozen=True)
class RoleCfg:
    code: str
    label: str
    short_label: str  # never empty
    phrase_label: str  # never empty (used inside sentences, e.g. "project manager")
    description: str
    active: bool
    is_builtin: bool
    has_transition_slot: bool
    transition_column: str | None
    can_approve: bool
    sort_order: int


@dataclass(frozen=True)
class IntakeFieldCfg:
    key: str
    label: str
    help: str
    builtin: bool
    structural: bool
    type: str  # text | textarea | number | date | select | multiselect | boolean | user
    option_list: str | None  # select: list key (or the virtual lists project_types / portfolios);
    # user: the role code whose users are offered
    visible: bool
    required_mode: str  # never | always | by_project_type
    required_for_project_types: tuple[str, ...]
    applies_to_project_types: tuple[str, ...]  # () = all
    applies_to_portfolios: tuple[str, ...]  # () = all
    section: str
    sort_order: int
    show_on_overview: bool
    filterable: bool
    form: str  # intake | ai_profile
    min: float | None
    max: float | None
    max_length: int | None
    active: bool


@dataclass(frozen=True)
class TierQuestionCfg:
    id: str
    text: str
    hint: str
    active: bool
    sort_order: int


@dataclass(frozen=True)
class RagThresholds:
    """BR-021 numbers. Red when critical >= red_critical_gaps, or a lens < red_lens_below, or
    (critical >= amber_critical_gaps and a decision within red_near_days). Amber when critical >=
    amber_critical_gaps or a lens < amber_lens_below."""

    red_critical_gaps: int = 2
    red_lens_below: int = 50
    red_near_days: int = 7
    amber_critical_gaps: int = 1
    amber_lens_below: int = 70


@dataclass(frozen=True)
class TemplateCfg:
    key: str
    name: str
    subject: str
    body: str
    enabled: bool
    placeholders: tuple[dict[str, Any], ...] = field(
        default_factory=tuple
    )  # {name, description, html}
    is_default: bool = True  # True = no row, the code default text


# --- cache --------------------------------------------------------------------------------------

_cache: dict[str, Any] = {}


def invalidate() -> None:
    """Drop every cached section (and the permission cache). Call after ANY configuration write."""
    _cache.clear()
    permissions.invalidate_cache()


def _section(name: str, load):
    if name not in _cache:
        _cache[name] = load()
    return _cache[name]


def _setting(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    return row.value if row is not None else None


def _merge(base: Mapping[str, Any], over: Any) -> dict[str, Any]:
    """Recursive dict merge (``over`` wins); non-dict ``over`` is ignored."""
    out: dict[str, Any] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    if isinstance(over, Mapping):
        for k, v in over.items():
            if isinstance(v, Mapping) and isinstance(out.get(k), dict):
                out[k] = _merge(out[k], v)
            else:
                out[k] = v
    return out


# --- project types and portfolios ---------------------------------------------------------------


def _project_type(row: FlavourRule) -> ProjectTypeCfg:
    return ProjectTypeCfg(
        code=row.project_type,
        label=row.label or row.project_type,
        description=row.description or "",
        checklists=tuple(row.checklists or ()),
        requires_tiering=bool(row.requires_tiering),
        has_ai_profile=bool(row.has_ai_profile),
        has_eval_metrics=bool(row.has_eval_metrics),
        required_intake_fields=tuple(row.required_intake_fields or ()),
        synonyms=tuple(row.synonyms or ()),
        note=row.note,
        active=bool(row.active),
        sort_order=int(row.sort_order or 0),
    )


def _all_project_types(db: Session) -> list[ProjectTypeCfg]:
    def load() -> list[ProjectTypeCfg]:
        rows = db.scalars(select(FlavourRule)).all()
        if rows:
            return sorted((_project_type(r) for r in rows), key=lambda p: (p.sort_order, p.code))
        return [
            ProjectTypeCfg(
                code=d["code"],
                label=d.get("label") or d["code"],
                description=d.get("description", ""),
                checklists=tuple(d.get("checklists", ())),
                requires_tiering=bool(d.get("requires_tiering", False)),
                has_ai_profile=bool(d.get("has_ai_profile", False)),
                has_eval_metrics=bool(d.get("has_eval_metrics", False)),
                required_intake_fields=tuple(d.get("required_intake_fields", ())),
                synonyms=tuple(d.get("synonyms", ())),
                note=d.get("note"),
                active=True,
                sort_order=int(d.get("sort_order", 0)),
            )
            for d in defaults.seed_config()["project_types"]
        ]

    return _section("project_types", load)


def project_types(db: Session, active_only: bool = True) -> list[ProjectTypeCfg]:
    """Project types ordered by ``sort_order``; inactive ones only with ``active_only=False``."""
    return [p for p in _all_project_types(db) if p.active or not active_only]


def project_type(db: Session, code: str | None) -> ProjectTypeCfg | None:
    """One project type by code (active or not); None when unknown."""
    return next((p for p in _all_project_types(db) if p.code == code), None)


def project_type_label(db: Session, code: str | None) -> str:
    found = project_type(db, code)
    return found.label if found else (code or "")


def _all_portfolios(db: Session) -> list[PortfolioCfg]:
    def load() -> list[PortfolioCfg]:
        rows = db.scalars(select(Portfolio)).all()
        return sorted(
            (
                PortfolioCfg(
                    name=r.name,
                    code=r.code,
                    label=r.label or r.name,
                    description=r.description or "",
                    focus_areas=tuple(r.focus_areas or ()),
                    requires_sites=bool(r.requires_sites),
                    sites_label=r.sites_label or "",
                    synonyms=tuple(r.synonyms or ()),
                    active=bool(r.active),
                    sort_order=int(r.sort_order or 0),
                )
                for r in rows
            ),
            key=lambda p: (p.sort_order, p.name),
        )

    return _section("portfolios", load)


def portfolios(db: Session, active_only: bool = True) -> list[PortfolioCfg]:
    return [p for p in _all_portfolios(db) if p.active or not active_only]


def portfolio(db: Session, name: str | None) -> PortfolioCfg | None:
    """One portfolio by name (active or not); None when unknown."""
    return next((p for p in _all_portfolios(db) if p.name == name), None)


def portfolio_label(db: Session, name: str | None) -> str:
    found = portfolio(db, name)
    return found.label if found else (name or "")


def portfolio_requires_sites(db: Session, name: str | None) -> bool:
    found = portfolio(db, name)
    return bool(found and found.requires_sites)


# --- checklists ---------------------------------------------------------------------------------


def checklist_defs(db: Session, active_only: bool = True) -> list[ChecklistDef]:
    """The checklist registry ordered by ``sort_order`` (default: the four built-ins)."""

    def load() -> list[ChecklistDef]:
        rows = db.scalars(select(Checklist)).all()
        raw = (
            [
                dict(
                    code=r.code,
                    label=r.label,
                    description=r.description,
                    kind=r.kind,
                    tier_filtered=r.tier_filtered,
                    is_builtin=r.is_builtin,
                    active=r.active,
                    sort_order=r.sort_order,
                )
                for r in rows
            ]
            if rows
            else defaults.seed_config()["checklists"]
        )
        return sorted(
            (
                ChecklistDef(
                    code=d["code"],
                    label=d.get("label") or d["code"],
                    description=d.get("description", ""),
                    kind=d.get("kind", "library"),
                    tier_filtered=bool(d.get("tier_filtered", False)),
                    is_builtin=bool(d.get("is_builtin", False)),
                    active=bool(d.get("active", True)),
                    sort_order=int(d.get("sort_order", 0)),
                )
                for d in raw
            ),
            key=lambda c: (c.sort_order, c.code),
        )

    return [c for c in _section("checklists", load) if c.active or not active_only]


# --- option lists -------------------------------------------------------------------------------


def _option_lists(db: Session) -> dict[str, dict[str, Any]]:
    """key -> {label, structural, meta_fields, items: [OptionCfg, ...] in order}."""

    def load() -> dict[str, dict[str, Any]]:
        lists = db.scalars(select(OptionList).order_by(OptionList.sort_order, OptionList.key)).all()
        if not lists:
            raw: dict[str, dict[str, Any]] = {
                d["key"]: {
                    "label": d.get("label", d["key"]),
                    "group": d.get("group", ""),
                    "structural": bool(d.get("structural", False)),
                    "meta_fields": d.get("meta_fields", []),
                    "items": [
                        dict(it, active=True, sort_order=i) for i, it in enumerate(d["items"])
                    ],
                }
                for d in defaults.seed_config()["option_lists"]
            }
        else:
            raw = {
                ol.key: {
                    "label": ol.label or ol.key,
                    "group": ol.group,
                    "structural": ol.structural,
                    "meta_fields": list(ol.meta_fields or []),
                    "items": [],
                }
                for ol in lists
            }
            for it in db.scalars(
                select(OptionItem).order_by(OptionItem.sort_order, OptionItem.id)
            ).all():
                if it.list_key in raw:
                    raw[it.list_key]["items"].append(
                        dict(
                            value=it.value,
                            label=it.label,
                            description=it.description,
                            meta=it.meta,
                            active=it.active,
                            sort_order=it.sort_order,
                        )
                    )
        return {
            key: {
                "label": data["label"],
                "group": data["group"],
                "structural": data["structural"],
                "meta_fields": data["meta_fields"],
                "items": [
                    OptionCfg(
                        value=it["value"],
                        label=it.get("label") or it["value"],
                        description=it.get("description", ""),
                        meta=dict(it.get("meta") or {}),
                        active=bool(it.get("active", True)),
                        sort_order=int(it.get("sort_order", 0)),
                    )
                    for it in data["items"]
                ],
            }
            for key, data in raw.items()
        }

    return _section("option_lists", load)


def option_list_keys(db: Session, group: str | None = None) -> list[str]:
    """Keys of every option list in editor order, optionally only those of one ``group``."""
    return [k for k, v in _option_lists(db).items() if group is None or v["group"] == group]


def option_list_exists(db: Session, key: str) -> bool:
    return key in _option_lists(db)


def option_list_label(db: Session, key: str) -> str:
    found = _option_lists(db).get(key)
    return found["label"] if found else key


def options(db: Session, key: str, active_only: bool = True) -> list[OptionCfg]:
    """The items of list ``key`` in order ([] for an unknown list)."""
    found = _option_lists(db).get(key)
    if not found:
        return []
    return [o for o in found["items"] if o.active or not active_only]


def option_values(db: Session, key: str, active_only: bool = True) -> list[str]:
    return [o.value for o in options(db, key, active_only)]


def _option(db: Session, key: str, value: str | None) -> OptionCfg | None:
    return next((o for o in options(db, key, active_only=False) if o.value == value), None)


def option_label(db: Session, key: str, value: str | None) -> str:
    """The display label of ``value`` (the value itself when the option is unknown)."""
    found = _option(db, key, value)
    return found.label if found else (value or "")


def evidence_type_for(db: Session, needs: str) -> str | None:
    """The first active, non-system evidence type whose ``needs`` is ``needs`` ("url", "text" ...).
    Orion uses it to pick the type for a pasted link or e-mail (None when the Admin has none)."""
    for o in options(db, "evidence_types"):
        if o.meta.get("needs") == needs and not o.meta.get("system"):
            return o.value
    return None


def option_meta(db: Session, key: str, value: str | None) -> dict[str, Any]:
    """A copy of the item's meta ({} when unknown)."""
    found = _option(db, key, value)
    return dict(found.meta) if found else {}


def validate_option(db: Session, key: str, value: str | None, current: str | None = None) -> None:
    """422 unless ``value`` is an ACTIVE option of list ``key``. An inactive (or since removed)
    value stays valid on an UNCHANGED existing record: pass the record's ``current`` value."""
    if value is None or value == "":
        raise BadRequest(f"{option_list_label(db, key)}: a value is required")
    if value == current:
        return
    if not option_list_exists(db, key):
        raise BadRequest(f"Unknown option list '{key}'")
    active = [o.value for o in options(db, key)]
    if value not in active:
        raise BadRequest(
            f"'{value}' is not an option of {option_list_label(db, key)}",
            [
                f"'{value}' is not an option of {option_list_label(db, key)} (use one of: {', '.join(active)})"
            ],
        )


def critical_severity(db: Session) -> str:
    """The gap severity that counts as critical (exactly one; default "Critical")."""
    for o in options(db, "severities"):
        if o.meta.get("counts_as_critical"):
            return o.value
    return defaults.DEFAULT_CRITICAL_SEVERITY


def owner_hints(db: Session) -> list[tuple[str, str]]:
    """Ordered (keyword, role code) pairs: a keyword in a library item's owner hint picks the role."""
    return [
        (o.value, str(o.meta.get("role_code") or ""))
        for o in options(db, "owner_hints")
        if o.meta.get("role_code")
    ]


# --- roles --------------------------------------------------------------------------------------


def _roles(db: Session) -> list[RoleCfg]:
    def load() -> list[RoleCfg]:
        rows = db.scalars(select(Role)).all()
        raw = (
            [
                dict(
                    code=r.code,
                    label=r.label,
                    short_label=r.short_label,
                    phrase_label=r.phrase_label,
                    description=r.description,
                    active=r.active,
                    is_builtin=r.is_builtin,
                    has_transition_slot=r.has_transition_slot,
                    transition_column=r.transition_column,
                    can_approve=r.can_approve,
                    sort_order=r.sort_order,
                )
                for r in rows
            ]
            if rows
            else defaults.seed_config()["roles"]
        )
        return sorted(
            (
                RoleCfg(
                    code=d["code"],
                    label=d.get("label") or d["code"],
                    short_label=d.get("short_label") or d.get("label") or d["code"],
                    phrase_label=d.get("phrase_label") or d.get("label") or d["code"],
                    description=d.get("description", ""),
                    active=bool(d.get("active", True)),
                    is_builtin=bool(d.get("is_builtin", False)),
                    has_transition_slot=bool(d.get("has_transition_slot", False)),
                    transition_column=d.get("transition_column"),
                    can_approve=bool(d.get("can_approve", False)),
                    sort_order=int(d.get("sort_order", 0)),
                )
                for d in raw
            ),
            key=lambda r: (r.sort_order, r.code),
        )

    return _section("roles", load)


def roles(db: Session, active_only: bool = True) -> list[RoleCfg]:
    return [r for r in _roles(db) if r.active or not active_only]


def role(db: Session, code: str | None) -> RoleCfg | None:
    return next((r for r in _roles(db) if r.code == code), None)


_MOCK_LABELS = {"CISO_BISO": "CISO/BISO"}


def role_label(db: Session, code: str | None) -> str:
    """Long label, e.g. "OR focal (S&T)" (the code for an unknown role; CISO/BISO for the mock)."""
    found = role(db, code)
    return found.label if found else _MOCK_LABELS.get(code or "", code or "")


def role_short_label(db: Session, code: str | None) -> str:
    """Short label used in approval steps and chips, e.g. "OR focal"."""
    found = role(db, code)
    return found.short_label if found else _MOCK_LABELS.get(code or "", code or "")


def role_phrase_label(db: Session, code: str | None) -> str:
    """Label used inside sentences ("Only Asha, the project manager of TR-0001, can ...")."""
    found = role(db, code)
    return found.phrase_label if found else _MOCK_LABELS.get(code or "", code or "")


def slot_roles(db: Session) -> list[RoleCfg]:
    """Active roles that hold a person on every transition (OR focal, PM, Architect, OLM, IRM and
    admin-created slot roles), in display order."""
    return [r for r in roles(db) if r.has_transition_slot]


# --- thresholds, approval chain settings --------------------------------------------------------


def thresholds(db: Session) -> dict[str, Any]:
    """``cfg.thresholds`` merged over the defaults (a fresh copy)."""
    merged = _section(
        "thresholds",
        lambda: _merge(defaults.DEFAULT_THRESHOLDS, _setting(db, "cfg.thresholds")),
    )
    return _merge(merged, {})


def rag_thresholds(db: Session) -> RagThresholds:
    rag = thresholds(db)["rag"]
    return RagThresholds(
        red_critical_gaps=int(rag["red_critical_gaps"]),
        red_lens_below=int(rag["red_lens_below"]),
        red_near_days=int(rag["red_near_days"]),
        amber_critical_gaps=int(rag["amber_critical_gaps"]),
        amber_lens_below=int(rag["amber_lens_below"]),
    )


def rag_rule_text(db: Session) -> dict[str, str]:
    """The ``rag_rule`` display text GENERATED from the numbers (cannot disagree with behaviour)."""
    t = rag_thresholds(db)
    return {
        "red": (
            f"critical_gaps >= {t.red_critical_gaps} OR min_lens_readiness < {t.red_lens_below} OR "
            f"(critical_gaps >= {t.amber_critical_gaps} AND days_to_next_decision <= {t.red_near_days})"
        ),
        "amber": (
            f"critical_gaps >= {t.amber_critical_gaps} OR min_lens_readiness < {t.amber_lens_below}"
        ),
        "green": "otherwise",
    }


def gate_chain(db: Session) -> dict[str, str]:
    """{decision gate code: approval chain type} (default SG4_ATD -> AtD, SG6_ATO -> AtO)."""
    value = _section("gate_chain", lambda: _setting(db, "cfg.gate_chain"))
    return (
        dict(value) if isinstance(value, Mapping) and value else dict(defaults.DEFAULT_GATE_CHAIN)
    )


def mock_approver(db: Session) -> dict[str, str]:
    """{mock_role, approver_role, mock_label}: the mocked approval role and who acts for it."""
    value = _section("mock_approver", lambda: _setting(db, "cfg.mock_approver"))
    return _merge(defaults.DEFAULT_MOCK_APPROVER, value)


# --- tiering ------------------------------------------------------------------------------------


def tiers(db: Session) -> list[dict[str, Any]]:
    """Ordered tier definitions [{tier, name, definition, examples, builder_persona}] (a copy)."""
    value = _section("tiers", lambda: _setting(db, "cfg.tiers") or defaults.seed_config()["tiers"])
    return [dict(t) for t in sorted(value, key=lambda t: t["tier"])]


def tier_numbers(db: Session) -> list[int]:
    """Valid tier numbers, ascending (default 1-4)."""
    return [int(t["tier"]) for t in tiers(db)]


def tier_dimensions(db: Session) -> list[str]:
    return list(
        _section(
            "tier_dimensions",
            lambda: _setting(db, "cfg.tier_dimensions")
            or defaults.seed_config()["tier_dimensions"],
        )
    )


def default_tier(db: Session) -> int:
    """The tier proposed when no rule matches (conservative default, Tier 3)."""
    return int(thresholds(db)["default_tier"])


def tier_questions(db: Session, active_only: bool = True) -> list[TierQuestionCfg]:
    def load() -> list[TierQuestionCfg]:
        rows = db.scalars(select(TierQuestion)).all()
        raw = (
            [
                dict(id=r.id, text=r.text, hint=r.hint, active=r.active, sort_order=r.sort_order)
                for r in rows
            ]
            if rows
            else defaults.seed_config()["tier_questions"]
        )
        return sorted(
            (
                TierQuestionCfg(
                    id=d["id"],
                    text=d["text"],
                    hint=d.get("hint", ""),
                    active=bool(d.get("active", True)),
                    sort_order=int(d.get("sort_order", 0)),
                )
                for d in raw
            ),
            key=lambda q: (q.sort_order, q.id),
        )

    return [q for q in _section("tier_questions", load) if q.active or not active_only]


# --- intake fields ------------------------------------------------------------------------------


def _intake_fields(db: Session) -> list[IntakeFieldCfg]:
    def load() -> list[IntakeFieldCfg]:
        rows = db.scalars(select(IntakeField)).all()
        raw = (
            [{c: getattr(r, c) for c in IntakeFieldCfg.__dataclass_fields__} for r in rows]
            if rows
            else defaults.seed_config()["intake_fields"]
        )
        return sorted(
            (
                IntakeFieldCfg(
                    key=d["key"],
                    label=d.get("label") or d["key"],
                    help=d.get("help", ""),
                    builtin=bool(d.get("builtin", False)),
                    structural=bool(d.get("structural", False)),
                    type=d.get("type", "text"),
                    option_list=d.get("option_list"),
                    visible=bool(d.get("visible", True)),
                    required_mode=d.get("required_mode", "never"),
                    required_for_project_types=tuple(d.get("required_for_project_types") or ()),
                    applies_to_project_types=tuple(d.get("applies_to_project_types") or ()),
                    applies_to_portfolios=tuple(d.get("applies_to_portfolios") or ()),
                    section=d.get("section", ""),
                    sort_order=int(d.get("sort_order", 0)),
                    show_on_overview=bool(d.get("show_on_overview", False)),
                    filterable=bool(d.get("filterable", False)),
                    form=d.get("form", "intake"),
                    min=d.get("min"),
                    max=d.get("max"),
                    max_length=d.get("max_length"),
                    active=bool(d.get("active", True)),
                )
                for d in raw
            ),
            key=lambda f: (f.sort_order, f.key),
        )

    return _section("intake_fields", load)


def intake_fields(
    db: Session, form: str | None = "intake", active_only: bool = True
) -> list[IntakeFieldCfg]:
    """Intake fields in form order. ``form`` "intake" | "ai_profile" | None (both)."""
    return [
        f
        for f in _intake_fields(db)
        if (f.active or not active_only) and (form is None or f.form == form)
    ]


def intake_field(db: Session, key: str) -> IntakeFieldCfg | None:
    return next((f for f in _intake_fields(db) if f.key == key), None)


def field_applies(f: IntakeFieldCfg, project_type: str | None, portfolio_name: str | None) -> bool:
    """True when the field is shown for this project type and portfolio ([] = all)."""
    if f.applies_to_project_types and project_type not in f.applies_to_project_types:
        return False
    return not (f.applies_to_portfolios and portfolio_name not in f.applies_to_portfolios)


def field_required(f: IntakeFieldCfg, project_type: str | None) -> bool:
    """True when the field is required for ``project_type`` (``by_project_type`` also honours the
    project type's own ``required_intake_fields``)."""
    if f.required_mode == "always":
        return True
    return f.required_mode == "by_project_type" and project_type in f.required_for_project_types


def required_fields_for(db: Session, project_type_code: str | None) -> list[str]:
    """Keys of the visible, active fields required for ``project_type`` (field rules plus the type's
    ``required_intake_fields`` list)."""
    pt = project_type(db, project_type_code)
    keys = [f.key for f in intake_fields(db) if f.visible and field_required(f, project_type_code)]
    for key in pt.required_intake_fields if pt else ():
        if key not in keys:
            keys.append(key)
    return keys


# --- message templates --------------------------------------------------------------------------


def template(db: Session, key: str) -> TemplateCfg | None:
    """The template of ``key``: the saved row, else the code default. None for an unknown key."""
    if key not in defaults.DEFAULT_TEMPLATES:
        return _stored_templates(db).get(key)
    stored = _stored_templates(db).get(key)
    if stored is not None:
        return stored
    name, subject, body, _src = defaults.DEFAULT_TEMPLATES[key]
    return TemplateCfg(
        key=key,
        name=name,
        subject=subject,
        body=body,
        enabled=True,
        placeholders=tuple(defaults.placeholder_specs(key)),
        is_default=True,
    )


def _stored_templates(db: Session) -> dict[str, TemplateCfg]:
    def load() -> dict[str, TemplateCfg]:
        return {
            r.key: TemplateCfg(
                key=r.key,
                name=r.name,
                subject=r.subject,
                body=r.body,
                enabled=bool(r.enabled),
                placeholders=tuple(r.placeholders or ()),
                is_default=False,
            )
            for r in db.scalars(select(MessageTemplate)).all()
        }

    return _section("templates", load)


def template_keys() -> list[str]:
    """Every template key the code knows (the draft kinds and reminder variants)."""
    return list(defaults.DEFAULT_TEMPLATES)


def render(text: str, values: Mapping[str, Any], html_placeholders: Iterable[str] = ()) -> str:
    """Fill ``{{placeholders}}``. Unknown or missing placeholders render as "". Values are
    HTML-escaped, except placeholders listed in ``html_placeholders`` (already-escaped fragments).
    """
    raw = set(html_placeholders)

    def sub(match) -> str:  # noqa: ANN001
        name = match.group(1)
        value = values.get(name)
        if value is None:
            return ""
        return str(value) if name in raw else html.escape(str(value), quote=True)

    return defaults._PLACEHOLDER_RE.sub(sub, text or "")


def render_template(tpl: TemplateCfg, values: Mapping[str, Any]) -> dict[str, str]:
    """{subject, body_html} of ``tpl`` filled with ``values`` (see ``render``). The subject is plain
    text (all values escaped); the body is HTML."""
    raw = [p["name"] for p in tpl.placeholders if p.get("html")]
    subject = render(tpl.subject, values, html_placeholders=list(values))  # plain text: no escaping
    return {"subject": subject, "body_html": render(tpl.body, values, raw)}
