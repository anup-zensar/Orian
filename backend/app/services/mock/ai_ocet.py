"""Mock Orion text for OCET version changes (spec 8.10 Orion card). Implemented in M6.

The integration lead wires ``MockAIService.explain_ocet_change`` to this function.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _money(amount: float, currency: str) -> str:
    from app.rules.ocet import format_total_label

    return f"{format_total_label(amount)} {currency}".strip()


def _override_phrase(line: Mapping[str, Any]) -> str | None:
    overrides = line.get("year_overrides") or {}
    if not overrides:
        return None
    parts = []
    for year in sorted(overrides, key=lambda y: int(y)):
        value = float(overrides[year])
        parts.append(f"{year} growth overridden to {value:+g}%")
    text = ", ".join(parts)
    reason = (line.get("override_reason") or "").strip()
    return f"{text} ({reason})" if reason else text


def explain_ocet_change(diff: Mapping[str, Any]) -> str:
    """Plain-English explanation of an OCET version change, deterministic (no randomness).

    ``diff`` keys (built by app.domain.ocet): ``version`` (int), ``previous_version`` (int | None),
    ``currency``, ``total`` (float), ``total_abs`` (float), ``total_pct`` (float | None),
    ``by_category`` [{category, abs_change, pct_change}], ``by_line`` [{line_key, category,
    description, abs_change, status, growth_pct, year_overrides, override_reason}],
    ``inputs_pending`` (bool), ``missing_lines`` [description].

    Example: "Total up 8.4% vs v1, mainly AI tokens: 2028 growth overridden to +30% because two
    more markets onboard". No previous version -> "First estimate: <total> over 5 years, mostly
    <largest category>". Inputs pending -> append "N input(s) still missing: <descriptions>".
    Never states a decision or approval (BR-050).
    """
    from app.services.mock._common import log_mock, simulate_latency

    log_mock("AI", "explain_ocet_change", version=diff.get("version"))
    simulate_latency()

    currency = str(diff.get("currency") or "")
    previous = diff.get("previous_version")
    by_category = list(diff.get("by_category") or [])
    by_line = list(diff.get("by_line") or [])
    total = float(diff.get("total") or 0.0)

    if previous is None:
        ranked = sorted(by_category, key=lambda c: -float(c.get("current_total", 0.0)))
        text = f"First estimate: {_money(total, currency)} over the horizon"
        if ranked and total > 0:
            text += f", mostly {ranked[0]['category']}"
        text += "."
    else:
        pct = diff.get("total_pct")
        abs_change = float(diff.get("total_abs") or 0.0)
        if abs(abs_change) < 0.005:
            text = f"Total unchanged vs v{previous}."
        else:
            direction = "up" if abs_change > 0 else "down"
            amount = f"{abs(pct):.1f}%" if pct is not None else _money(abs(abs_change), currency)
            text = f"Total {direction} {amount} vs v{previous}"
            sign = 1 if abs_change > 0 else -1
            drivers = sorted(
                (c for c in by_category if float(c.get("abs_change", 0.0)) * sign > 0),
                key=lambda c: -abs(float(c.get("abs_change", 0.0))),
            )
            if drivers:
                text += f", mainly {drivers[0]['category']}"
                top = next(
                    (
                        ln
                        for ln in sorted(
                            by_line, key=lambda ln: -abs(float(ln.get("abs_change", 0.0)))
                        )
                        if ln.get("category") == drivers[0]["category"]
                    ),
                    None,
                )
                phrase = _override_phrase(top) if top else None
                if phrase:
                    text += f": {phrase}"
                elif top and top.get("status") == "added":
                    text += f": new line {top.get('description') or top.get('line_key')}"
            text += "."
    missing = list(diff.get("missing_lines") or [])
    if missing:
        text += f" {len(missing)} input(s) still missing: {', '.join(missing)}."
    return text
