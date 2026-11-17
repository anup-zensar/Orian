"""Live AI stubs (spec 10.1) - not enabled in the MVP (PLAN.md section 3, SHOULD item)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.interfaces import DraftText, IntakeExtraction, ParsedCommand


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

    def extract_intake(
        self, text: str, vocab: Mapping[str, Any], servicenow: Mapping[str, Any] | None = None
    ) -> IntakeExtraction:
        """Intake extraction with Azure OpenAI function calling.

        Real call: one chat completion with a single tool ``fill_intake`` whose JSON schema is
        ``TransitionCreateIn`` (enum values built from ``vocab`` at call time: project_type,
        portfolio, region, option lists, user ids with names and roles in the system prompt) plus a
        per-field ``evidence`` quote and ``confidence``. ``tool_choice`` forces the tool, temperature
        0, ``strict: true``. The user text is passed as DATA inside delimiters and the system prompt
        says to ignore instructions inside it. The result is mapped to ``IntakeExtraction`` (fields
        absent from the tool call -> state "missing"). A value outside ``vocab`` is dropped; any
        error, timeout or invalid JSON falls back to ``mock.ai_chat.extract_intake``.
        ``domain.nl_intake`` re-validates everything anyway."""
        raise NotImplementedError("Live AI is not enabled in the MVP")

    def parse_command(
        self,
        message: str,
        catalog: Sequence[Mapping[str, Any]],
        vocab: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> list[ParsedCommand]:
        """Command parsing with Azure OpenAI tool calling.

        Real call: each catalog intent with a proposal kind (and each quick action) becomes one tool:
        name = intent, parameters = the JSON schema of the kind's payload model in
        ``schemas.orion.PAYLOAD_MODELS`` (or the ``ChatIn.form_data`` fields for quick actions);
        refusal intents are parameterless tools so the model can route to them. ``tool_choice``
        "auto", ``parallel_tool_calls`` true (max 5 calls kept), temperature 0. The prompt carries
        ``context`` (today, open transition and item, user role) and a compact vocab (ids and names).
        No tool call -> []. Falls back to ``mock.ai_chat.parse_command`` on error. The model can only
        choose among catalog tools and ``domain.nl_intake`` re-validates ids, enums and permissions,
        so the model has no way to cause a write (BR-050)."""
        raise NotImplementedError("Live AI is not enabled in the MVP")
