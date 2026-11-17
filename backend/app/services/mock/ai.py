"""Mock AI service (spec 10.1).

Every method exists so the class satisfies ``AIService``; each is implemented together with its
caller in a later milestone (PLAN.md):

* ``insights``                 - M2
* ``recommend_applicability``  - M3
* ``readiness_narrative``, ``recommend_actions``, ``draft_message`` - M5
* ``explain_ocet_change``      - M6
* ``chat``, ``leadership_update`` - M8
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.interfaces import DraftText


class MockAIService:
    def readiness_narrative(self, ctx: Mapping[str, Any]) -> str:
        raise NotImplementedError("readiness_narrative is implemented in M5")

    def recommend_actions(self, gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError("recommend_actions is implemented in M5")

    def recommend_applicability(
        self, items: Sequence[Mapping[str, Any]], flavour: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("recommend_applicability is implemented in M3")

    def draft_message(self, kind: str, ctx: Mapping[str, Any]) -> DraftText:
        raise NotImplementedError("draft_message is implemented in M5")

    def leadership_update(self, scope_data: Mapping[str, Any]) -> str:
        raise NotImplementedError("leadership_update is implemented in M8")

    def explain_ocet_change(self, diff: Mapping[str, Any]) -> str:
        raise NotImplementedError("explain_ocet_change is implemented in M6")

    def chat(self, message: str, context: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("chat is implemented in M8")

    def insights(self, scope_data: Mapping[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError("insights is implemented in M2")
