"""Mock support model generator (spec 10.6.1).

``generate`` is implemented in M7 together with the Support Model module (landscape JSON, spec 8.8).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MockSupportModelGenerator:
    def generate(self, transition: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("generate is implemented in M7")
