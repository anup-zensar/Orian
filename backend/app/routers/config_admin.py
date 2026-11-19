"""CR-01 no-code configuration API. Everything under ``/api/v1/admin/...``, Admin only.

Rules every write follows:

* 403 unless ``Perm.ADMIN``; 422 with ``reasons[]`` (one per problem); 409 "Used by N transitions -
  deactivate instead" for ``DELETE`` of a value in use; 404 for an unknown key.
* Codes / keys never change; labels do. Inactive values stay valid on UNCHANGED existing records.
* Each write creates an AuditEvent (actor Human, entity ``config:<section>``, before / after), is
  committed, then ``cfg.invalidate()`` refreshes the configuration and permission caches, and the
  response is the saved section (the same model as its GET), so the UI needs no re-fetch.
* The logic lives in ``app/domain/config_admin.py`` (guardrails first, then one block per section);
  the response builders in ``app/domain/config_admin_read.py``.
* No role, permission or user is called Orion / agent / bot / ai (BR-050); gates, chain types,
  reminder ids, status buckets, the eight roles and the built-in checklists cannot be recoded.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require
from app.domain import cfg
from app.domain import config_admin as domain
from app.domain import config_admin_read as read
from app.models import User
from app.permissions import Perm
from app.schemas import config_admin as dto
from app.schemas.common import ErrorOut

router = APIRouter(tags=["admin config"])

AdminUser = Annotated[User, Depends(require(Perm.ADMIN))]
Db = Annotated[Session, Depends(get_db)]

_E = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 422: {"model": ErrorOut}}
_W = {**_E, 409: {"model": ErrorOut}}


def _save(db: Session) -> None:
    """Commit a configuration write and refresh every cache that reads configuration."""
    db.commit()
    cfg.invalidate()


# --------------------------------------------------------------------------- project types


@router.get("/admin/project-types", response_model=list[dto.ProjectTypeAdminOut], responses=_E)
def list_project_types(db: Db, user: AdminUser) -> list[dto.ProjectTypeAdminOut]:
    """All project types (active and inactive) by ``sort_order`` with ``used_by`` = transitions of
    that type. 403 non-admin."""
    return read.project_types_out(db)


@router.post(
    "/admin/project-types",
    response_model=list[dto.ProjectTypeAdminOut],
    status_code=201,
    responses=_W,
)
def create_project_type(body: dto.ProjectTypeCreateIn, db: Db, user: AdminUser):
    """Create a project type (no code change needed). Checklists must be active library checklists
    and the required intake fields must exist (written to both sides, see
    ``write_type_requirements``). New transitions only. 422 reasons per problem; 409 duplicate code.
    Returns the list."""
    domain.create_project_type(db, user, body)
    _save(db)
    return read.project_types_out(db)


@router.patch(
    "/admin/project-types/{code}", response_model=list[dto.ProjectTypeAdminOut], responses=_W
)
def update_project_type(code: str, body: dto.ProjectTypeUpdateIn, db: Db, user: AdminUser):
    """Edit label, description, flags, checklists, required intake fields, synonyms, order, active.
    The last active project type cannot be deactivated. The code never changes. 404 unknown code."""
    domain.update_project_type(db, user, code, body)
    _save(db)
    return read.project_types_out(db)


@router.delete(
    "/admin/project-types/{code}", response_model=list[dto.ProjectTypeAdminOut], responses=_W
)
def delete_project_type(code: str, db: Db, user: AdminUser):
    """Delete a project type nobody uses. 409 "Used by N transitions - deactivate instead"."""
    domain.delete_project_type(db, user, code)
    _save(db)
    return read.project_types_out(db)


@router.get(
    "/admin/project-types/{code}/preview", response_model=dto.ProjectTypePreviewOut, responses=_E
)
def preview_project_type(code: str, db: Db, user: AdminUser) -> dto.ProjectTypePreviewOut:
    """What a NEW transition of this type would get: active library item counts per gate and per
    checklist, and which steps (tiering, AI profile, eval metrics) it shows. 404 unknown code."""
    return read.project_type_preview(db, code)


# --------------------------------------------------------------------------- checklists


@router.get("/admin/checklists", response_model=list[dto.ChecklistAdminOut], responses=_E)
def list_checklists(db: Db, user: AdminUser) -> list[dto.ChecklistAdminOut]:
    """The checklist registry with item counts and the project types that list each one."""
    return read.checklists_out(db)


@router.post(
    "/admin/checklists", response_model=list[dto.ChecklistAdminOut], status_code=201, responses=_W
)
def create_checklist(body: dto.ChecklistCreateIn, db: Db, user: AdminUser):
    """Create a ``library`` checklist (code ``^[A-Z][A-Z0-9_]{1,39}$``, unique). 409 duplicate code."""
    domain.create_checklist(db, user, body)
    _save(db)
    return read.checklists_out(db)


@router.patch("/admin/checklists/{code}", response_model=list[dto.ChecklistAdminOut], responses=_W)
def update_checklist(code: str, body: dto.ChecklistUpdateIn, db: Db, user: AdminUser):
    """Edit label, description, order, ``tier_filtered`` and active. Deactivating is refused (409)
    while an active project type lists the checklist."""
    domain.update_checklist(db, user, code, body)
    _save(db)
    return read.checklists_out(db)


@router.delete("/admin/checklists/{code}", response_model=list[dto.ChecklistAdminOut], responses=_W)
def delete_checklist(code: str, db: Db, user: AdminUser):
    """Delete a custom checklist with no items and no project type; 409 otherwise (built-ins too)."""
    domain.delete_checklist(db, user, code)
    _save(db)
    return read.checklists_out(db)


@router.post(
    "/admin/playbook-items",
    response_model=dto.PlaybookItemCreateOut,
    status_code=201,
    responses=_W,
)
def create_playbook_item(body: dto.PlaybookItemCreateIn, db: Db, user: AdminUser):
    """Create a library item in ANY checklist (``source`` = checklist code). A golden-set checklist
    needs its ``portfolio``; gate, tiers, owner role and project types are validated. New
    transitions only. 404 unknown checklist; 409 duplicate id."""
    from app.domain import admin as admin_domain

    item = domain.create_playbook_item(db, user, body)
    result = admin_domain.get_playbook_item(db, item.id)
    _save(db)
    return result


# --------------------------------------------------------------------------- portfolios


@router.get("/admin/portfolios", response_model=list[dto.PortfolioAdminOut], responses=_E)
def list_portfolios(db: Db, user: AdminUser) -> list[dto.PortfolioAdminOut]:
    """All portfolios (active and inactive) with golden-set size and ``used_by``. The golden-set
    routes (``/admin/portfolios/{name}/golden-set``) are in the playbook admin API."""
    return read.portfolios_out(db)


@router.post(
    "/admin/portfolios", response_model=list[dto.PortfolioAdminOut], status_code=201, responses=_W
)
def create_portfolio(body: dto.PortfolioCreateIn, db: Db, user: AdminUser):
    """Create a portfolio (name unique, short ``code`` unique). ``requires_sites`` turns on the site
    rows at intake. 409 duplicate name."""
    domain.create_portfolio(db, user, body)
    _save(db)
    return read.portfolios_out(db)


@router.patch("/admin/portfolios/{name}", response_model=list[dto.PortfolioAdminOut], responses=_W)
def update_portfolio(name: str, body: dto.PortfolioUpdateIn, db: Db, user: AdminUser):
    """Edit code, label, description, focus areas, ``requires_sites``, ``sites_label``, synonyms,
    order, active. The last active portfolio cannot be deactivated."""
    domain.update_portfolio(db, user, name, body)
    _save(db)
    return read.portfolios_out(db)


@router.delete("/admin/portfolios/{name}", response_model=list[dto.PortfolioAdminOut], responses=_W)
def delete_portfolio(name: str, db: Db, user: AdminUser):
    """Delete an unused portfolio and its golden set. 409 "Used by N transitions - deactivate
    instead"."""
    domain.delete_portfolio(db, user, name)
    _save(db)
    return read.portfolios_out(db)


# --------------------------------------------------------------------------- option lists


@router.get("/admin/option-lists", response_model=list[dto.OptionListAdminOut], responses=_E)
def list_option_lists(db: Db, user: AdminUser) -> list[dto.OptionListAdminOut]:
    """Every list (built-in and custom) with ``group``, ``structural`` (lock icon), declared meta
    columns and counts. Items: ``GET /admin/option-lists/{key}/items``."""
    return read.option_lists_out(db)


@router.post(
    "/admin/option-lists",
    response_model=list[dto.OptionListAdminOut],
    status_code=201,
    responses=_W,
)
def create_option_list(body: dto.OptionListCreateIn, db: Db, user: AdminUser):
    """Create a custom list (key unique, ``^[a-z][a-z0-9_]{1,39}$``) for custom fields. 409
    duplicate key."""
    domain.create_option_list(db, user, body)
    _save(db)
    return read.option_lists_out(db)


@router.patch(
    "/admin/option-lists/{key}", response_model=list[dto.OptionListAdminOut], responses=_W
)
def update_option_list(key: str, body: dto.OptionListUpdateIn, db: Db, user: AdminUser):
    """Edit label, description, group, meta columns. A structural list accepts label and description
    only (422 "Behaviour depends on these values - only the labels can change")."""
    domain.update_option_list(db, user, key, body)
    _save(db)
    return read.option_lists_out(db)


@router.delete(
    "/admin/option-lists/{key}", response_model=list[dto.OptionListAdminOut], responses=_W
)
def delete_option_list(key: str, db: Db, user: AdminUser):
    """Delete a custom list not used by any field. Built-in lists cannot be deleted (409)."""
    domain.delete_option_list(db, user, key)
    _save(db)
    return read.option_lists_out(db)


@router.get("/admin/option-lists/{key}/items", response_model=dto.OptionItemsOut, responses=_E)
def get_option_items(key: str, db: Db, user: AdminUser) -> dto.OptionItemsOut:
    """The ordered items of a list (inactive included) with ``used_by``. 404 unknown list."""
    return read.option_items_out(db, key)


@router.put("/admin/option-lists/{key}/items", response_model=dto.OptionItemsOut, responses=_W)
def put_option_items(key: str, body: dto.OptionItemsIn, db: Db, user: AdminUser):
    """Replace the ORDERED items (position = ``sort_order``). The value of a row never changes; a new
    value adds a row; a used value that is missing or sent ``active=false`` is DEACTIVATED (see
    ``warnings``), an unused one is removed. Structural lists: labels and descriptions only.
    ``severities``: exactly one active ``counts_as_critical``; ``evidence_types`` ``needs`` in
    file / url / text / none; a built-in list keeps one active value."""
    warnings = domain.put_option_items(db, user, key, body)
    _save(db)
    out = read.option_items_out(db, key)
    out.warnings = warnings
    return out


# --------------------------------------------------------------------------- intake fields


@router.get("/admin/intake-fields", response_model=list[dto.IntakeFieldAdminOut], responses=_E)
def list_intake_fields(db: Db, user: AdminUser) -> list[dto.IntakeFieldAdminOut]:
    """Built-in and custom fields (both forms, inactive included) in form order with ``used_by``
    and ``type_locked``."""
    return read.intake_fields_out(db)


@router.post(
    "/admin/intake-fields",
    response_model=list[dto.IntakeFieldAdminOut],
    status_code=201,
    responses=_W,
)
def create_intake_field(body: dto.IntakeFieldCreateIn, db: Db, user: AdminUser):
    """Create a custom field. The key ``cf_<slug>`` is made from the label. select / multiselect need
    an existing option list; number accepts ``min`` / ``max``; text ``max_length``. Values live on
    the transition (``custom_fields``)."""
    domain.create_intake_field(db, user, body)
    _save(db)
    return read.intake_fields_out(db)


@router.put(
    "/admin/intake-fields/order", response_model=list[dto.IntakeFieldAdminOut], responses=_W
)
def order_intake_fields(body: dto.IntakeFieldOrderIn, db: Db, user: AdminUser):
    """Set the field order: ``keys`` must contain every field key exactly once (422 otherwise)."""
    domain.order_intake_fields(db, user, body)
    _save(db)
    return read.intake_fields_out(db)


@router.patch(
    "/admin/intake-fields/{key}", response_model=list[dto.IntakeFieldAdminOut], responses=_W
)
def update_intake_field(key: str, body: dto.IntakeFieldUpdateIn, db: Db, user: AdminUser):
    """Edit a field. Built-in fields: label, help and (optional ones) visibility only. Custom
    fields: everything, but the ``type`` is refused once any transition holds a value. Required-for-
    project-types is written to the project types too."""
    domain.update_intake_field(db, user, key, body)
    _save(db)
    return read.intake_fields_out(db)


@router.delete(
    "/admin/intake-fields/{key}", response_model=list[dto.IntakeFieldAdminOut], responses=_W
)
def delete_intake_field(key: str, db: Db, user: AdminUser):
    """Delete an UNUSED custom field. Built-in fields cannot be deleted (409); a used custom field
    answers 409 "Used by N transitions - deactivate instead"."""
    domain.delete_intake_field(db, user, key)
    _save(db)
    return read.intake_fields_out(db)


# --------------------------------------------------------------------------- roles and users


@router.get("/admin/roles", response_model=list[dto.RoleAdminOut], responses=_E)
def list_roles(db: Db, user: AdminUser) -> list[dto.RoleAdminOut]:
    """The eight built-in roles with ``user_count`` and lock reasons."""
    return read.roles_out(db)


@router.patch("/admin/roles/{code}", response_model=list[dto.RoleAdminOut], responses=_W)
def update_role(code: str, body: dto.RoleUpdateIn, db: Db, user: AdminUser):
    """Rename a role (label, short label, phrase, description). Codes are fixed; the reserved words
    Orion / agent / bot / ai are refused (BR-050)."""
    domain.update_role(db, user, code, body)
    _save(db)
    return read.roles_out(db)


@router.get("/admin/users", response_model=list[dto.UserAdminOut], responses=_E)
def list_users(db: Db, user: AdminUser) -> list[dto.UserAdminOut]:
    """Everybody (inactive included) with the number of active transitions each person is assigned
    to. The login list (``GET /users``) shows active people only."""
    return read.users_out(db)


@router.post("/admin/users", response_model=dto.UserAdminOut, status_code=201, responses=_W)
def create_user(body: dto.UserCreateIn, db: Db, user: AdminUser):
    """Create a user (next id U17, U18 ...). The role must be active, the e-mail unique, the name not
    Orion / agent / bot / ai."""
    new_id = domain.create_user(db, user, body)
    _save(db)
    return read.user_out(db, db.get(User, new_id))  # type: ignore[arg-type]


@router.patch("/admin/users/{user_id}", response_model=dto.UserAdminOut, responses=_W)
def update_user(user_id: str, body: dto.UserUpdateIn, db: Db, user: AdminUser):
    """Edit name, e-mail, role, focal label, title; ``active=true`` re-activates. You cannot move
    yourself, or the last active Admin, away from Admin. 404 unknown user."""
    domain.update_user(db, user, user_id, body)
    _save(db)
    return read.user_out(db, db.get(User, user_id))  # type: ignore[arg-type]


@router.post(
    "/admin/users/{user_id}/deactivate", response_model=dto.UserDeactivateOut, responses=_W
)
def deactivate_user(user_id: str, body: dto.UserDeactivateIn, db: Db, user: AdminUser):
    """Deactivate a user (never delete). Refused for yourself and for the last active Admin. The
    answer says how many active transitions the person is assigned to; ``reassign_to`` (an active
    user with the same role) takes those slots over in the same audited action."""
    assigned, moved, warnings = domain.deactivate_user(db, user, user_id, body.reassign_to)
    _save(db)
    return dto.UserDeactivateOut(
        user=read.user_out(db, db.get(User, user_id)),  # type: ignore[arg-type]
        assigned_transitions=assigned,
        reassigned=moved,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- permissions


@router.get("/admin/permissions", response_model=dto.PermissionMatrixOut, responses=_E)
def get_permissions(db: Db, user: AdminUser) -> dto.PermissionMatrixOut:
    """The permission grid: rows = permissions grouped by ``area`` with scope (global / transition),
    columns = roles, locked cells with reasons, editable denial texts."""
    return read.permission_matrix_out(db)


@router.put("/admin/permissions", response_model=dto.PermissionMatrixOut, responses=_W)
def put_permissions(body: dto.PermissionsPutIn, db: Db, user: AdminUser):
    """Replace the grid (every permission present) and optionally the wording. 422 when the Admin
    role would lose ``admin``, nobody active could change configuration, a role loses ``view``, or a
    code is unknown. A denial text nobody edited is regenerated from the role names. Applies at once.
    """
    domain.put_permissions(db, user, body)
    _save(db)
    return read.permission_matrix_out(db)


# --------------------------------------------------------------------------- tiering


@router.get("/admin/tiering", response_model=dto.TieringConfigOut, responses=_E)
def get_tiering(db: Db, user: AdminUser) -> dto.TieringConfigOut:
    """Tier definitions and tiering question wording (the rules BR-011 stay in code)."""
    return read.tiering_out(db)


@router.put("/admin/tiering", response_model=dto.TieringConfigOut, responses=_W)
def put_tiering(body: dto.TieringConfigIn, db: Db, user: AdminUser):
    """New wording for the tier definitions and the questions. The tier numbers and question ids must
    be the existing ones (422 otherwise). Applies to new tier proposals."""
    domain.put_tiering(db, user, body)
    _save(db)
    return read.tiering_out(db)


# --------------------------------------------------------------------------- eval metrics


@router.get("/admin/eval-metrics", response_model=list[dto.EvalMetricAdminOut], responses=_E)
def list_eval_metrics(db: Db, user: AdminUser) -> list[dto.EvalMetricAdminOut]:
    """Every eval metric (EV-nn) with its targets per tier and the metric-level ``active`` flag.
    (The tier-target editor stays ``/admin/eval-targets``.)"""
    return read.eval_metrics_out(db)


def _metric(db: Session, metric_id: str) -> dto.EvalMetricAdminOut:
    return next(m for m in read.eval_metrics_out(db) if m.id == metric_id)


@router.post(
    "/admin/eval-metrics", response_model=dto.EvalMetricAdminOut, status_code=201, responses=_W
)
def create_eval_metric(body: dto.EvalMetricCreateIn, db: Db, user: AdminUser):
    """Add a metric (id EV-nn = next free). ``targets_by_tier`` must cover every tier; operator and
    value only for ``auto`` metrics. New transitions only."""
    metric_id = domain.create_eval_metric(db, user, body)
    _save(db)
    return _metric(db, metric_id)


@router.patch(
    "/admin/eval-metrics/{metric_id}", response_model=dto.EvalMetricAdminOut, responses=_W
)
def update_eval_metric(metric_id: str, body: dto.EvalMetricUpdateIn, db: Db, user: AdminUser):
    """Edit name, evaluation mode, unit; ``active=false`` deactivates the metric for new results
    (existing results stay). 404 unknown metric."""
    domain.update_eval_metric(db, user, metric_id, body)
    _save(db)
    return _metric(db, metric_id)


# --------------------------------------------------------------------------- thresholds


@router.get("/admin/thresholds", response_model=dto.ThresholdsOut, responses=_E)
def get_thresholds(db: Db, user: AdminUser) -> dto.ThresholdsOut:
    """RAG numbers, insight thresholds, calendar horizon, dashboard limits, narrative size, default
    tier / pricing basis / horizon / growth, and the ``rag_rule`` text generated from them."""
    return read.thresholds_out(db)


@router.put("/admin/thresholds", response_model=dto.ThresholdsOut, responses=_W)
def put_thresholds(body: dto.ThresholdsIn, db: Db, user: AdminUser):
    """Replace the thresholds. 422 when amber is stricter than red, or the default tier / pricing
    basis does not exist. Live: RAG recalculates for all active transitions."""
    domain.put_thresholds(db, user, body)
    _save(db)
    return read.thresholds_out(db)


# --------------------------------------------------------------------------- message templates


@router.get(
    "/admin/message-templates", response_model=list[dto.MessageTemplateAdminOut], responses=_E
)
def list_message_templates(db: Db, user: AdminUser) -> list[dto.MessageTemplateAdminOut]:
    """Every template (saved row, else the code default) with its allowed placeholders, the code
    default text and the code path it replaces."""
    return read.templates_out(db)


@router.put(
    "/admin/message-templates", response_model=list[dto.MessageTemplateAdminOut], responses=_W
)
def put_message_templates(body: dto.MessageTemplatesPutIn, db: Db, user: AdminUser):
    """Save templates. Only the key's own placeholders (an unknown ``{{name}}`` refuses the save with
    the name in the reason); no scripts. Recipients and send policy are not part of a template."""
    domain.put_message_templates(db, user, body)
    _save(db)
    return read.templates_out(db)


@router.post(
    "/admin/message-templates/{key}/preview",
    response_model=dto.TemplatePreviewOut,
    responses=_E,
)
def preview_message_template(
    key: str, body: dto.TemplatePreviewIn, db: Db, user: AdminUser
) -> dto.TemplatePreviewOut:
    """Render a template (saved, or the unsaved edit in the body) with a sample context; values
    are HTML-escaped, unknown placeholders are listed. Writes nothing, no audit."""
    return read.preview_template(db, key, body)


# --------------------------------------------------------------------------- usage


@router.get("/admin/usage", response_model=dto.UsageOut, responses=_E)
def get_usage(
    db: Db,
    user: AdminUser,
    kind: str = Query(description="project_type | portfolio | option | role | checklist"),
    key: str = Query(description='the code / name; for kind=option "<list key>:<value>"'),
) -> dto.UsageOut:
    """Where a value is used: count and the first 10 transitions. 422 unknown ``kind``."""
    return read.usage(db, kind, key)
