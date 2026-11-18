"""Orion agent DTOs (spec §8.15, §9 "Orion agent"). Every Orion output is labelled "Orion agent" with an
AI badge in the UI (BR-050)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef
from app.schemas.gates import ReadinessCheckOut
from app.schemas.leadership import LeadershipUpdateOut


class InsightActionOut(BaseModel):
    """A button on an insight. M2: ``kind="link"`` navigates to ``href``. M8 adds proposal kinds that a
    permitted human accepts (BR-050)."""

    label: str
    kind: str = "link"
    href: str | None = None
    proposal_id: int | None = None


class InsightOut(BaseModel):
    id: str  # deterministic key, e.g. "TR-0001:critical-gap"
    text: str
    severity: str  # critical | warning | info | success
    transition_id: str | None = None
    actions: list[InsightActionOut] = []


class InsightsOut(BaseModel):
    scope: str  # dashboard | control-tower | transition
    scope_id: str | None = None
    generated_by: str = "Orion agent"
    insights: list[InsightOut]


# ---------------------------------------------------------------------------------------------
# M8a: chat, proposals (BR-050), leadership messages (FR-090, FR-080)
# ---------------------------------------------------------------------------------------------

QuickAction = Literal[
    "start_gate_review",
    "assess_gate_readiness",
    "track_owner_actions",
    "draft_owner_reminders",
    "create_leadership_update",
    "create_support_model",
    "create_update_ocet",
]
ProposalKind = Literal[
    "create_action",
    "draft_chaser",
    "request_inputs",
    "request_exception",
    "request_approval",
    "accept_applicability",
    # --- natural-language actions (BR-050: every one is executed by a permitted human) ---
    "create_transition",  # hand-off: opens the pre-filled intake form, creates nothing
    "update_transition",  # PATCH /transitions/{id} (intake fields only; never tier or gate)
    "update_item",  # PATCH /items/{id}: owner, note, gap severity, B/T status (never Compliance)
    "add_evidence",  # POST /transitions/{id}/evidence: link or email sign-off text, status Submitted
]
ProposalStatus = Literal["Open", "Accepted", "Dismissed"]
FormFieldKind = Literal["transition", "gate", "scope", "portfolio", "select", "text"]
ORION_AGENT = "Orion agent"


class ChatContext(BaseModel):
    transition_id: str | None = None  # transition open in the UI (defaults for forms)
    page: str | None = None
    item_id: str | None = None  # playbook item id open in the UI, e.g. "S3-019" ("this item")


class ChatIn(BaseModel):
    """Exactly one of ``message`` (free text) or ``quick_action`` must be given (422 otherwise).
    ``form_data`` is the submitted form of a previous ``form`` message (keys = field names); without
    it a quick action answers with its form (form-first, FR-090)."""

    message: str | None = Field(default=None, max_length=2000)
    quick_action: QuickAction | None = None
    form_data: dict[str, Any] | None = None
    context: ChatContext = ChatContext()


class FormFieldOption(BaseModel):
    value: str
    label: str


class FormField(BaseModel):
    name: str  # key in ChatIn.form_data: "transition_id", "gate", "scope", "scope_id"
    label: str
    kind: FormFieldKind
    options: list[FormFieldOption] | None = None
    required: bool = True
    default: str | None = None


class _MessageBase(BaseModel):
    generated_by: str = ORION_AGENT  # AI badge (BR-050)


class TextMessage(_MessageBase):
    type: Literal["text"] = "text"
    text: str


class FormMessage(_MessageBase):
    type: Literal["form"] = "form"
    form_id: str  # equals the quick_action name
    title: str
    fields: list[FormField]
    submit_label: str
    quick_action: QuickAction


class ReadinessMessage(_MessageBase):
    type: Literal["readiness"] = "readiness"
    check: ReadinessCheckOut


class TableColumn(BaseModel):
    key: str
    label: str


class TableMessage(_MessageBase):
    type: Literal["table"] = "table"
    title: str
    columns: list[TableColumn]
    rows: list[dict[str, Any]]
    footnote: str | None = None


class DraftSummary(BaseModel):
    id: int
    kind: str
    subject: str
    to: list[str]
    transition_id: str | None = None


class DraftsMessage(_MessageBase):
    type: Literal["drafts"] = "drafts"
    title: str
    drafts: list[DraftSummary]
    link: str = "/drafts"


class LinkMessage(_MessageBase):
    type: Literal["link"] = "link"
    label: str
    href: str
    description: str | None = None


class ProposalOut(BaseModel):
    id: int
    transition_id: str | None = None
    kind: ProposalKind
    title: str
    # kind-specific payload (ids are strings unless noted):
    #  create_action {title, item_ids, owner_user_id, due_date (ISO), priority}
    #  draft_chaser {item_ids}            request_inputs {version_id, line_ids}
    #  request_exception {item_id, text}  request_approval {gate}
    #  accept_applicability {decisions: [{item_id, applies, reason?}]}
    #  create_transition CreateTransitionPayload   update_transition UpdateTransitionPayload
    #  update_item UpdateItemPayload                add_evidence AddEvidencePayload
    #  (the four new kinds are validated against ``PAYLOAD_MODELS``)
    payload: dict[str, Any]
    status: ProposalStatus
    created_at: datetime
    accepted_by: PersonRef | None = None
    accepted_at: datetime | None = None
    can_accept: bool  # the current user holds the permission of the underlying operation
    accept_denied_reason: str | None = None
    generated_by: str = ORION_AGENT


class ProposalMessage(_MessageBase):
    type: Literal["proposal"] = "proposal"
    proposal: ProposalOut


class LeadershipMessage(_MessageBase):
    type: Literal["leadership"] = "leadership"
    update: LeadershipUpdateOut


OrionMessage = Annotated[
    TextMessage
    | FormMessage
    | ReadinessMessage
    | TableMessage
    | DraftsMessage
    | LinkMessage
    | ProposalMessage
    | LeadershipMessage,
    Field(discriminator="type"),
]


class ChatOut(BaseModel):
    messages: list[OrionMessage]


class AcceptOut(BaseModel):
    proposal: ProposalOut  # status Accepted, accepted_by/at set
    # kind-specific ids: create_action {action_id}; draft_chaser/request_inputs/request_approval
    # {draft_id}; request_exception {exception_id}; accept_applicability {accepted: int}
    # new kinds: create_transition {handoff: true} (nothing is created); update_transition
    # {transition_id, changed: [field names]}; update_item {item_id, changed: [...]};
    # add_evidence {evidence_id}
    result: dict[str, Any]
    navigate_to: str | None = None  # create_transition: "/transitions/new?proposal=<id>"


# ---------------------------------------------------------------------------------------------
# Natural-language actions: extraction DTOs and proposal payloads
# ---------------------------------------------------------------------------------------------

FieldState = Literal["found", "inferred", "ambiguous", "missing"]
FieldSource = Literal["servicenow", "text", "document", "context", "inferred"]
InputSource = Literal["chat", "text", "email", "document"]
EXTRACT_MAX_CHARS = 20000  # pasted text / document text is truncated to this (truncated=true)
EXTRACT_MAX_BYTES = 5 * 1024 * 1024  # uploaded document size limit (413 above)
EXTRACT_EXTENSIONS = (".txt", ".md", ".vtt", ".docx")  # audio/video are not accepted here


class ExtractedField(BaseModel):
    """One intake field Orion looked for. The UI shows state + source + confidence next to the value
    so the human can check it (BR-050)."""

    name: str  # TransitionCreateIn key, "sites", or a role picker such as "architect_user_id"
    label: str
    value: Any = (
        None  # option label / user id / ISO date / list of {site_id, site_key}; None if missing
    )
    display: str | None = None  # human text of the value (user name instead of id)
    state: FieldState
    source: FieldSource | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: str | None = Field(default=None, max_length=300)  # quoted words it came from
    candidates: list[FormFieldOption] = []  # ambiguous: the options to choose from
    note: str | None = None  # e.g. "From ServiceNow PRJ123456", "Two users match 'Mei'"
    required: bool = False


class CreateTransitionPayload(BaseModel):
    """Payload of a ``create_transition`` proposal and the body of GET /orion/proposals/{id}.

    ``prefill`` only contains keys of ``TransitionCreateIn`` whose state is found or inferred (an
    ambiguous or missing field is absent, never guessed), so the UI can spread it into the form."""

    prefill: dict[str, Any]
    fields: list[ExtractedField]  # every field considered, in intake-form order
    missing_fields: list[str]  # required field names with no value (UI highlights them)
    ambiguous_fields: list[str]
    servicenow_project_id: str | None = None
    servicenow_found: bool | None = None  # None when the text had no PRJ id
    source: InputSource
    source_name: str | None = None  # uploaded filename
    source_excerpt: str = Field(default="", max_length=1500)
    summary: str = ""  # "Found 7 of 9 fields - 2 need your input"
    warnings: list[str] = []  # e.g. "TR-0019 already exists for PRJ0052210"


class UpdateTransitionPayload(BaseModel):
    transition_id: str
    changes: dict[str, Any]  # subset of TransitionUpdateIn keys (never tier/gate/status)
    fields: list[ExtractedField] = []
    source_excerpt: str = Field(default="", max_length=1500)


class UpdateItemPayload(BaseModel):
    transition_id: str
    item_id: str  # playbook item id, e.g. "S3-019"
    # subset of {status, gap_severity, note, owner_user_id}; status only for Business/Technical items
    changes: dict[str, Any]
    current: dict[str, Any] = {}  # same keys, current values, for a before/after display
    source_excerpt: str = Field(default="", max_length=1500)


class AddEvidencePayload(BaseModel):
    transition_id: str
    item_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    type: Literal["Link", "Email sign-off"]
    url: str | None = None  # type Link
    text: str | None = None  # type Email sign-off: VERBATIM text the user pasted, never generated


PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "create_transition": CreateTransitionPayload,
    "update_transition": UpdateTransitionPayload,
    "update_item": UpdateItemPayload,
    "add_evidence": AddEvidencePayload,
}


class IntentMatch(BaseModel):
    intent: str  # key of INTENT_CATALOG
    confidence: float = Field(ge=0, le=1)
    summary: str


class ExtractOut(BaseModel):
    """Response of POST /orion/extract: the same cards as chat, plus what was understood."""

    messages: list[OrionMessage]
    intents: list[IntentMatch]
    source: InputSource
    source_name: str | None = None
    characters_read: int
    truncated: bool = False  # input was cut at EXTRACT_MAX_CHARS


class IntentSpecOut(BaseModel):
    """One row of the intent catalog (GET /orion/intents) used for the panel's example chips."""

    intent: str
    label: str
    examples: list[str]
    result: Literal["message", "link", "form", "proposal", "refusal"]
    proposal_kind: ProposalKind | None = None
    permission: str | None = None  # Perm value needed to ACCEPT / run; None = any signed-in user
    allowed: bool  # current user holds that permission
    denied_reason: str | None = None


class IntentCatalogOut(BaseModel):
    intents: list[IntentSpecOut]
    refusals: list[str]  # plain-language list of what Orion will never do
