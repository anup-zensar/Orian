"""Reference and configuration tables (spec §6 User, FlavourRule, Portfolio; Admin-editable config).

CR-01 (docs: scratchpad d-config/CR01_design.md) turns most hard-coded vocabulary into rows here:
project types, checklists, option lists, intake fields, roles, the permission matrix, tiering and
message templates. Codes / keys are immutable, labels are editable ("deactivate, never delete").
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "U01"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(30))  # a roles.code (built-ins: app.permissions.Role)
    focal_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # CR-01 (design 1.6): users are deactivated, never deleted; ``title`` is a free job title
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ReferenceData(TimestampMixin, Base):
    """Read-mostly reference blobs loaded from seed (e.g. key="reference" = reference.json)."""

    __tablename__ = "reference_data"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    data: Mapped[Any] = mapped_column(JSON)


class AppSetting(TimestampMixin, Base):
    """Small key/value store (e.g. "today_override", "last_reminder_run", "schema_version").

    CR-01 settings documents (JSON, read through ``app.domain.cfg``): ``cfg.thresholds``,
    ``cfg.gates``, ``cfg.gate_outcome_labels``, ``cfg.gate_chain``, ``cfg.mock_approver``,
    ``cfg.labels``, ``cfg.lenses``, ``cfg.tiers``, ``cfg.tier_dimensions``.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)


class FlavourRule(TimestampMixin, Base):
    """A PROJECT TYPE (CR-01 design 1.1): checklists plus behaviour flags; editable in Admin (FR-100).

    The table name stays ``flavour_rules`` (the API calls the rows project types). ``project_type``
    is the immutable code; ``label`` is what people see ("" = show the code)."""

    __tablename__ = "flavour_rules"

    project_type: Mapped[str] = mapped_column(String(40), primary_key=True)  # immutable code
    checklists: Mapped[list[str]] = mapped_column(JSON)  # ["FRAMEWORK", "AI_PLAYBOOK"]
    requires_tiering: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    has_ai_profile: Mapped[bool] = mapped_column(Boolean, default=False)  # AI profile step / tab
    has_eval_metrics: Mapped[bool] = mapped_column(Boolean, default=False)  # eval metrics tab
    # intake field keys that are required for this type (e.g. audience, write_actions)
    required_intake_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list)  # Orion natural language
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)  # colour token


class Portfolio(TimestampMixin, Base):
    """A portfolio. ``name`` is the immutable key, ``label`` what people see ("" = the name)."""

    __tablename__ = "portfolios"

    name: Mapped[str] = mapped_column(String(60), primary_key=True)  # "GCC"
    code: Mapped[str] = mapped_column(String(10))
    focus_areas: Mapped[list[str]] = mapped_column(JSON)
    # superseded by intake_fields (CR-01 1.5); kept so old payloads load, always []
    intake_extra_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    label: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    requires_sites: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # intake asks for site rows
    sites_label: Mapped[str] = mapped_column(String(80), default="")
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list)


class ApprovalChainConfig(TimestampMixin, Base):
    """reference.json -> approval_chains; editable in Admin. steps = [{step, role, label, is_mock?}]."""

    __tablename__ = "approval_chain_configs"

    type: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )  # OCET | AtD | AtO | SUPPORT_MODEL | EXCEPTION
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)  # CR-01 display name


class ReminderRule(TimestampMixin, Base):
    """Reminder engine rules R1–R7 (BR-060) with editable thresholds (FR-100)."""

    __tablename__ = "reminder_rules"

    id: Mapped[str] = mapped_column(String(4), primary_key=True)  # "R1"
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    autonomous_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # e.g. {"days_before_decision": 14}
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


# --- CR-01 configuration tables (design 1.2 - 1.8) ----------------------------------------------


class Checklist(TimestampMixin, Base):
    """A named set of library items. ``kind``: library (included when the project type lists it) |
    portfolio_golden (picked by the transition portfolio) | common (always included, BR-010)."""

    __tablename__ = "checklists"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)  # immutable
    label: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    tier_filtered: Mapped[bool] = mapped_column(Boolean, default=False)  # items filtered by tier
    kind: Mapped[str] = mapped_column(String(20), default="library")


class OptionList(TimestampMixin, Base):
    """A named list of options (regions, severities, evidence types ...). Items in ``option_items``."""

    __tablename__ = "option_lists"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)  # immutable
    label: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    # code depends on the values: only label / description of the list and its items may change
    structural: Mapped[bool] = mapped_column(Boolean, default=False)
    # declared meta keys for the editor, e.g. [{"key": "color", "type": "token"}]
    meta_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    group: Mapped[str] = mapped_column(String(40), default="")  # editor grouping
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class OptionItem(TimestampMixin, Base):
    """One value of an option list. ``value`` is the stored string (never changes once used);
    ``label`` is what the UI shows ("" = the value)."""

    __tablename__ = "option_items"
    __table_args__ = (UniqueConstraint("list_key", "value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_key: Mapped[str] = mapped_column(ForeignKey("option_lists.key"), index=True)
    value: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class IntakeField(TimestampMixin, Base):
    """One field of the intake form (built-in and custom in one table, design 1.5)."""

    __tablename__ = "intake_fields"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)  # name | cf_<slug> ...
    label: Mapped[str] = mapped_column(String(120), default="")
    help: Mapped[str] = mapped_column(Text, default="")
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    # structural fields (name, project_type, portfolio, region, or_focal_user_id) cannot be hidden,
    # made optional or removed; their label stays editable
    structural: Mapped[bool] = mapped_column(Boolean, default=False)
    # text | textarea | number | date | select | multiselect | boolean | user
    type: Mapped[str] = mapped_column(String(20), default="text")
    option_list: Mapped[str | None] = mapped_column(String(60), nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    required_mode: Mapped[str] = mapped_column(
        String(20), default="never"
    )  # never|always|by_project_type
    required_for_project_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    applies_to_project_types: Mapped[list[str]] = mapped_column(JSON, default=list)  # [] = all
    applies_to_portfolios: Mapped[list[str]] = mapped_column(JSON, default=list)  # [] = all
    section: Mapped[str] = mapped_column(String(60), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    show_on_overview: Mapped[bool] = mapped_column(Boolean, default=False)
    filterable: Mapped[bool] = mapped_column(Boolean, default=False)
    form: Mapped[str] = mapped_column(String(20), default="intake")  # intake | ai_profile
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(TimestampMixin, Base):
    """A role (design 1.6): the eight built-ins plus admin-created ones. Orion is never a role."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)  # immutable
    label: Mapped[str] = mapped_column(String(80), default="")  # long: "OR focal (S&T)"
    short_label: Mapped[str] = mapped_column(String(40), default="")  # "OR focal"; "" = label
    phrase_label: Mapped[str] = mapped_column(String(40), default="")  # in sentences; "" = label
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    has_transition_slot: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # a person per transition
    transition_column: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )  # built-in slots
    can_approve: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # may be an approval-step role
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)


class RolePermission(TimestampMixin, Base):
    """The permission matrix: one row per (permission, role) that is granted."""

    __tablename__ = "role_permissions"

    perm: Mapped[str] = mapped_column(String(40), primary_key=True)  # app.permissions.Perm value
    role_code: Mapped[str] = mapped_column(String(30), primary_key=True)


class PermissionText(TimestampMixin, Base):
    """Editable wording of a permission: label, help and the 403 / tooltip reason."""

    __tablename__ = "permission_texts"

    perm: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    denial_reason: Mapped[str] = mapped_column(Text, default="")
    area: Mapped[str] = mapped_column(String(40), default="")  # grouping in the matrix editor
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)  # admin edited the reason text


class TierQuestion(TimestampMixin, Base):
    """A tiering question (TQ1..). ``hint`` is the "if yes" explanation."""

    __tablename__ = "tier_questions"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)  # TQ1 ...
    text: Mapped[str] = mapped_column(Text)
    hint: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TierRule(TimestampMixin, Base):
    """BR-011 as data. First matching active rule (by ``sort_order``) wins, otherwise the default tier.
    ``conditions`` = [{source: question|intake|custom, key, op: yes|no|equals|not_equals|in,
    value, rationale}]."""

    __tablename__ = "tier_rules"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # RULE-1 ...
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(120), default="")
    result_tier: Mapped[int] = mapped_column(Integer)
    match: Mapped[str] = mapped_column(String(3), default="any")  # any | all
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class MessageTemplate(TimestampMixin, Base):
    """Wording of one Orion draft kind (design 1.8). Placeholders ``{{name}}``; known ones only."""

    __tablename__ = "message_templates"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    placeholders: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # read-only
