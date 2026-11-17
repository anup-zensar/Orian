"""Support model domain logic (FR-040, BR-030 linked items, BR-041 chain). Implemented in M7.

Status flow: Not started (no row) -> Draft -> In review -> Agreed. Regeneration after Agreed
creates a new version row (version + 1, status Draft). All writes are audited and the functions do
not commit (the router does).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.deps import ensure
from app.domain import audit
from app.domain.ids import next_id
from app.errors import BadRequest, Conflict, NotFound
from app.models import (
    ApprovalRequest,
    Evidence,
    OrionDraft,
    Portfolio,
    SupportModel,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules.constants import (
    ACTOR_HUMAN,
    ACTOR_ORION,
    ACTOR_WORKFLOW,
    done_status_for,
    is_open_status,
)
from app.schemas.support_models import (
    ALLOWED_EXTENSIONS,
    INFO_NOTE,
    ConfluencePageOut,
    ConfluenceSummaryOut,
    GenerateOut,
    GenerateStepOut,
    InputFileOut,
    LandscapeIn,
    LandscapeOut,
    LinkedItemOut,
    PptxInfoOut,
    PptxOut,
    SupportApprovalOut,
    SupportInputsOut,
    SupportModelListItemOut,
    SupportModelOut,
)
from app.services.factory import (
    get_confluence_service,
    get_document_store,
    get_support_model_generator,
    get_transcript_service,
)

LINKED_MODULE = "SUPPORT_MODEL"
PPTX_ITEM_ID = "FW-035"  # evidence of the generated PPT is linked to this item
GENERATE_STEPS: list[tuple[str, int]] = [
    ("Reading transcript", 1500),
    ("Reading diagrams and documents", 1500),
    ("Drafting landscape and support flows", 1500),
]
RELATIONS = ("bidirectional", "inbound", "outbound")
_KIND_BY_EXT = {
    ".mp4": "recording",
    ".m4a": "recording",
    ".vtt": "transcript",
    ".txt": "transcript",
    ".docx": "design",
    ".pdf": "design",
    ".png": "diagram",
    ".jpg": "diagram",
}
_TEXT_KINDS = ("recording", "transcript")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


# ------------------------------------------------------------------ helpers


def _transition(db: Session, transition_id: str) -> Transition:
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


def _model(db: Session, support_model_id: int) -> SupportModel:
    model = db.get(SupportModel, support_model_id)
    if model is None:
        raise NotFound(f"Support model {support_model_id} not found")
    return model


def _latest(db: Session, transition_id: str) -> SupportModel | None:
    return db.scalars(
        select(SupportModel)
        .where(SupportModel.transition_id == transition_id)
        .order_by(SupportModel.version.desc(), SupportModel.id.desc())
    ).first()


def _inputs(model: SupportModel | None) -> dict[str, Any]:
    raw = dict(model.inputs or {}) if model else {}
    return {
        "confluence_url": raw.get("confluence_url"),
        "confluence": raw.get("confluence"),
        "files": list(raw.get("files") or []),
    }


def _snap(model: SupportModel) -> dict[str, Any]:
    return {
        "version": model.version,
        "status": model.status,
        "approval_request_id": model.approval_request_id,
        "pptx_version": model.pptx_version,
    }


def _central(model: SupportModel) -> str:
    return str((model.landscape or {}).get("central_app") or "")


def validate_landscape(landscape: LandscapeIn) -> None:
    """422 on duplicate ids, unknown relation, or a child_of / target naming an unknown component."""
    reasons: list[str] = []
    ids = [c.id for c in landscape.components]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        reasons.append(f"Component id '{dup}' is used more than once")
    all_names = [c.name for c in landscape.components]
    for dup in sorted({n for n in all_names if all_names.count(n) > 1}):
        reasons.append(f"Component name '{dup}' is used more than once")
    names = set(all_names)
    parents = {
        c.name: c.relation.split(":", 1)[1]
        for c in landscape.components
        if c.relation.startswith("child_of:")
    }
    for start in sorted(parents):
        node, hops = parents[start], 0
        while node in parents and node != start and hops <= len(parents):
            node, hops = parents[node], hops + 1
        if node == start and parents[start] != start:
            reasons.append(f"'{start}' is part of a child_of cycle")
    for comp in landscape.components:
        rel = comp.relation
        if rel.startswith("child_of:"):
            parent = rel.split(":", 1)[1]
            if parent not in names:
                reasons.append(f"'{comp.name}' is a child of unknown component '{parent}'")
            elif parent == comp.name:
                reasons.append(f"'{comp.name}' cannot be its own parent")
        elif rel not in RELATIONS:
            reasons.append(f"'{comp.name}' has unknown relation '{rel}'")
        if comp.target is not None and comp.target not in names:
            reasons.append(f"'{comp.name}' points to unknown component '{comp.target}'")
    if reasons:
        raise BadRequest("Invalid landscape", reasons)


def _normalise_ids(landscape: dict[str, Any]) -> dict[str, Any]:
    for i, component in enumerate(landscape.get("components", []), start=1):
        component["id"] = f"c{i}"
    return landscape


def _landscape_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Round-trip through the schema so stored JSON always has every field."""
    return LandscapeIn.model_validate(raw).model_dump()


def _linked_items(db: Session, transition_id: str) -> list[TransitionItem]:
    rows = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition_id,
            TransitionItem.linked_module == LINKED_MODULE,
        )
    ).all()
    return sorted(rows, key=lambda r: r.playbook_item_id)


def _pptx_info(db: Session, model: SupportModel) -> PptxInfoOut | None:
    if not model.pptx_version or not model.evidence_id:
        return None
    evidence = db.get(Evidence, model.evidence_id)
    if evidence is None:
        return None
    path = evidence.file_path or model.generated_pptx_path or ""
    return PptxInfoOut(
        version=model.pptx_version,
        evidence_id=evidence.id,
        filename=PurePosixPath(path).name,
        generated_at=evidence.created_at,
    )


def _approval(db: Session, model: SupportModel, user: User) -> SupportApprovalOut | None:
    if not model.approval_request_id:
        return None
    request = db.get(ApprovalRequest, model.approval_request_id)
    if request is None:
        return None
    from app.routers.approvals import approval_out  # DTO builder of the approvals area

    out = approval_out(db, request, user)
    return SupportApprovalOut(request_id=out.id, status=out.status, steps=out.steps)


def _view(
    db: Session, transition: Transition, model: SupportModel | None, user: User
) -> SupportModelOut:
    status = model.status if model else "Not started"
    denied: str | None = None
    if not has_perm(user.role, Perm.EDIT_SUPPORT_MODEL):
        denied = DENIAL_REASONS[Perm.EDIT_SUPPORT_MODEL]
    elif status not in ("Not started", "Draft"):
        denied = f"Support model is {status}"
    inputs = _inputs(model)
    confluence = inputs["confluence"]
    return SupportModelOut(
        id=model.id if model else None,
        transition_id=transition.id,
        transition_name=transition.name,
        version=model.version if model else 0,
        status=status,  # type: ignore[arg-type]
        inputs=SupportInputsOut(
            confluence_url=inputs["confluence_url"],
            confluence=ConfluenceSummaryOut(**confluence) if confluence else None,
            files=[InputFileOut(**f) for f in inputs["files"]],
        ),
        landscape=LandscapeOut(**model.landscape) if model and model.landscape else None,
        pptx=_pptx_info(db, model) if model else None,
        approval=_approval(db, model, user) if model else None,
        can_edit=denied is None,
        edit_denied_reason=denied,
        info_note=INFO_NOTE,
        linked_items=[
            LinkedItemOut(item_id=i.playbook_item_id, title=i.playbook_item.title, status=i.status)
            for i in _linked_items(db, transition.id)
        ],
    )


def _view_of(db: Session, model: SupportModel, user: User) -> SupportModelOut:
    return _view(db, _transition(db, model.transition_id), model, user)


# ------------------------------------------------------------------ public API


def get_view(db: Session, transition_id: str, user: User) -> SupportModelOut:
    """Latest SupportModel of the transition as a DTO (see router docstring)."""
    transition = _transition(db, transition_id)
    return _view(db, transition, _latest(db, transition_id), user)


def fetch_confluence(url: str) -> ConfluencePageOut:
    """ConfluenceService.fetch(url). 422 when blank / not http(s)."""
    clean = (url or "").strip()
    if not clean or not _URL_RE.fullmatch(clean):
        raise BadRequest(
            "Invalid link", ["Enter a Confluence link starting with http:// or https://"]
        )
    page = get_confluence_service().fetch(clean)
    return ConfluencePageOut(
        title=page["title"],
        summary=page["summary"],
        diagrams=list(page.get("diagrams", [])),
        url=page["url"],
    )


def _ensure_editable_row(db: Session, transition: Transition, user: User) -> SupportModel:
    latest = _latest(db, transition.id)
    if latest is not None and latest.status != "Draft":
        raise Conflict(
            "Support model cannot be changed",
            [f"The latest support model is {latest.status}. Generate a new version first."],
        )
    if latest is not None:
        return latest
    model = SupportModel(
        transition_id=transition.id,
        version=1,
        status="Draft",
        inputs={"confluence_url": None, "confluence": None, "files": []},
        landscape=None,
        pptx_version=0,
        created_by=user.id,
    )
    db.add(model)
    db.flush()
    return model


def save_inputs(
    db: Session,
    transition_id: str,
    *,
    confluence_url: str | None,
    files: list[tuple[str, BinaryIO]],
    user: User,
) -> SupportModelOut:
    """Store inputs on the latest Draft model (creates a Draft v1 row when none exists)."""
    from app.domain.evidence import read_upload
    from app.services.mock.document_store import sanitize_filename

    ensure(user, Perm.EDIT_SUPPORT_MODEL)
    transition = _transition(db, transition_id)
    latest = _latest(db, transition_id)
    if latest is not None and latest.status != "Draft":
        raise Conflict(
            "Support model cannot be changed",
            [f"The latest support model is {latest.status}. Generate a new version first."],
        )

    reasons: list[str] = []
    payloads: list[tuple[str, str, bytes]] = []
    for raw_name, handle in files:
        name = sanitize_filename(raw_name)
        ext = PurePosixPath(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            reasons.append(f"{name}: type not allowed (use {', '.join(ALLOWED_EXTENSIONS)})")
            continue
        content = read_upload(handle)
        if not content:
            reasons.append(f"{name}: the file is empty")
            continue
        payloads.append((name, _KIND_BY_EXT[ext], content))
    page = None
    url = None
    if confluence_url is not None and confluence_url.strip():
        url = confluence_url.strip()
        if not _URL_RE.fullmatch(url):
            reasons.append("The Confluence link must start with http:// or https://")
    if reasons:
        raise BadRequest("Invalid inputs", reasons)
    if url:
        page = fetch_confluence(url)

    model = _ensure_editable_row(db, transition, user)
    before = _inputs(model)
    inputs = _inputs(model)
    store = get_document_store()
    stored = {f["filename"]: f for f in inputs["files"]}
    for name, kind, content in payloads:
        saved = store.save(transition.id, name, content)
        stored[name] = {
            "filename": name,
            "kind": kind,
            "url": saved["url"],
            "size": saved["size"],
            "uploaded_at": clock.now().isoformat(),
            "path": saved["path"],
        }
    inputs["files"] = list(stored.values())
    if confluence_url is not None:
        if page is not None:
            inputs["confluence_url"] = page.url
            inputs["confluence"] = ConfluenceSummaryOut(
                title=page.title, summary=page.summary, diagrams=page.diagrams
            ).model_dump()
        else:
            inputs["confluence_url"] = None
            inputs["confluence"] = None
    model.inputs = inputs
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="SupportModel",
        entity_id=model.id,
        action="inputs_saved",
        transition_id=transition.id,
        before={
            "confluence_url": before["confluence_url"],
            "files": [f["filename"] for f in before["files"]],
        },
        after={
            "confluence_url": inputs["confluence_url"],
            "files": [f["filename"] for f in inputs["files"]],
        },
    )
    return _view(db, transition, model, user)


def _transition_ctx(db: Session, transition: Transition) -> dict[str, Any]:
    portfolio = db.get(Portfolio, transition.portfolio)
    return {
        "id": transition.id,
        "name": transition.name,
        "portfolio": transition.portfolio,
        "project_type": transition.project_type,
        "focus_areas": list(portfolio.focus_areas) if portfolio else [],
    }


def generate(db: Session, transition_id: str, user: User) -> GenerateOut:
    """Run SupportModelGenerator.generate and store the landscape (see router docstring)."""
    ensure(user, Perm.EDIT_SUPPORT_MODEL)
    transition = _transition(db, transition_id)
    latest = _latest(db, transition_id)
    if latest is None:
        raise Conflict("No inputs yet", ["Add a Confluence link or upload at least one file first"])
    if latest.status == "In review":
        raise Conflict("Support model is in review", ["Wait for the review to finish first"])
    inputs = _inputs(latest)
    if not inputs["confluence_url"] and not inputs["files"]:
        raise Conflict("No inputs yet", ["Add a Confluence link or upload at least one file first"])

    store = get_document_store()
    transcripts = get_transcript_service()
    texts: dict[str, str] = {}
    for entry in inputs["files"]:
        if entry["kind"] in _TEXT_KINDS or entry["filename"].lower().endswith(".docx"):
            try:
                texts[entry["filename"]] = transcripts.get_text(
                    entry["filename"], store.read(entry["path"])
                )
            except NotFound:
                texts[entry["filename"]] = ""
    generator_inputs = {
        "confluence_url": inputs["confluence_url"],
        "confluence": inputs["confluence"],
        "files": [{"filename": f["filename"], "kind": f["kind"]} for f in inputs["files"]],
        "texts": texts,
    }
    landscape = _landscape_dict(
        _normalise_ids(
            get_support_model_generator().generate(
                _transition_ctx(db, transition), generator_inputs
            )
        )
    )

    if latest.status == "Agreed":
        model = SupportModel(
            transition_id=transition.id,
            version=latest.version + 1,
            status="Draft",
            inputs=dict(latest.inputs or {}),
            landscape=landscape,
            pptx_version=0,
            created_by=user.id,
        )
        db.add(model)
        before: dict[str, Any] | None = None
    else:
        model = latest
        before = _snap(model)
        model.landscape = landscape
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_ORION,
        entity="SupportModel",
        entity_id=model.id,
        action="generated",
        transition_id=transition.id,
        before=before,
        after={**_snap(model), "central_app": landscape["central_app"]},
        note="Landscape drafted by Orion agent; a human reviews and edits it",
    )
    return GenerateOut(
        support_model=_view(db, transition, model, user),
        steps=[GenerateStepOut(label=label, duration_ms=ms) for label, ms in GENERATE_STEPS],
    )


def update_landscape(
    db: Session, support_model_id: int, landscape: LandscapeIn, user: User
) -> SupportModelOut:
    """Replace the landscape of a Draft model (see router docstring)."""
    ensure(user, Perm.EDIT_SUPPORT_MODEL)
    model = _model(db, support_model_id)
    if model.status != "Draft":
        raise Conflict(
            "Support model cannot be edited",
            [f"The support model is {model.status}; only Draft can be edited"],
        )
    validate_landscape(landscape)
    before = model.landscape
    model.landscape = landscape.model_dump()
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="SupportModel",
        entity_id=model.id,
        action="landscape_edited",
        transition_id=model.transition_id,
        before={"landscape": before},
        after={"landscape": model.landscape},
    )
    return _view_of(db, model, user)


def send_for_review(db: Session, support_model_id: int, user: User) -> SupportModelOut:
    """Draft -> In review; creates the SUPPORT_MODEL approval chain."""
    from app.domain import approvals

    ensure(user, Perm.EDIT_SUPPORT_MODEL)
    model = _model(db, support_model_id)
    if model.status != "Draft":
        raise Conflict("Support model is not a draft", [f"The support model is {model.status}"])
    if not model.landscape:
        raise Conflict("Nothing to review", ["Generate the support model first"])
    transition = _transition(db, model.transition_id)
    request = approvals.create_approval_request(
        db,
        type=LINKED_MODULE,
        transition=transition,
        created_by=user,
        created_source=ACTOR_HUMAN,
        subject_id=str(model.id),
        subject_label=f"Support model v{model.version} - {_central(model)}",
    )
    before = _snap(model)
    model.status = "In review"
    model.approval_request_id = request.id
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="SupportModel",
        entity_id=model.id,
        action="sent_for_review",
        transition_id=model.transition_id,
        before=before,
        after=_snap(model),
    )
    return _view_of(db, model, user)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:50].strip("-") or "app"


def build_pptx(db: Session, support_model_id: int, user: User) -> PptxOut:
    """Generate the .pptx, store it, create the Generated Evidence row on FW-035."""
    from app.services.pptx_support_model import build_support_model_pptx

    ensure(user, Perm.EDIT_SUPPORT_MODEL)
    model = _model(db, support_model_id)
    if not model.landscape:
        raise Conflict("Nothing to export", ["Generate the support model first"])
    latest = _latest(db, model.transition_id)
    if latest is not None and latest.id != model.id:
        raise Conflict(
            "Superseded support model",
            [f"v{model.version} is superseded by v{latest.version} - export the latest version"],
        )
    transition = _transition(db, model.transition_id)
    version = model.pptx_version + 1
    central = _central(model)
    content = build_support_model_pptx(
        model.landscape,
        {
            "transition_name": transition.name,
            "portfolio": transition.portfolio,
            "version": model.version,
            "date": clock.today().isoformat(),
            "reviewed_by": user.name,
            "status": model.status,
        },
    )
    saved = get_document_store().save_generated(
        transition.id, f"support-model-{_slug(central)}-v{version}.pptx", content
    )
    item = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition.id,
            TransitionItem.playbook_item_id == PPTX_ITEM_ID,
        )
    ).first()
    evidence = Evidence(
        id=next_id(db, Evidence.id, "EVD-"),
        transition_id=transition.id,
        transition_item_id=item.id if item else None,
        title=f"Support model - {central} (v{model.version}, PPT v{version})",
        type="Generated",
        url=saved["url"],
        file_path=saved["path"],
        submitted_by=user.id,
        status="Submitted",
    )
    db.add(evidence)
    db.flush()
    model.pptx_version = version
    model.generated_pptx_path = saved["path"]
    model.evidence_id = evidence.id
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="SupportModel",
        entity_id=model.id,
        action="pptx_generated",
        transition_id=transition.id,
        after={"pptx_version": version, "evidence_id": evidence.id, "file": saved["filename"]},
    )
    return PptxOut(
        evidence_id=evidence.id,
        filename=saved["filename"],
        version=version,
        download_path=f"/evidence/{evidence.id}/download",
    )


def list_models(db: Session, user: User, q: str | None = None) -> list[SupportModelListItemOut]:
    """Latest model per transition, optional case-insensitive filter, newest first."""
    rows = db.scalars(
        select(SupportModel).order_by(SupportModel.version.desc(), SupportModel.id.desc())
    ).all()
    latest: dict[str, SupportModel] = {}
    for row in rows:
        latest.setdefault(row.transition_id, row)
    needle = (q or "").strip().lower()
    out: list[SupportModelListItemOut] = []
    for model in latest.values():
        transition = db.get(Transition, model.transition_id)
        if transition is None:
            continue
        central = _central(model)
        if needle and needle not in transition.name.lower() and needle not in central.lower():
            continue
        out.append(
            SupportModelListItemOut(
                id=model.id,
                transition_id=transition.id,
                transition_name=transition.name,
                portfolio=transition.portfolio,
                central_app=central,
                version=model.version,
                status=model.status,  # type: ignore[arg-type]
                updated_at=model.updated_at,
                pptx_available=bool(model.pptx_version),
            )
        )
    out.sort(key=lambda r: (r.updated_at, r.id), reverse=True)
    return out


def draft_question_to_architect(
    db: Session, support_model_id: int, question_index: int, user: User
) -> OrionDraft:
    """Orion draft (Input request) to the transition architect for one open question."""
    from app.domain.drafts import create_draft
    from app.domain.html_sanitize import escape_text as esc

    ensure(user, Perm.EDIT_SUPPORT_MODEL)
    model = _model(db, support_model_id)
    questions = list((model.landscape or {}).get("open_questions") or [])
    if question_index < 0 or question_index >= len(questions):
        raise NotFound(f"Open question {question_index} not found")
    question = str(questions[question_index])
    transition = _transition(db, model.transition_id)
    architect = db.get(User, transition.architect_user_id) if transition.architect_user_id else None
    focal = db.get(User, transition.or_focal_user_id)
    to = [architect.email] if architect and architect.email else []
    cc = [focal.email] if focal and focal.email and focal.email not in to else []
    greeting = f"Hi {esc(architect.name)}," if architect else "Hi,"
    link = f"/transitions/{transition.id}/support-model"
    body = (
        f"<p>{greeting}</p>"
        f"<p>While drafting the support model for {esc(transition.name)} we need your input on "
        f"one open question:</p><p><b>{esc(question)}</b></p>"
        f'<p>You can see the full landscape in Orion: <a href="{esc(link)}">support model</a>.</p>'
        f"<p>Thank you,<br>{esc(user.name)}<br><i>Drafted by Orion agent</i></p>"
    )
    return create_draft(
        db,
        kind="Input request",
        transition=transition,
        to=to,
        cc=cc,
        subject=f"Question for the support model: {transition.name}"[:300],
        body_html=body,
        created_source="Orion agent",
        related_ids=[transition.id, f"SM-{model.id}"],
    )


def on_support_model_chain_completed(db: Session, request: ApprovalRequest) -> None:
    """Completion hook for SUPPORT_MODEL requests (Approved -> Agreed + linked items Complete;
    Rejected -> Draft)."""
    model = (
        db.get(SupportModel, int(request.subject_id))
        if (request.subject_id or "").isdigit()
        else None
    )
    if model is None or model.approval_request_id != request.id or model.status != "In review":
        return
    before = _snap(model)
    if request.status == "Approved":
        model.status = "Agreed"
        db.flush()
        audit.record(
            db,
            actor=None,
            actor_type=ACTOR_WORKFLOW,
            entity="SupportModel",
            entity_id=model.id,
            action="agreed",
            transition_id=model.transition_id,
            before=before,
            after=_snap(model),
            note="Approval chain completed",
        )
        for item in _linked_items(db, model.transition_id):
            if item.applicability == "Not applicable" or not is_open_status(item.status):
                continue
            item_before = {"status": item.status}
            item.status = done_status_for(item.playbook_item.lens)
            item.last_updated_by = None
            item.last_updated_source = ACTOR_WORKFLOW
            audit.record(
                db,
                actor=None,
                actor_type=ACTOR_WORKFLOW,
                entity="TransitionItem",
                entity_id=item.id,
                action="updated",
                transition_id=item.transition_id,
                before=item_before,
                after={"status": item.status},
                note="Support model agreed",
            )
    elif request.status == "Rejected":
        model.status = "Draft"
        audit.record(
            db,
            actor=None,
            actor_type=ACTOR_WORKFLOW,
            entity="SupportModel",
            entity_id=model.id,
            action="returned_to_draft",
            transition_id=model.transition_id,
            before=before,
            after={**before, "status": "Draft"},
            note="Approval chain rejected",
        )
    db.flush()


def _register() -> None:
    from app.domain.approvals import register_completion_hook

    register_completion_hook(LINKED_MODULE, on_support_model_chain_completed)


_register()
