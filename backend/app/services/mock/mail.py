"""Mock Microsoft Graph mail (spec 10.2): writes an OutboxMessage instead of sending."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.orion import OutboxMessage
from app.services.mock._common import log_mock, simulate_latency


class MockMailService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def send_mail(
        self,
        from_mailbox: str,
        to: Sequence[str],
        cc: Sequence[str],
        subject: str,
        html_body: str,
        related_ids: Sequence[str] = (),
    ) -> int:
        simulate_latency()
        message = OutboxMessage(
            channel="Email",
            from_address=from_mailbox,
            to=list(to),
            cc=list(cc),
            subject=subject,
            body_html=html_body,
            related_ids=list(related_ids),
            mode="mock",
        )
        self.db.add(message)
        self.db.flush()  # the caller owns the transaction
        log_mock(
            "Mail",
            "send_mail",
            note=f"would POST https://graph.microsoft.com/v1.0/users/{from_mailbox}/sendMail",
            to=",".join(to),
            subject=subject,
        )
        return message.id
