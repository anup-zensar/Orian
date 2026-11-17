"""Outbox of mock email / Teams messages (FR-072). M5."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import OutboxMessage, User
from app.schemas.messages import OutboxMessageOut

router = APIRouter(tags=["outbox"], dependencies=[Depends(get_current_user)])


@router.get("/outbox", response_model=list[OutboxMessageOut])
def list_outbox(
    channel: Literal["Email", "Teams"] | None = Query(default=None),
    transition_id: str | None = Query(
        default=None, description="Messages whose related_ids contain this transition id"
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OutboxMessageOut]:
    """Every message sent through the mock Mail/Notification services, newest first (FR-072).
    Readable by all roles. ``transition_id`` filters on related_ids membership.
    """
    query = select(OutboxMessage).order_by(OutboxMessage.sent_at.desc(), OutboxMessage.id.desc())
    if channel:
        query = query.where(OutboxMessage.channel == channel)
    rows = db.scalars(query).all()
    if transition_id:
        rows = [r for r in rows if transition_id in (r.related_ids or [])]
    return [
        OutboxMessageOut(
            id=r.id,
            channel=r.channel,  # type: ignore[arg-type]
            from_address=r.from_address,
            to=list(r.to or []),
            cc=list(r.cc or []),
            subject=r.subject,
            body_html=r.body_html,
            adaptive_card_json=r.adaptive_card_json,
            related_ids=list(r.related_ids or []),
            sent_at=r.sent_at,
            mode=r.mode,
            draft_id=r.draft_id,
        )
        for r in rows
    ]
