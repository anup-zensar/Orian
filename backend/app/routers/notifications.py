"""In-app notifications (bell). M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.errors import NotFound
from app.models import Notification, User
from app.schemas.common import OkOut
from app.schemas.messages import NotificationOut, NotificationsOut

router = APIRouter(tags=["notifications"], dependencies=[Depends(get_current_user)])


@router.get("/notifications", response_model=NotificationsOut)
def list_notifications(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NotificationsOut:
    """The current user's notifications, newest first (max 50), with the unread count."""
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(50)
    ).all()
    unread = (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read.is_(False))
        )
        or 0
    )
    return NotificationsOut(
        unread=unread,
        items=[
            NotificationOut(id=n.id, text=n.text, link=n.link, read=n.read, created_at=n.created_at)
            for n in rows
        ],
    )


@router.post("/notifications/read-all", response_model=OkOut)
def read_all_notifications(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OkOut:
    """Mark all of the current user's notifications read. Commits."""
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read.is_(False))
        .values(read=True)
    )
    db.commit()
    return OkOut()


@router.post("/notifications/{notification_id}/read", response_model=OkOut)
def read_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkOut:
    """Mark one notification read. 404 if unknown or owned by another user. Commits."""
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise NotFound(f"Notification {notification_id} not found")
    row.read = True
    db.commit()
    return OkOut()
