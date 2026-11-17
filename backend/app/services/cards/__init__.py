"""Adaptive Card templates (spec §10.4) and a minimal renderer.

The JSON files use the standard Adaptive Cards Templating syntax – ``${path}`` expressions and ``$data``
array repetition – so Phase 2 can post them unchanged with the official templating SDK and the Teams bot.
This renderer implements only the subset the templates use:

* a string that is exactly one expression, e.g. ``"${step}"``, keeps the value's type (``1``);
* text with expressions, e.g. ``"Step ${step} of ${step_count}"``, is interpolated (missing -> ``""``);
* a list element ``{"$data": "${items}", ...}`` is repeated once per element of ``items``; inside it,
  expressions resolve against the element first, then against the outer data.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

CARDS_DIR = Path(__file__).resolve().parent
TEMPLATE_NAMES = ("approval_request", "reminder_digest", "ocet_approval")

_FULL = re.compile(r"^\$\{([A-Za-z0-9_.]+)\}$")
_PART = re.compile(r"\$\{([A-Za-z0-9_.]+)\}")


@lru_cache
def _load(name: str) -> str:
    if name not in TEMPLATE_NAMES:
        raise ValueError(f"Unknown card template {name!r}")
    return (CARDS_DIR / f"{name}.json").read_text(encoding="utf-8")


def _resolve(path: str, scopes: tuple[Mapping[str, Any], ...]) -> Any:
    """Look ``a.b.c`` up in the innermost scope first, then outer scopes."""
    for scope in scopes:
        value: Any = scope
        found = True
        for part in path.split("."):
            if isinstance(value, Mapping) and part in value:
                value = value[part]
            else:
                found = False
                break
        if found:
            return value
    return None


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _expand(node: Any, scopes: tuple[Mapping[str, Any], ...]) -> Any:
    if isinstance(node, str):
        full = _FULL.match(node)
        if full:
            return _resolve(full.group(1), scopes)
        return _PART.sub(lambda m: _text(_resolve(m.group(1), scopes)), node)
    if isinstance(node, list):
        out: list[Any] = []
        for element in node:
            if isinstance(element, Mapping) and "$data" in element:
                data = _expand(element["$data"], scopes)
                body = {k: v for k, v in element.items() if k != "$data"}
                for item in data or []:
                    inner = item if isinstance(item, Mapping) else {"value": item}
                    out.append(_expand(body, (inner, *scopes)))
            else:
                out.append(_expand(element, scopes))
        return out
    if isinstance(node, Mapping):
        return {key: _expand(value, scopes) for key, value in node.items()}
    return node


def render_card(name: str, data: Mapping[str, Any]) -> dict[str, Any]:
    """Return template ``name`` filled with ``data`` (Adaptive Card JSON, ready to store or post)."""
    template = json.loads(_load(name))
    return _expand(template, (data,))
