"""Audit trail writer (NFR-03, BR-050).

Every write in the system calls ``record`` with the actor type:
``Human`` (a person clicked), ``Workflow rule`` (deterministic rule, e.g. OCET approval completes
linked items), ``Orion agent`` (AI drafted/proposed something – never a decision), ``System``
(seeding, startup).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app import clock
from app.models import AuditEvent, User
from app.rules.constants import ACTOR_TYPES


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return value


def record(
    db: Session,
    *,
    actor: User | str | None,
    actor_type: str,
    entity: str,
    entity_id: str | int,
    action: str,
    transition_id: str | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    note: str = "",
) -> AuditEvent:
    """Add an AuditEvent to the session (the caller commits)."""
    if actor_type not in ACTOR_TYPES:
        raise ValueError(f"Unknown actor_type {actor_type!r}")
    actor_id = actor.id if isinstance(actor, User) else actor
    at = clock.now()
    if actor_type == "System" and action == "seeded":
        # The demo clock keeps the demo date but uses the real time of day, so a later action on the
        # same demo date could carry an earlier time than the seed. Seed events sit at the start of
        # their day, so the newest activity always sorts first.
        at = datetime.combine(clock.today(), time.min)
    event = AuditEvent(
        at=at,
        actor_user_id=actor_id,
        actor_type=actor_type,
        transition_id=transition_id,
        entity=entity,
        entity_id=str(entity_id),
        action=action,
        before=_jsonable(dict(before)) if before is not None else None,
        after=_jsonable(dict(after)) if after is not None else None,
        note=note,
    )
    db.add(event)
    return event


def snapshot(obj: Any, fields: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Pick ``fields`` from an ORM object for before/after diffs."""
    return {f: _jsonable(getattr(obj, f, None)) for f in fields}
