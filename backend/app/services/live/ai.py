"""Live AI stubs (spec 10.1) - not enabled in the MVP (PLAN.md section 3, SHOULD item)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.interfaces import DraftText


class LiveAIService:
    """Azure OpenAI backed Orion agent (stub)."""

    def readiness_narrative(self, ctx: Mapping[str, Any]) -> str:
        """Narrative from computed facts.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def recommend_actions(self, gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Action proposals per gap.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def recommend_applicability(
        self, items: Sequence[Mapping[str, Any]], flavour: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Applicability recommendations.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def draft_message(self, kind: str, ctx: Mapping[str, Any]) -> DraftText:
        """Draft a message.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def leadership_update(self, scope_data: Mapping[str, Any]) -> str:
        """Leadership update text.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def explain_ocet_change(self, diff: Mapping[str, Any]) -> str:
        """OCET change explanation.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def chat(self, message: str, context: Mapping[str, Any]) -> dict[str, Any]:
        """Free-text chat.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def insights(self, scope_data: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Insight bullets.

        Real call: Azure OpenAI (Azure AI Foundry) chat completion with rule-computed facts
        as context; falls back to the mock on error.
        """
        raise NotImplementedError("Live AI is not enabled in the MVP")
