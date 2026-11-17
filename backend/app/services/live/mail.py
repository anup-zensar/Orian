"""Live Microsoft Graph mail stub (spec 10.2)."""

from __future__ import annotations

from collections.abc import Sequence


class LiveMailService:
    def send_mail(
        self,
        from_mailbox: str,
        to: Sequence[str],
        cc: Sequence[str],
        subject: str,
        html_body: str,
        related_ids: Sequence[str] = (),
    ) -> int:
        """Real call: ``POST https://graph.microsoft.com/v1.0/users/{mailbox}/sendMail``.

        Uses the application permission ``Mail.Send``, restricted to the Orion shared mailbox via
        Exchange RBAC for Applications. Orion also records an OutboxMessage (mode "graph").
        """
        raise NotImplementedError("Live mail (Microsoft Graph) is a stub in the MVP")
