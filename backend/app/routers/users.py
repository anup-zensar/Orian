"""Users: GET /users (public – the login page lists demo users, PLAN.md A-27) and GET /me (spec §9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.permissions import Role, denied_reasons_for, permissions_for
from app.schemas.common import MeOut, UserOut

router = APIRouter(tags=["users"])

ROLE_LABELS: dict[str, str] = {
    Role.OR_FOCAL: "OR focal (S&T)",
    Role.PM: "Project manager",
    Role.ARCHITECT: "Solution architect",
    Role.OLM: "SOM OLM (Ops lead)",
    Role.PLANNER: "Planner (Finance)",
    Role.IRM: "IRM (Compliance)",
    Role.LEADERSHIP: "Leadership (read-only)",
    Role.ADMIN: "Playbook admin",
}


def to_user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.role_label = ROLE_LABELS.get(user.role, user.role)
    return out


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    return [to_user_out(u) for u in db.scalars(select(User).order_by(User.id)).all()]


@router.get("/me", response_model=MeOut)
def get_me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        user=to_user_out(user),
        permissions=permissions_for(user.role),
        denied_reasons=denied_reasons_for(user.role),
    )
