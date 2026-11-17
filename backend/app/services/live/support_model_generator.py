"""Live support model generator stub (spec 10.6.1)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class LiveSupportModelGenerator:
    def generate(self, transition: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Real call: Azure OpenAI multimodal (Azure AI Foundry) over the diagrams, files and
        texts, returning the landscape JSON. Facts stay rule-computed; on error fall back to
        the mock generator."""
        raise NotImplementedError("Live support model generation is a stub in the MVP")
