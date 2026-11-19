"""Support model generator DTOs (spec 6 SupportModel, 8.8 FR-040, 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.approvals import ApprovalStatus, ApprovalStepOut

SupportModelStatus = Literal["Not started", "Draft", "In review", "Agreed"]
InputFileKind = Literal["recording", "transcript", "design", "diagram", "other"]
SourceType = Literal["diagram", "recording", "document"]

ALLOWED_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".m4a",
    ".vtt",
    ".txt",
    ".docx",
    ".pdf",
    ".png",
    ".jpg",
)
INFO_NOTE = "Orion doesn't join meetings. Upload the recording or transcript after the walkthrough."


# ------------------------------------------------------------------ landscape (spec 8.8 JSON)


# Size limits keep the editable landscape (and the PPT built from it) bounded.
Text = Annotated[str, StringConstraints(max_length=1000)]


class ComponentIO(BaseModel):
    """A landscape component. ``relation`` is "bidirectional" | "inbound" | "outbound" |
    "child_of:<name>" (name of another component). ``target`` is the component name the edge
    points to (None = the central app). Layout is computed client-side (radial)."""

    id: str = Field(min_length=1, max_length=20)  # c1..cn
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=60)  # Integration, Data flow, Identity, Team ...
    relation: str = Field(default="bidirectional", max_length=200)
    target: str | None = Field(default=None, max_length=120)


class SupportTiersIO(BaseModel):
    L1: str = Field(default="", max_length=1000)
    L2: str = Field(default="", max_length=1000)
    L3: str = Field(default="", max_length=1000)


class ContactIO(BaseModel):
    party: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    sla: str = Field(default="", max_length=200)


class SourceIO(BaseModel):
    type: SourceType
    ref: str = Field(
        max_length=500
    )  # diagram/page name, or recording timestamp such as "walkthrough.mp4 @ 12:40"


class OpenQuestionIO(BaseModel):
    """An open question for the architect and its answer. Answered = non-empty ``answer``.
    A plain string (landscapes stored before answers existed) loads as an unanswered question."""

    question: Text = Field(min_length=1)
    answer: str = Field(default="", max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def _from_plain_string(cls, value: object) -> object:
        return {"question": value} if isinstance(value, str) else value

    @property
    def answered(self) -> bool:
        return bool(self.answer.strip())


class LandscapeIn(BaseModel):
    """Editable landscape (request body of PUT, and shape of the generated JSON)."""

    central_app: str = Field(min_length=1, max_length=200)
    hosting: str = Field(default="", max_length=500)
    vendor: str = Field(default="", max_length=500)
    supplier: str = Field(default="", max_length=500)
    vendor_responsibilities: list[Text] = Field(default=[], max_length=30)
    components: list[ComponentIO] = Field(default=[], max_length=24)
    support_tiers: SupportTiersIO = SupportTiersIO()
    contacts: list[ContactIO] = Field(default=[], max_length=50)
    open_questions: list[OpenQuestionIO] = Field(default=[], max_length=50)
    sources: list[SourceIO] = Field(default=[], max_length=30)


class LandscapeOut(LandscapeIn):
    """Same fields as the input; returned by the API."""


# ------------------------------------------------------------------ inputs


class InputFileOut(BaseModel):
    filename: str
    kind: InputFileKind
    url: str  # fake SharePoint URL
    size: int
    uploaded_at: datetime


class ConfluencePageOut(BaseModel):
    title: str
    summary: str
    diagrams: list[str] = []
    url: str


class ConfluenceSummaryOut(BaseModel):
    title: str
    summary: str
    diagrams: list[str] = []


class ConfluenceFetchIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class SupportInputsOut(BaseModel):
    confluence_url: str | None = None
    confluence: ConfluenceSummaryOut | None = None
    files: list[InputFileOut] = []


# ------------------------------------------------------------------ view


class PptxInfoOut(BaseModel):
    version: int
    evidence_id: str
    filename: str
    generated_at: datetime


class SupportApprovalOut(BaseModel):
    request_id: str
    status: ApprovalStatus
    steps: list[ApprovalStepOut]


class LinkedItemOut(BaseModel):
    item_id: str  # FW-027 .. FW-035 and Support Model sheet items
    title: str
    status: str


class SupportModelOut(BaseModel):
    id: int | None  # None when nothing exists yet (status "Not started")
    transition_id: str
    transition_name: str
    version: int  # 0 when not started
    status: SupportModelStatus
    inputs: SupportInputsOut
    landscape: LandscapeOut | None
    pptx: PptxInfoOut | None
    approval: SupportApprovalOut | None
    can_edit: bool  # Perm.EDIT_SUPPORT_MODEL and status in (Not started, Draft)
    edit_denied_reason: str | None
    info_note: str = INFO_NOTE
    linked_items: list[LinkedItemOut] = []


class GenerateStepOut(BaseModel):
    label: str
    duration_ms: int


class GenerateOut(BaseModel):
    support_model: SupportModelOut
    # Simulated client-side: "Reading transcript", "Reading diagrams and documents",
    # "Drafting landscape and support flows" (~1500 ms each)
    steps: list[GenerateStepOut]


class PutLandscapeIn(BaseModel):
    landscape: LandscapeIn


class PptxOut(BaseModel):
    evidence_id: str
    filename: str
    version: int
    download_path: str  # "/evidence/<id>/download"


class SupportModelListItemOut(BaseModel):
    id: int
    transition_id: str
    transition_name: str
    portfolio: str
    central_app: str
    version: int
    status: SupportModelStatus
    updated_at: datetime
    pptx_available: bool


class QuestionDraftOut(BaseModel):
    """Result of "Draft question to architect": an Orion draft in the drafts queue."""

    draft_id: int
    message: str = "Orion drafted a question to the architect. Review and send it from the drafts."
