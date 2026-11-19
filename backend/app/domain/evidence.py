"""Evidence: list, add (upload / link / email sign-off), review, download (FR-033, spec 8.7 d, 10.5).

Files are stored through the ``DocumentStore`` service (mock SharePoint on local disk). The service
enforces the size and extension rules; ``read_upload`` additionally stops reading an oversized upload
early so a huge body is never held in memory. Domain functions do not commit.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import PurePosixPath
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_transition_role, transition_denial
from app.config import get_settings
from app.domain import audit, cfg
from app.domain.ids import next_id
from app.domain.records import find_item, get_transition, person, users_by_id
from app.errors import BadRequest, NotFound
from app.models import Evidence, Transition, TransitionItem, User
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN
from app.schemas.records import EvidenceFilters, EvidenceOut, EvidenceReviewIn
from app.services.factory import get_document_store

EVIDENCE_FIELDS = ("transition_item_id", "title", "type", "url", "file_path", "text", "status")
REVIEW_FIELDS = ("status", "reviewed_by", "reviewed_at", "review_note")
_CHUNK = 1024 * 1024
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


# --- helpers --------------------------------------------------------------------------------------
def read_upload(handle: BinaryIO) -> bytes:
    """Read an upload in chunks; 422 as soon as it is larger than ``MAX_UPLOAD_MB``."""
    limit_mb = get_settings().max_upload_mb
    limit = limit_mb * 1024 * 1024
    data = bytearray()
    while True:
        chunk = handle.read(_CHUNK)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > limit:
            raise BadRequest("File too large", [f"Maximum upload size is {limit_mb} MB"])
    return bytes(data)


def _review_perm(item: TransitionItem | None) -> Perm:
    """Compliance items are reviewed by IRM; everything else (also evidence without an item) by OR focal."""
    if item is not None and item.playbook_item.lens == "Compliance":
        return Perm.REVIEW_EVIDENCE_C
    return Perm.REVIEW_EVIDENCE_BT


def evidence_out(
    db: Session,
    evidence: Evidence,
    item: TransitionItem | None,
    users: dict[str, User],
    viewer: User,
    transition: Transition,
) -> EvidenceOut:
    """DTO; ``can_review`` = role permission AND assigned on this transition (BE#1)."""
    perm = _review_perm(item)
    denial = transition_denial(db, viewer, transition, perm)
    if denial is None and transition.status == "Closed":
        denial = f"{transition.id} is closed - records can no longer be added or changed"
    allowed = denial is None
    return EvidenceOut(
        id=evidence.id,
        transition_id=evidence.transition_id,
        item_id=item.playbook_item_id if item else None,
        transition_item_id=evidence.transition_item_id,
        item_title=item.playbook_item.title if item else None,
        title=evidence.title,
        type=evidence.type,
        url=evidence.url or "",
        has_file=bool(evidence.file_path),
        text=evidence.text,
        submitted_by=person(users, evidence.submitted_by),
        status=evidence.status,  # type: ignore[arg-type]
        reviewed_by=person(users, evidence.reviewed_by),
        reviewed_at=evidence.reviewed_at,
        review_note=evidence.review_note,
        created_at=evidence.created_at,
        can_review=allowed,
        review_denied_reason=denial,
    )


def _item_for(db: Session, evidence: Evidence) -> TransitionItem | None:
    if evidence.transition_item_id is None:
        return None
    return db.get(TransitionItem, evidence.transition_item_id)


def _snapshot(evidence: Evidence, fields: tuple[str, ...]) -> dict[str, object]:
    return audit.snapshot(evidence, fields)


# --- list -----------------------------------------------------------------------------------------
def list_evidence(
    db: Session, transition_id: str, filters: EvidenceFilters, viewer: User
) -> list[EvidenceOut]:
    transition = get_transition(db, transition_id)
    items = {
        i.id: i
        for i in db.scalars(
            select(TransitionItem).where(TransitionItem.transition_id == transition_id)
        ).all()
    }
    query = select(Evidence).where(Evidence.transition_id == transition_id)
    if filters.type:
        query = query.where(Evidence.type == filters.type)
    if filters.status:
        query = query.where(Evidence.status == filters.status)
    rows = db.scalars(query).all()
    if filters.item:
        wanted = {i.id for i in items.values() if i.playbook_item_id == filters.item}
        rows = [r for r in rows if r.transition_item_id in wanted]
    rows = sorted(rows, key=lambda r: (r.created_at, r.id), reverse=True)
    users = users_by_id(db)
    return [
        evidence_out(db, r, items.get(r.transition_item_id or -1), users, viewer, transition)
        for r in rows
    ]


# --- add ------------------------------------------------------------------------------------------
def _clean_url(url: str | None) -> str | None:
    if url is None or not url.strip():
        return None
    url = url.strip()
    if not _URL_RE.fullmatch(url):
        raise BadRequest("Invalid link", ["The link must start with http:// or https://"])
    return url


def add_evidence(
    db: Session,
    transition_id: str,
    *,
    title: str,
    type: str,
    item_id: str | None,
    url: str | None,
    text: str | None,
    filename: str | None,
    content: bytes | None,
    user: User,
) -> EvidenceOut:
    transition: Transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.MANAGE_EVIDENCE)
    item = find_item(db, transition, item_id) if item_id else None

    title = (title or "").strip()
    reasons: list[str] = []
    if not title:
        reasons.append("Evidence needs a title")
    # What a type needs comes from the "Evidence types" dropdown list (meta.needs):
    # file = a file or a link, url = a link, text = the e-mail text, none = system only.
    known = type in cfg.option_values(db, "evidence_types", active_only=False)
    meta = cfg.option_meta(db, "evidence_types", type)
    needs = meta.get("needs")
    label = cfg.option_label(db, "evidence_types", type)
    if not known:
        reasons.append(f"Unknown evidence type '{type}'")
    elif meta.get("system") or needs == "none":
        reasons.append(f"'{label}' evidence is created by the system only")
    elif type not in cfg.option_values(db, "evidence_types"):
        reasons.append(f"Evidence type '{label}' is no longer offered")
    has_file = content is not None and bool(filename)
    link = _clean_url(url) if needs in ("file", "url") else None
    if needs == "file" and not has_file and link is None:
        reasons.append(f"{label} evidence needs a file (or a link)")
    if needs == "url" and link is None:
        reasons.append(f"{label} evidence needs a url")
    if needs == "text" and not (text or "").strip():
        reasons.append(f"{label} evidence needs the e-mail text")
    if reasons:
        raise BadRequest("Invalid evidence", reasons)

    stored_url = link or ""
    stored_path: str | None = None
    if needs == "file" and content is not None and filename:
        saved = get_document_store().save(transition.id, filename, content)
        stored_url = saved["url"]
        stored_path = saved["path"]

    evidence = Evidence(
        id=next_id(db, Evidence.id, "EVD-"),
        transition_id=transition.id,
        transition_item_id=item.id if item else None,
        title=title,
        type=type,
        url=stored_url,
        file_path=stored_path,
        text=(text or "").strip() if needs == "text" else None,
        submitted_by=user.id,
        status="Submitted",
    )
    db.add(evidence)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Evidence",
        entity_id=evidence.id,
        action="created",
        transition_id=transition.id,
        after=_snapshot(evidence, EVIDENCE_FIELDS),
    )
    return evidence_out(db, evidence, item, users_by_id(db), user, transition)


# --- review ---------------------------------------------------------------------------------------
def review_evidence(
    db: Session, evidence_id: str, body: EvidenceReviewIn, user: User
) -> EvidenceOut:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise NotFound(f"Evidence {evidence_id} not found")
    item = _item_for(db, evidence)
    transition = get_transition(db, evidence.transition_id)
    ensure_transition_role(db, user, transition, _review_perm(item))
    if body.decision == "Reject" and not body.note.strip():
        raise BadRequest("Rejection needs a note", ["Rejection needs a note"])

    before = _snapshot(evidence, REVIEW_FIELDS)
    evidence.status = "Accepted" if body.decision == "Accept" else "Rejected"
    evidence.reviewed_by = user.id
    evidence.reviewed_at = clock.now()
    evidence.review_note = body.note.strip() or None
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Evidence",
        entity_id=evidence.id,
        action="accepted" if evidence.status == "Accepted" else "rejected",
        transition_id=evidence.transition_id,
        before=before,
        after=_snapshot(evidence, REVIEW_FIELDS),
    )
    return evidence_out(db, evidence, item, users_by_id(db), user, transition)


# --- download -------------------------------------------------------------------------------------
def safe_download_name(raw: str) -> str:
    """Header-safe file name: ASCII letters, digits, space and ``._-`` only."""
    name = PurePosixPath(raw.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9 ._-]", "_", name).strip(" .")
    return name or "evidence"


def download(db: Session, evidence_id: str) -> tuple[bytes, str, str]:
    """(content, media type, safe filename) of a stored evidence file."""
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise NotFound(f"Evidence {evidence_id} not found")
    if not evidence.file_path:
        raise NotFound("This evidence is a link, nothing to download")
    content = get_document_store().read(evidence.file_path)
    filename = safe_download_name(evidence.file_path)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return content, media_type, filename
