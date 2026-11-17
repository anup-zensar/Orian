"""Support model generator + PPT export (FR-040). M7."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.domain import support_model  # importing registers the SUPPORT_MODEL completion hook
from app.models import User
from app.permissions import Perm
from app.schemas.common import ErrorOut
from app.schemas.support_models import (
    ConfluenceFetchIn,
    ConfluencePageOut,
    GenerateOut,
    PptxOut,
    PutLandscapeIn,
    QuestionDraftOut,
    SupportModelListItemOut,
    SupportModelOut,
)

# Database ids fit SQLite's 64-bit INTEGER; anything bigger is a 422, never a 500.
PathId = Annotated[int, Path(ge=1, le=2**62)]

router = APIRouter(tags=["support-models"], dependencies=[Depends(get_current_user)])


async def _raw_confluence_url(request: Request) -> str | None:
    """The submitted ``confluence_url`` form value, "" included (FastAPI maps "" to None, but a
    blank value means "clear the link"). None when the field was not sent at all."""
    form = await request.form()
    value = form.get("confluence_url")
    return value if isinstance(value, str) else None


_ERR = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


@router.get(
    "/transitions/{transition_id}/support-model",
    response_model=SupportModelOut,
    responses={404: {"model": ErrorOut}},
)
def get_support_model(
    transition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SupportModelOut:
    """Latest support model of a transition (any signed-in user in scope).

    404 unknown transition / outside scope. When nothing exists yet: id null, version 0, status
    "Not started", empty inputs, landscape null (the screen shows step 1). Includes
    ``can_edit`` / ``edit_denied_reason``, ``info_note``, ``linked_items`` (FW-027..FW-035 and
    Support Model sheet items with status) and ``approval`` / ``pptx`` when present.
    """
    return support_model.get_view(db, transition_id, user)


@router.post(
    "/transitions/{transition_id}/support-model/inputs",
    response_model=SupportModelOut,
    responses={**_ERR, 422: {"model": ErrorOut}},
)
def save_inputs(
    transition_id: str,
    confluence_url: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    raw_url: str | None = Depends(_raw_confluence_url),
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_SUPPORT_MODEL)),
) -> SupportModelOut:
    """Save inputs (multipart; both parts optional). Perm EDIT_SUPPORT_MODEL (OR focal, Architect).

    403 without permission; 404 unknown transition; 409 when the latest model is In review or
    Agreed; 422 for an extension outside .mp4 .m4a .vtt .txt .docx .pdf .png .jpg or an empty
    file. Files are stored through DocumentStore (same filename replaces the old entry). A
    confluence_url is fetched (ConfluenceService) and its title/summary/diagrams kept; blank clears
    them. Creates a Draft v1 row when none exists. Audited.
    """
    result = support_model.save_inputs(
        db,
        transition_id,
        confluence_url=raw_url if raw_url is not None else confluence_url,
        files=[(f.filename or "", f.file) for f in files if f.filename],
        user=user,
    )
    db.commit()
    return result


@router.post(
    "/integrations/confluence/fetch",
    response_model=ConfluencePageOut,
    responses={422: {"model": ErrorOut}},
)
def confluence_fetch(body: ConfluenceFetchIn) -> ConfluencePageOut:
    """Confluence lookup on blur of the link field (mock, spec 10.5). Any signed-in user.

    First seed page whose ``url_contains`` matches the URL (case-insensitive), else the generic
    page. 422 for a blank or non-http(s) URL. Writes nothing.
    """
    return support_model.fetch_confluence(body.url)


@router.post(
    "/transitions/{transition_id}/support-model/generate",
    response_model=GenerateOut,
    responses={**_ERR, 422: {"model": ErrorOut}},
)
def generate_support_model(
    transition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_SUPPORT_MODEL)),
) -> GenerateOut:
    """Generate the landscape from the saved inputs (mock generator, spec 10.6.1).

    403 without permission; 404 unknown transition; 409 when no input was saved yet or the
    latest model is In review. Overwrites a Draft landscape; after Agreed it creates version + 1.
    The three ``steps`` (~1500 ms each) are only a hint for the client-side progress UI.
    Audited as "Orion agent".
    """
    result = support_model.generate(db, transition_id, user)
    db.commit()
    return result


@router.put(
    "/support-models/{support_model_id}",
    response_model=SupportModelOut,
    responses={**_ERR, 422: {"model": ErrorOut}},
)
def update_support_model(
    support_model_id: PathId,
    body: PutLandscapeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_SUPPORT_MODEL)),
) -> SupportModelOut:
    """Replace the landscape (canvas, side panels, questions, sources). Draft only.

    403 without permission; 404 unknown id; 409 when status is not Draft; 422 for duplicate
    component ids, unknown relation, or a child_of/target naming an unknown component. Audited
    with before/after.
    """
    result = support_model.update_landscape(db, support_model_id, body.landscape, user)
    db.commit()
    return result


@router.post(
    "/support-models/{support_model_id}/send-for-review",
    response_model=SupportModelOut,
    responses=_ERR,
)
def send_support_model_for_review(
    support_model_id: PathId,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_SUPPORT_MODEL)),
) -> SupportModelOut:
    """Draft -> In review; starts the SUPPORT_MODEL approval chain Architect -> OLM (BR-041).

    403 without permission; 404 unknown id; 409 unless Draft, without a landscape, or a Pending
    request already exists. Approvals are then decided via /approvals; on Approved the model is
    Agreed and the linked items (FW-027..FW-035, Support Model sheet) become Complete (Workflow
    rule); on Rejected it returns to Draft.
    """
    result = support_model.send_for_review(db, support_model_id, user)
    db.commit()
    return result


@router.post(
    "/support-models/{support_model_id}/pptx",
    response_model=PptxOut,
    responses=_ERR,
)
def generate_pptx(
    support_model_id: PathId,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_SUPPORT_MODEL)),
) -> PptxOut:
    """Build the 5-slide .pptx (python-pptx, spec 10.6.2), store it as Evidence type "Generated"
    linked to FW-035 and return the download path (/evidence/<id>/download).

    403 without permission; 404 unknown id; 409 when there is no landscape. Any status allowed;
    each call is a new version (new Evidence row). Audited.
    """
    result = support_model.build_pptx(db, support_model_id, user)
    db.commit()
    return result


@router.post(
    "/support-models/{support_model_id}/questions/{question_index}/draft",
    response_model=QuestionDraftOut,
    responses=_ERR,
)
def draft_question(
    support_model_id: PathId,
    question_index: Annotated[int, Path(ge=0, le=100_000)],
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_SUPPORT_MODEL)),
) -> QuestionDraftOut:
    """Draft question to architect for open_questions[question_index].

    Creates an Orion draft (Input request to the transition's architect, source Orion agent).
    Nothing is sent. 403 without permission; 404 unknown id or index.
    """
    draft = support_model.draft_question_to_architect(db, support_model_id, question_index, user)
    db.commit()
    return QuestionDraftOut(draft_id=draft.id)


@router.get("/support-models", response_model=list[SupportModelListItemOut])
def list_support_models(
    q: str | None = Query(default=None, description="Case-insensitive name filter"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SupportModelListItemOut]:
    """List page: latest model per transition in the user's scope, optional ``q`` substring filter
    on transition name or central app, newest first."""
    return support_model.list_models(db, user, q)
