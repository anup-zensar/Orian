"""Notification fan-out: in-app + mock email + mock Teams card (spec §10.2, §10.3). M5."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain import cfg
from app.domain.html_sanitize import sanitize_html
from app.models import User
from app.services.factory import get_mail_service, get_notification_service


def message_templates(db: Session) -> dict[str, cfg.TemplateCfg]:
    """The message templates (Admin > Messages) by key, for ``AIService.draft_message``
    (``ctx["templates"]``). A key without a saved row gets the code default."""
    found = {key: cfg.template(db, key) for key in cfg.template_keys()}
    return {key: tpl for key, tpl in found.items() if tpl is not None}


def deliver(
    db: Session,
    *,
    user_ids: list[str],
    text: str,
    link: str,
    email_subject: str | None = None,
    email_html: str | None = None,
    teams_card: dict[str, Any] | None = None,
    related_ids: Sequence[str] = (),
) -> None:
    """Create an in-app Notification per user (NotificationService.notify). If ``email_subject``
    and ``email_html`` are given, send one mock email per user via MailService (from the Orion
    mailbox, writes OutboxMessage Email). If ``teams_card`` is given, post it via
    NotificationService.post_teams_card (OutboxMessage Teams). Unknown user ids and duplicates are
    skipped. No-op for an empty ``user_ids``. Does not commit.
    """
    unique = list(dict.fromkeys(uid for uid in user_ids if uid))
    if not unique:
        return
    db.flush()
    found = {u.id: u for u in db.scalars(select(User).where(User.id.in_(unique))).all()}
    users = [found[uid] for uid in unique if uid in found]
    if not users:
        return
    ids = [u.id for u in users]

    get_notification_service(db).notify(ids, text, link)

    if email_subject is not None and email_html is not None:
        mail = get_mail_service(db)
        body = sanitize_html(email_html)
        mailbox = get_settings().orion_mailbox
        for user in users:
            mail.send_mail(mailbox, [user.email], [], email_subject, body, list(related_ids))

    if teams_card is not None:
        get_notification_service(db).post_teams_card(
            ids, teams_card, email_subject or text, list(related_ids)
        )
