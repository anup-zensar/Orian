"""Leadership updates (FR-080). Orion drafts the text from live data; a permitted human sends it.
NFR-04: generating or storing an update writes no statuses/decisions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import LeadershipUpdate, User
from app.schemas.leadership import LeadershipScope, LeadershipUpdateOut


def collect_scope_data(db: Session, scope: LeadershipScope, scope_id: str | None) -> dict[str, Any]:
    """Live data for ``AIService.leadership_update``: keys ``scope``, ``scope_id``, ``title``, ``today``,
    ``transitions`` (id, name, portfolio, current gate, RAG, readiness %, days to decision, verdict),
    ``portfolios`` (per portfolio counts by RAG/gate), ``risks`` (top open risks/blockers incl.
    critical gaps), ``decisions_next_30_days`` (gate decisions due within 30 days of today,
    clock-aware), ``approvals`` (recent AtD/AtO approvals with date and approver - storyline step 10:
    the GCC portfolio update must show the AtD approval and the remaining risks), ``asks`` (open
    conditions, pending exceptions, overdue items), ``wins`` (approvals, closed gaps). NotFound 404
    for an unknown transition id / portfolio name; BadRequest 400 when scope=all with a scope_id, or
    scope!=all without one."""
    raise NotImplementedError("M8")


def generate_update(
    db: Session, user: User, scope: LeadershipScope, scope_id: str | None
) -> LeadershipUpdate:
    """Collect data, call ``get_ai_service().leadership_update``, store a ``LeadershipUpdate`` row
    (generated_by=user.id), audit actor_type "Human" (the requesting user) note "Generated leadership
    update", flush. Caller must hold Perm.GENERATE_LEADERSHIP_UPDATE."""
    raise NotImplementedError("M8")


def send_update(db: Session, update_id: int, user: User, to: list[str]) -> LeadershipUpdate:
    """Validate addresses (``domain.drafts.validate_addresses``; BadRequest 400 on invalid), send an
    HTML email via the mock MailService from ``ORION_MAILBOX`` (subject = update title, body =
    markdown rendered to sanitised HTML via ``domain.html_sanitize``), add an outbox row, set
    ``sent_at`` (clock-aware), record recipients, audit actor_type "Human" note "Sent leadership
    update to <n> recipients". NotFound 404 for unknown id. Re-sending is allowed."""
    raise NotImplementedError("M8")


def leadership_out(db: Session, row: LeadershipUpdate) -> LeadershipUpdateOut:
    """Map a row: title (first markdown heading), generated_by PersonRef, generated_source
    "Orion agent", sent_to from the latest outbox row / audit payload of this update."""
    raise NotImplementedError("M8")


def list_updates(db: Session) -> list[LeadershipUpdateOut]:
    """Newest first (created_at desc, id desc)."""
    raise NotImplementedError("M8")


def get_update(db: Session, update_id: int) -> LeadershipUpdateOut:
    """404 when unknown."""
    raise NotImplementedError("M8")
