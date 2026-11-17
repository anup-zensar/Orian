"""Live notification stub (spec 10.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class LiveNotificationService:
    def notify(self, user_ids: Sequence[str], text: str, link: str) -> list[int]:
        """In-app notifications stay in the Orion database; no external call is needed."""
        raise NotImplementedError("Live notifications are a stub in the MVP")

    def post_teams_card(
        self,
        user_ids: Sequence[str],
        card_json: Mapping[str, Any],
        summary: str,
        related_ids: Sequence[str] = (),
    ) -> int:
        """Real call: Teams bot proactive message (Adaptive Card) via Azure Bot Service (Phase 2)."""
        raise NotImplementedError("Live Teams messaging is Phase 2")
