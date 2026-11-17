"""Mock notifications (spec 10.3): in-app rows and Teams cards written to the outbox."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.orion import Notification, OutboxMessage
from app.models.reference import User
from app.services.mock._common import log_mock, simulate_latency


class MockNotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def notify(self, user_ids: Sequence[str], text: str, link: str) -> list[int]:
        rows = [Notification(user_id=uid, text=text, link=link) for uid in user_ids]
        self.db.add_all(rows)
        self.db.flush()
        log_mock("Notification", "notify", users=",".join(user_ids))
        return [row.id for row in rows]

    def post_teams_card(
        self,
        user_ids: Sequence[str],
        card_json: Mapping[str, Any],
        summary: str,
        related_ids: Sequence[str] = (),
    ) -> int:
        simulate_latency()
        users = self.db.scalars(select(User).where(User.id.in_(list(user_ids)))).all()
        emails = [u.email for u in users]
        message = OutboxMessage(
            channel="Teams",
            from_address=get_settings().orion_mailbox,
            to=emails,
            cc=[],
            subject=summary,
            body_html=summary,
            adaptive_card_json=dict(card_json),
            related_ids=list(related_ids),
            mode="mock",
        )
        self.db.add(message)
        self.db.flush()
        log_mock(
            "Notification",
            "post_teams_card",
            note="would send Teams proactive message via Azure Bot Service",
            to=",".join(emails),
        )
        return message.id
