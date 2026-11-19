"""Request dependencies: DB session, current user, permissions (spec §3.2, §3.3, BR-001).

Demo authentication reads the ``X-Demo-User`` header (PLAN.md A-23). Only ``get_current_user`` knows
about it, so Entra ID token validation can replace it later without touching any router.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Header, Path
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db as _get_db
from app.errors import Forbidden, NotFound, Unauthorized
from app.models import User
from app.permissions import DENIAL_REASONS, Perm, has_perm

# Integer path ids are bounded so huge values give 422 instead of a SQLite overflow 500 (BE#11).
IdPath = Annotated[int, Path(ge=1, le=2**31 - 1)]
MAX_BULK = 500  # upper bound for id lists in bulk requests (BE#11)


def get_db() -> Iterator[Session]:
    yield from _get_db()


def get_current_user(
    x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
    db: Session = Depends(get_db),
) -> User:
    if not x_demo_user:
        raise Unauthorized(
            "Not signed in – pick a demo user on the login page (X-Demo-User header missing)"
        )
    user = db.get(User, x_demo_user.strip())
    if user is None:
        raise Unauthorized(f"Unknown demo user '{x_demo_user}'")
    if not user.active:
        raise Unauthorized(f"{user.name} has been deactivated - pick another demo user")
    return user


def require(perm: Perm) -> Callable[..., User]:
    """Dependency factory: ``user: User = Depends(require(Perm.UPDATE_C_STATUS))`` → 403 with reason."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if not has_perm(user.role, perm):
            raise Forbidden(DENIAL_REASONS[perm])
        return user

    _dependency.__name__ = f"require_{perm.value}"
    return _dependency


def ensure(user: User, perm: Perm) -> None:
    """Imperative permission check for domain code (raises 403 with the human reason)."""
    if not has_perm(user.role, perm):
        raise Forbidden(DENIAL_REASONS[perm])


def require_demo_mode() -> None:
    """Dependency for /admin/demo/* endpoints: 404 when DEMO_MODE=false."""
    if not get_settings().demo_mode:
        raise NotFound("Demo controls are disabled (DEMO_MODE=false)")
