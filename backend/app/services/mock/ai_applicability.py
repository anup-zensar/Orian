"""Mock AIService.recommend_applicability (M3, FR-022). Deterministic: same input -> same output.

For each "To confirm" golden-set / common row it recommends Yes or No with a one-line reason:

* ``ALL-02`` (customer journey) is Yes when the audience is External or Enterprise, else No.
* Every other row is Yes when its title shares at least one keyword with the transition name,
  description or the portfolio focus areas, else No.

Advisory only: the OR focal decides (BR-050), nothing here is persisted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.services.mock._common import log_mock, simulate_latency

_STOPWORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "plan",
        "model",
        "process",
        "procedure",
        "matrix",
        "evidence",
        "support",
        "service",
        "level",
        "global",
        "central",
        "if",
        "applicable",
    }
)
_JOURNEY_ITEM = "ALL-02"
_BROAD_AUDIENCES = ("External", "Enterprise")


def _stem(word: str) -> str:
    for suffix in ("ing", "ies", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def _keywords(text: str) -> dict[str, str]:
    """stem -> original word for the meaningful words of ``text``."""
    result: dict[str, str] = {}
    for word in re.findall(r"[a-z][a-z0-9]+", (text or "").lower()):
        if len(word) < 4 or word in _STOPWORDS:
            continue
        result.setdefault(_stem(word), word)
    return result


def recommend_applicability(
    items: Sequence[Mapping[str, Any]], flavour: Mapping[str, Any]
) -> list[dict[str, Any]]:
    simulate_latency()
    log_mock(
        "AI",
        "recommend_applicability",
        items=len(items),
        portfolio=flavour.get("portfolio"),
        project_type=flavour.get("project_type"),
    )
    context = " ".join(
        [str(flavour.get("name") or ""), str(flavour.get("description") or "")]
        + [str(a) for a in flavour.get("focus_areas") or []]
    )
    context_words = _keywords(context)
    audience = flavour.get("audience")

    results: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("id"))
        title = str(item.get("title") or "")
        if item_id == _JOURNEY_ITEM:
            if audience in _BROAD_AUDIENCES:
                rec, reason = "Yes", f"{audience} audience - a customer journey is relevant"
            elif audience:
                rec, reason = "No", f"{audience} audience - no customer journey to document"
            else:
                rec, reason = "No", "Audience not captured - no customer-facing journey indicated"
        else:
            shared = [w for stem, w in _keywords(title).items() if stem in context_words]
            if shared:
                rec = "Yes"
                reason = f"Matches '{shared[0]}' in the solution scope and portfolio focus areas"
            else:
                rec = "No"
                reason = (
                    "No link between this requirement and the solution scope or portfolio focus"
                )
        results.append({"item_id": item_id, "recommendation": rec, "reason": reason})
    return results
