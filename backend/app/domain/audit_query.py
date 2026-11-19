"""Audit trail query (FR-110, spec 8.17, NFR-03): filters, newest first, paging, resolved names."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.audit_text import describe_event
from app.errors import BadRequest
from app.models import AuditEvent, Transition, User
from app.schemas.audit import AuditEventOut, AuditFilters, AuditPageOut


def query_audit(db: Session, filters: AuditFilters) -> AuditPageOut:
    if filters.from_date and filters.to_date and filters.from_date > filters.to_date:
        raise BadRequest("Invalid date range", ["'from' must not be after 'to'"])

    conditions = []
    if filters.transition_id:
        conditions.append(AuditEvent.transition_id == filters.transition_id)
    if filters.actor:
        conditions.append(AuditEvent.actor_user_id == filters.actor)
    if filters.actor_type:
        conditions.append(AuditEvent.actor_type == filters.actor_type)
    if filters.entity:
        conditions.append(AuditEvent.entity == filters.entity)
    if filters.from_date:
        conditions.append(AuditEvent.at >= datetime.combine(filters.from_date, time.min))
    if filters.to_date:
        conditions.append(
            AuditEvent.at < datetime.combine(filters.to_date + timedelta(days=1), time.min)
        )

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    rows = db.scalars(
        select(AuditEvent)
        .where(*conditions)
        .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    ).all()

    user_ids = {r.actor_user_id for r in rows if r.actor_user_id}
    transition_ids = {r.transition_id for r in rows if r.transition_id}
    users = (
        {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )
    transitions = (
        {
            t.id: t.name
            for t in db.scalars(select(Transition).where(Transition.id.in_(transition_ids))).all()
        }
        if transition_ids
        else {}
    )
    return AuditPageOut(
        items=[
            AuditEventOut(
                id=r.id,
                at=r.at,
                actor_user_id=r.actor_user_id,
                actor_name=users.get(r.actor_user_id) if r.actor_user_id else None,
                actor_type=r.actor_type,
                transition_id=r.transition_id,
                transition_name=transitions.get(r.transition_id) if r.transition_id else None,
                entity=r.entity,
                entity_id=r.entity_id,
                action=r.action,
                before=r.before,
                after=r.after,
                note=r.note or "",
                summary=describe_event(r.entity, r.entity_id, r.action),
            )
            for r in rows
        ],
        total=total,
    )
