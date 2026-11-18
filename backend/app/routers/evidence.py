"""Evidence: /transitions/{id}/evidence, /evidence/{eid}/review, /evidence/{eid}/download (FR-033). M4."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.records import EvidenceFilters, EvidenceOut, EvidenceReviewIn, EvidenceType

router = APIRouter(tags=["evidence"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(
    transition_id: str,
    filters: Annotated[EvidenceFilters, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EvidenceOut]:
    """Evidence of a transition, newest first (spec 8.7 d). 404 when the transition does not exist.
    ``item`` filters by playbook item id, ``type`` and ``status`` by exact value.
    ``can_review`` / ``review_denied_reason`` are per current user: items of the Business/Technical lens
    need ``Perm.REVIEW_EVIDENCE_BT`` (OR focal), Compliance items ``Perm.REVIEW_EVIDENCE_C`` (IRM);
    evidence without an item counts as Business/Technical; already Accepted/Rejected evidence can still be
    re-reviewed by a permitted user."""
    from app.domain import evidence

    return evidence.list_evidence(db, transition_id, filters, user)


@router.post("/transitions/{transition_id}/evidence", response_model=EvidenceOut, status_code=201)
def add_evidence(
    transition_id: str,
    title: str = Form(..., min_length=1, max_length=300),
    type: EvidenceType = Form(...),
    item_id: str | None = Form(
        default=None, max_length=50, description="Playbook item id, e.g. S45-014"
    ),
    url: str | None = Form(default=None, max_length=2000),
    text: str | None = Form(default=None, max_length=4000),
    file: UploadFile | None = File(default=None),
    user: User = Depends(require(Perm.MANAGE_EVIDENCE)),
    db: Session = Depends(get_db),
) -> EvidenceOut:
    """Upload a file, add a link or record an email sign-off (multipart form; spec 8.7 d, 10.5).

    * 403 without ``Perm.MANAGE_EVIDENCE``; 404 unknown transition or ``item_id`` not a TransitionItem of
      this transition.
    * 422: ``Document``/``Recording`` need a file (or url); ``Link`` needs ``url``; ``Email sign-off`` needs
      ``text``; ``Generated`` is system-only and is rejected here.
    * A file is saved through ``DocumentStore.save(transition_id, filename, bytes)``; ``url`` of the record
      becomes the fake SharePoint URL it returns and ``file_path`` the storage path. Links store ``url``
      as given (no file, ``has_file`` false).
    * Creates Evidence ``EVD-nnn`` (``next_id``) with status "Submitted", ``submitted_by`` = user and one
      AuditEvent (entity "Evidence", action "created", Human). Returns 201 with ``EvidenceOut``.
    """
    from app.domain import evidence

    filename: str | None = None
    content: bytes | None = None
    if file is not None and file.filename:
        filename = file.filename
        content = evidence.read_upload(file.file)
    result = evidence.add_evidence(
        db,
        transition_id,
        title=title,
        type=type,
        item_id=item_id,
        url=url,
        text=text,
        filename=filename,
        content=content,
        user=user,
    )
    db.commit()
    return result


@router.post("/evidence/{evidence_id}/review", response_model=EvidenceOut)
def review_evidence(
    evidence_id: str,
    body: EvidenceReviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceOut:
    """Accept or Reject evidence (spec 8.7 d). The required permission depends on the linked item's
    lens: OR focal (``Perm.REVIEW_EVIDENCE_BT``) for Business/Technical items and evidence without an item,
    IRM (``Perm.REVIEW_EVIDENCE_C``) for Compliance items.

    * 404 unknown evidence. 403 with the matching ``DENIAL_REASONS`` text.
    * 422 when ``decision`` is Reject and ``note`` is blank ("Rejection needs a note").
    * Sets status Accepted/Rejected, ``reviewed_by``, ``reviewed_at`` (clock.now()), ``review_note``;
      one AuditEvent (entity "Evidence", action "accepted"/"rejected", before/after status, Human).
    """
    from app.domain import evidence

    result = evidence.review_evidence(db, evidence_id, body, user)
    db.commit()
    return result


@router.get("/evidence/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the stored file via ``DocumentStore.read`` (Content-Disposition attachment with the
    original file name, correct media type guessed from the extension). 404 for unknown evidence and for
    link / email sign-off evidence without a stored file ("This evidence is a link, nothing to download").
    """
    from app.domain import evidence

    content, media_type, filename = evidence.download(db, evidence_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
