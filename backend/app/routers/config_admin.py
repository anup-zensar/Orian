"""CR-01 no-code configuration API (design 4). Everything under ``/api/v1/admin/...``, Admin only.

Contract owned by the CR-01 foundation: every endpoint, request/response model and the docstring of
what it must validate. The GET endpoints are implemented here (builders in
``app/domain/config_admin_read.py``); every write raises ``NotImplementedError("CR-01")`` (answered
as 501, A-74) until the admin-API engineer implements it in ``app/domain/config_admin.py``.

Rules every write must follow (design 4 and 5):

* 403 unless ``Perm.ADMIN``; 422 with ``reasons[]`` (one per problem); 409 "Used by N transitions -
  deactivate instead" for ``DELETE`` of a value in use; 404 for an unknown key.
* Codes / keys are immutable; labels editable. Inactive values stay valid on UNCHANGED existing
  records (``cfg.validate_option(db, key, value, current=...)``).
* Each write creates an AuditEvent (actor Human, entity ``config:<section>``, before/after), calls
  ``cfg.invalidate()`` after commit, and returns the saved section (same model as the GET).
* No role, permission row or user may be named Orion / agent / bot / ai (BR-050); structural codes
  (gates, lenses, chain types, reminder ids, status buckets, built-in roles and checklists) cannot be
  deleted or recoded.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require
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


def _todo() -> None:
    raise NotImplementedError("CR-01")


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
    """Create a project type (no code change needed). Validates: code unique (case-insensitive) and
    printable; every checklist exists and is a ``library`` checklist; required intake fields exist;
    ``has_ai_profile`` / ``requires_tiering`` are plain flags. New transitions only. Audit
    ``config:project_types``. 422 reasons per problem; 409 duplicate code. Returns the list."""
    _todo()


@router.patch(
    "/admin/project-types/{code}", response_model=list[dto.ProjectTypeAdminOut], responses=_W
)
def update_project_type(code: str, body: dto.ProjectTypeUpdateIn, db: Db, user: AdminUser):
    """Edit label, description, flags, checklists, required intake fields (written to both sides:
    the type's list and the fields' ``required_for_project_types``), synonyms, order, active.
    Guardrails: the last active project type cannot be deactivated (guardrail 5); a checklist must
    exist and be active. The code never changes. Returns the list. 404 unknown code."""
    _todo()


@router.delete(
    "/admin/project-types/{code}", response_model=list[dto.ProjectTypeAdminOut], responses=_W
)
def delete_project_type(code: str, db: Db, user: AdminUser):
    """Delete a project type nobody uses. 409 "Used by N transitions - deactivate instead" when any
    transition has it. Returns the list."""
    _todo()


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
    """Create a ``library`` checklist (code ``^[A-Z][A-Z0-9_]{1,39}$``, unique). Audit
    ``config:checklists``. 409 duplicate code. Returns the list."""
    _todo()


@router.patch("/admin/checklists/{code}", response_model=list[dto.ChecklistAdminOut], responses=_W)
def update_checklist(code: str, body: dto.ChecklistUpdateIn, db: Db, user: AdminUser):
    """Edit label, description, order, ``tier_filtered`` and active. ``kind`` never changes;
    deactivating is refused (409) while an active project type lists the checklist. Returns the list.
    """
    _todo()


@router.delete("/admin/checklists/{code}", response_model=list[dto.ChecklistAdminOut], responses=_W)
def delete_checklist(code: str, db: Db, user: AdminUser):
    """Delete a custom checklist with no items and no project type. Built-ins cannot be deleted
    (409); 409 when it has items or is listed by a project type. Returns the list."""
    _todo()


@router.post(
    "/admin/playbook-items",
    response_model=dto.PlaybookItemCreateOut,
    status_code=201,
    responses=_W,
)
def create_playbook_item(body: dto.PlaybookItemCreateIn, db: Db, user: AdminUser):
    """Create a library item in ANY checklist (``source`` = checklist code; GET / PUT of items
    already exist). Validates: checklist exists and is active; ``portfolio`` required for a
    ``portfolio_golden`` checklist and must exist; gate is a gate code; lens one of the three;
    tiers within ``cfg.tier_numbers``; ``default_owner_role`` an active role; id unique. New
    transitions only. Audit ``config:playbook_items``."""
    _todo()


# --------------------------------------------------------------------------- portfolios


@router.get("/admin/portfolios", response_model=list[dto.PortfolioAdminOut], responses=_E)
def list_portfolios(db: Db, user: AdminUser) -> list[dto.PortfolioAdminOut]:
    """All portfolios (active and inactive) with golden-set size and ``used_by``. The golden-set
    routes (``/admin/portfolios/{name}/golden-set``) are unchanged."""
    return read.portfolios_out(db)


@router.post(
    "/admin/portfolios", response_model=list[dto.PortfolioAdminOut], status_code=201, responses=_W
)
def create_portfolio(body: dto.PortfolioCreateIn, db: Db, user: AdminUser):
    """Create a portfolio (name immutable and unique, short ``code``). ``requires_sites`` turns on
    the site rows at intake. Audit ``config:portfolios``. 409 duplicate name. Returns the list."""
    _todo()


@router.patch("/admin/portfolios/{name}", response_model=list[dto.PortfolioAdminOut], responses=_W)
def update_portfolio(name: str, body: dto.PortfolioUpdateIn, db: Db, user: AdminUser):
    """Edit code, label, description, focus areas, ``requires_sites``, ``sites_label``, synonyms,
    order, active. The last active portfolio cannot be deactivated. Returns the list."""
    _todo()


@router.delete("/admin/portfolios/{name}", response_model=list[dto.PortfolioAdminOut], responses=_W)
def delete_portfolio(name: str, db: Db, user: AdminUser):
    """Delete an unused portfolio and its golden set. 409 "Used by N transitions - deactivate
    instead". Returns the list."""
    _todo()


# --------------------------------------------------------------------------- option lists


@router.get("/admin/option-lists", response_model=list[dto.OptionListAdminOut], responses=_E)
def list_option_lists(db: Db, user: AdminUser) -> list[dto.OptionListAdminOut]:
    """Every list (built-in and custom) with ``group``, ``structural`` (lock icon), declared meta
    fields and counts. Items: ``GET /admin/option-lists/{key}/items``."""
    return read.option_lists_out(db)


@router.post(
    "/admin/option-lists",
    response_model=list[dto.OptionListAdminOut],
    status_code=201,
    responses=_W,
)
def create_option_list(body: dto.OptionListCreateIn, db: Db, user: AdminUser):
    """Create a custom list (key unique, ``^[a-z][a-z0-9_]{1,39}$``) for custom fields. Audit
    ``config:option_lists``. 409 duplicate key. Returns the list of lists."""
    _todo()


@router.patch(
    "/admin/option-lists/{key}", response_model=list[dto.OptionListAdminOut], responses=_W
)
def update_option_list(key: str, body: dto.OptionListUpdateIn, db: Db, user: AdminUser):
    """Edit label, description, group, declared meta fields. A structural list accepts label and
    description only (422 "Behaviour depends on these values - only the labels can change")."""
    _todo()


@router.delete(
    "/admin/option-lists/{key}", response_model=list[dto.OptionListAdminOut], responses=_W
)
def delete_option_list(key: str, db: Db, user: AdminUser):
    """Delete a custom list not used by any intake field. Built-in and structural lists cannot be
    deleted (409); 409 while a field uses it."""
    _todo()


@router.get("/admin/option-lists/{key}/items", response_model=dto.OptionItemsOut, responses=_E)
def get_option_items(key: str, db: Db, user: AdminUser) -> dto.OptionItemsOut:
    """The ordered items of a list (inactive included) with ``used_by``. 404 unknown list."""
    return read.option_items_out(db, key)


@router.put("/admin/option-lists/{key}/items", response_model=dto.OptionItemsOut, responses=_W)
def put_option_items(key: str, body: dto.OptionItemsIn, db: Db, user: AdminUser):
    """Replace the ORDERED items (position = ``sort_order``). Existing values keep their identity
    (the value never changes); new values are added; a used value missing from the body or sent
    ``active=false`` is DEACTIVATED (warning with the count), an unused one is removed. Structural
    lists: labels / descriptions only (add / remove / recode refused with a reason). Validates meta
    against the declared meta fields; ``severities``: exactly one ``counts_as_critical``;
    ``evidence_types`` ``needs`` in file / url / text / none; the last active value of ``regions``
    cannot be deactivated. Returns the items."""
    _todo()


@router.post("/admin/config/reset", response_model=dto.ConfigResetOut, responses=_W)
def reset_config_section(body: dto.ConfigResetIn, db: Db, user: AdminUser):
    """EXTENSION of design 4 ("Reset section to defaults"): restore one editor from seed/config.json.
    409 when it would remove a value that is in use. Audit ``config:<section>``."""
    _todo()


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
    """Create a custom field. Key ``cf_<slug>`` from the label (unique, ``^[a-z][a-z0-9_]{1,40}$``
    after the prefix). select / multiselect need an existing option list (``option_list``); number
    accepts ``min`` / ``max``; text ``max_length``. ``required_mode`` by_project_type needs project
    types that exist. Values live in ``Transition.custom_fields`` (``AIProfile.extra`` for the
    ai_profile form). Audit ``config:intake_fields``."""
    _todo()


@router.put(
    "/admin/intake-fields/order", response_model=list[dto.IntakeFieldAdminOut], responses=_W
)
def order_intake_fields(body: dto.IntakeFieldOrderIn, db: Db, user: AdminUser):
    """Set the field order: ``keys`` must contain every field key exactly once (422 otherwise)."""
    _todo()


@router.patch(
    "/admin/intake-fields/{key}", response_model=list[dto.IntakeFieldAdminOut], responses=_W
)
def update_intake_field(key: str, body: dto.IntakeFieldUpdateIn, db: Db, user: AdminUser):
    """Edit a field. Label / help / section are editable everywhere. Structural fields (name,
    project_type, portfolio, region, or_focal_user_id) refuse hide, optional and deactivate; the
    ``type`` is refused once any transition holds a value and always for built-ins; a used option
    removal becomes deactivation. ``required_for_project_types`` and the project types'
    ``required_intake_fields`` are written through one function so they cannot diverge."""
    _todo()


@router.delete(
    "/admin/intake-fields/{key}", response_model=list[dto.IntakeFieldAdminOut], responses=_W
)
def delete_intake_field(key: str, db: Db, user: AdminUser):
    """Delete an UNUSED custom field. Built-in fields cannot be deleted (409); a used custom field
    answers 409 "Used by N transitions - deactivate instead" (deactivating hides it; stored values
    stay readable under "Retired fields")."""
    _todo()


# --------------------------------------------------------------------------- roles and users


@router.get("/admin/roles", response_model=list[dto.RoleAdminOut], responses=_E)
def list_roles(db: Db, user: AdminUser) -> list[dto.RoleAdminOut]:
    """All roles (active and inactive) with ``user_count`` and lock reasons."""
    return read.roles_out(db)


@router.post("/admin/roles", response_model=list[dto.RoleAdminOut], status_code=201, responses=_W)
def create_role(body: dto.RoleCreateIn, db: Db, user: AdminUser):
    """Create a role (code immutable, unique). Refused: names or codes containing Orion / agent /
    bot / ai (reserved, BR-050). A role with a transition slot gets a person per transition in
    ``Transition.role_assignments``. A new role holds only ``view`` until the matrix is edited.
    Audit ``config:roles``."""
    _todo()


@router.patch("/admin/roles/{code}", response_model=list[dto.RoleAdminOut], responses=_W)
def update_role(code: str, body: dto.RoleUpdateIn, db: Db, user: AdminUser):
    """Edit labels, description, colour, order, ``can_approve``, ``has_transition_slot`` (ADMIN is
    locked false; a built-in slot cannot be turned off), active. Deactivating needs no active user
    left with the role (409) and is refused for ADMIN."""
    _todo()


@router.delete("/admin/roles/{code}", response_model=list[dto.RoleAdminOut], responses=_W)
def delete_role(code: str, db: Db, user: AdminUser):
    """Delete an unused custom role (no users, no approval step, no assignment). Built-in roles
    cannot be deleted (409)."""
    _todo()


@router.post("/admin/users", response_model=dto.UserAdminOut, status_code=201, responses=_W)
def create_user(body: dto.UserCreateIn, db: Db, user: AdminUser):
    """Create a user (id from ``ID_FORMATS["U"]``: U17, U18 ...). Validates: role is an ACTIVE role;
    e-mail unique; name not Orion / agent / bot / ai. Audit ``config:users``."""
    _todo()


@router.patch("/admin/users/{user_id}", response_model=dto.UserAdminOut, responses=_W)
def update_user(user_id: str, body: dto.UserUpdateIn, db: Db, user: AdminUser):
    """Edit name, e-mail, role, focal label, title. You cannot change your own role away from
    Admin, and the last active Admin keeps the role (guardrail 4). 404 unknown user."""
    _todo()


@router.post(
    "/admin/users/{user_id}/deactivate", response_model=dto.UserDeactivateOut, responses=_W
)
def deactivate_user(user_id: str, body: dto.UserDeactivateIn, db: Db, user: AdminUser):
    """Deactivate a user (never delete). Refused for yourself and for the last active Admin
    (guardrail 4) and when it would leave nobody holding the ``admin`` permission. The response
    warns "assigned on N active transitions"; ``reassign_to`` (an active user of the same role)
    takes those slots over in the same audited action. Old records still resolve the name."""
    _todo()


# --------------------------------------------------------------------------- permissions


@router.get("/admin/permissions", response_model=dto.PermissionMatrixOut, responses=_E)
def get_permissions(db: Db, user: AdminUser) -> dto.PermissionMatrixOut:
    """The permission matrix: rows = permissions grouped by ``area`` with scope (global /
    transition), columns = active roles, locked cells with reasons, editable denial texts."""
    return read.permission_matrix_out(db)


@router.put("/admin/permissions", response_model=dto.PermissionMatrixOut, responses=_W)
def put_permissions(body: dto.PermissionsPutIn, db: Db, user: AdminUser):
    """Replace the matrix and optionally the texts. Guardrails (422, one reason each): ADMIN keeps
    ``admin`` and one ACTIVE user holds it; ``view`` includes every active role; unknown perm or
    role codes; no Orion / agent role. A denial text left unedited is regenerated from the role
    labels (``is_custom=false``) so it never names a role that lost the right. Effective at once
    (``cfg.invalidate()`` rebuilds the permission cache). Audit ``config:permissions`` with the
    before / after matrix."""
    _todo()


# --------------------------------------------------------------------------- tiering


@router.get("/admin/tiering", response_model=dto.TieringConfigOut, responses=_E)
def get_tiering(db: Db, user: AdminUser) -> dto.TieringConfigOut:
    """Tier definitions, dimensions, default tier, questions and rules (evaluation order), plus the
    intake / custom fields a rule condition may look at."""
    return read.tiering_out(db)


@router.put("/admin/tiering", response_model=dto.TieringConfigOut, responses=_W)
def put_tiering(body: dto.TieringConfigIn, db: Db, user: AdminUser):
    """Replace the whole tiering configuration. Guardrails: tier numbers unique and contiguous from
    1 (a tier is removed only when no tier assessment uses it); ``default_tier`` and every rule's
    ``result_tier`` are defined; ``source: question`` conditions name an existing question;
    ``intake`` / ``custom`` conditions name an existing field and (for select fields) a value of its
    list; new questions get the next id (TQ6 ...). Audit ``config:tiering``."""
    _todo()


@router.post("/admin/tiering/test", response_model=dto.TierTestOut, responses=_E)
def test_tiering(body: dto.TierTestIn, db: Db, user: AdminUser):
    """Run the pure ``propose_tier(rules, questions, intake, answers)`` on a hypothetical project
    (saved configuration, or the unsaved ``config`` in the body). Writes nothing, no audit."""
    _todo()


# --------------------------------------------------------------------------- eval metrics


@router.get("/admin/eval-metrics", response_model=list[dto.EvalMetricAdminOut], responses=_E)
def list_eval_metrics(db: Db, user: AdminUser) -> list[dto.EvalMetricAdminOut]:
    """Every eval metric (EV-nn) with its targets per tier and the metric-level ``active`` flag.
    (The tier-target editor stays ``/admin/eval-targets``.)"""
    return read.eval_metrics_out(db)


@router.post(
    "/admin/eval-metrics", response_model=dto.EvalMetricAdminOut, status_code=201, responses=_W
)
def create_eval_metric(body: dto.EvalMetricCreateIn, db: Db, user: AdminUser):
    """Add a metric (id EV-nn = next free). One target row per ``cfg.tiers`` tier; ``targets_by_tier``
    must cover every tier (422 otherwise); operator / value / unit only for ``auto`` metrics. New
    transitions only. Audit ``config:eval_metrics``."""
    _todo()


@router.patch(
    "/admin/eval-metrics/{metric_id}", response_model=dto.EvalMetricAdminOut, responses=_W
)
def update_eval_metric(metric_id: str, body: dto.EvalMetricUpdateIn, db: Db, user: AdminUser):
    """Edit name, evaluation mode, unit; ``active=false`` deactivates the metric for new results
    (existing results stay). 404 unknown metric."""
    _todo()


# --------------------------------------------------------------------------- settings documents


@router.get("/admin/thresholds", response_model=dto.ThresholdsOut, responses=_E)
def get_thresholds(db: Db, user: AdminUser) -> dto.ThresholdsOut:
    """RAG numbers, insight thresholds, calendar horizon, dashboard limits, narrative size, default
    tier / pricing basis / horizon / growth, and the ``rag_rule`` text generated from them."""
    return read.thresholds_out(db)


@router.put("/admin/thresholds", response_model=dto.ThresholdsOut, responses=_W)
def put_thresholds(body: dto.ThresholdsIn, db: Db, user: AdminUser):
    """Replace ``cfg.thresholds``. Guardrails: ranges (percent 0..100, days 0..365), amber not
    stricter than red (``amber_critical_gaps`` <= ``red_critical_gaps``, ``amber_lens_below`` >=
    ``red_lens_below``), ``default_tier`` is a defined tier, ``default_pricing_basis`` an active
    ``ocet_pricing_basis``. Live: RAG recalculates for all active transitions. Audit
    ``config:thresholds``."""
    _todo()


@router.get("/admin/labels", response_model=dto.LabelsOut, responses=_E)
def get_labels(db: Db, user: AdminUser) -> dto.LabelsOut:
    """Display overrides of workflow vocabulary (status words, RAG words, eval banner) with the
    defaults."""
    return read.labels_out(db)


@router.put("/admin/labels", response_model=dto.LabelsOut, responses=_W)
def put_labels(body: dto.LabelsDoc, db: Db, user: AdminUser):
    """Replace ``cfg.labels``. Keys must be known (422 for others); labels are non-empty and at
    most 120 characters. Wording only: behaviour never depends on a label. Audit ``config:labels``.
    """
    _todo()


@router.get("/admin/gates", response_model=dto.GatesOut, responses=_E)
def get_gates(db: Db, user: AdminUser) -> dto.GatesOut:
    """Gate label / short / description for every gate (codes, order and type are fixed in code),
    outcome label overrides, the decision-gate -> approval-chain map and the mocked approver."""
    return read.gates_out(db)


@router.put("/admin/gates", response_model=dto.GatesOut, responses=_W)
def put_gates(body: dto.GatesDoc, db: Db, user: AdminUser):
    """Replace the gate texts. Every gate code must be present and no unknown code (422);
    ``chain`` values must be existing approval chain types and only decision gates may have one;
    ``mock_approver_role`` must be an active role that ``can_approve``. Audit ``config:gates``."""
    _todo()


@router.get("/admin/lenses", response_model=dto.LensesOut, responses=_E)
def get_lenses(db: Db, user: AdminUser) -> dto.LensesOut:
    """The three lenses with question, colour hint, owner roles and sign-off role."""
    return read.lenses_out(db)


@router.put("/admin/lenses", response_model=dto.LensesDoc, responses=_W)
def put_lenses(body: dto.LensesDoc, db: Db, user: AdminUser):
    """Replace the lens texts. Exactly Business, Technical and Compliance (structural); owner and
    sign-off roles must be active roles. Audit ``config:lenses``. Returns the document."""
    _todo()


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
    """Save templates. Validates: known keys only; only the key's declared placeholders (an
    unknown ``{{name}}`` refuses the save with the name in the reason); length caps. Cannot change
    recipients or send policy (not part of a template). Audit ``config:message_templates``."""
    _todo()


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


# --------------------------------------------------------------------------- export / import, usage


@router.get("/admin/config-export", response_model=dto.ConfigExportOut, responses=_E)
def export_config(db: Db, user: AdminUser) -> dto.ConfigExportOut:
    """Stretch: every configuration section as JSON (settings, lists, fields, roles, matrix,
    tiering, templates). Demo configuration made in the UI is lost on a schema bump unless exported.
    """
    return read.config_export(db)


@router.post("/admin/config-import", response_model=dto.ConfigDiffOut, responses=_W)
def import_config(
    body: dto.ConfigImportIn,
    db: Db,
    user: AdminUser,
    dry_run: bool = Query(default=True),
):
    """Stretch: validate an export with the same rules as the editors and return the diff;
    ``dry_run=true`` (default) writes nothing. 422 with reasons when a section is invalid, 409 when
    ``schema_version`` differs from the server's."""
    _todo()


@router.get("/admin/usage", response_model=dto.UsageOut, responses=_E)
def get_usage(
    db: Db,
    user: AdminUser,
    kind: str = Query(description="project_type | portfolio | option | role | checklist"),
    key: str = Query(description='the code / name; for kind=option "<list key>:<value>"'),
) -> dto.UsageOut:
    """Where a value is used: count and the first 10 transitions. 422 unknown ``kind``."""
    return read.usage(db, kind, key)
