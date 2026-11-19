"""Users: GET /users (public – the login page lists demo users, PLAN.md A-27) and GET /me (spec §9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain import cfg
from app.models import User
from app.permissions import denied_reasons_for, permissions_for
from app.schemas.common import MeOut, UserOut

router = APIRouter(tags=["users"])


def to_user_out(db: Session, user: User) -> UserOut:
    """The user with the role label an Admin may have renamed (``cfg.role_label``)."""
    out = UserOut.model_validate(user)
    out.role_label = cfg.role_label(db, user.role)
    return out


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    """The login list: active people only (an Admin deactivates, never deletes)."""
    rows = db.scalars(select(User).where(User.active.is_(True)).order_by(User.id)).all()
    return [to_user_out(db, u) for u in rows]


@router.get("/me", response_model=MeOut)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    return MeOut(
        user=to_user_out(db, user),
        permissions=permissions_for(user.role),
        denied_reasons=denied_reasons_for(user.role),
    )
