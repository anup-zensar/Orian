"""Leadership updates: list, read, send (FR-080). Generation is POST /orion/leadership-update."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import IdPath, get_current_user, get_db, require
from app.domain import leadership as domain
from app.models import User
from app.permissions import Perm
from app.schemas.leadership import LeadershipSendIn, LeadershipUpdateOut

router = APIRouter(tags=["leadership"], dependencies=[Depends(get_current_user)])


@router.get("/leadership-updates", response_model=list[LeadershipUpdateOut])
def list_leadership_updates(db: Session = Depends(get_db)) -> list[LeadershipUpdateOut]:
    """All stored updates, newest first (created_at desc, id desc). Any signed-in user."""
    return domain.list_updates(db)


@router.get("/leadership-updates/{update_id}", response_model=LeadershipUpdateOut)
def get_leadership_update(update_id: IdPath, db: Session = Depends(get_db)) -> LeadershipUpdateOut:
    """One update. 404 when unknown."""
    return domain.get_update(db, update_id)


@router.post("/leadership-updates/{update_id}/send", response_model=LeadershipUpdateOut)
def send_leadership_update(
    update_id: IdPath,
    body: LeadershipSendIn,
    user: User = Depends(require(Perm.GENERATE_LEADERSHIP_UPDATE)),
    db: Session = Depends(get_db),
) -> LeadershipUpdateOut:
    """Send via the mock MailService from ORION_MAILBOX to ``body.to``; sets sent_at/sent_to; audited
    as Human; commits. 403 without Perm.GENERATE_LEADERSHIP_UPDATE; 404 unknown update; 400 on an
    invalid address; 422 on an empty list."""
    row = domain.send_update(db, update_id, user, body.to)
    db.commit()
    return domain.leadership_out(db, row)
