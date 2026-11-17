"""Mock support model generator (spec 10.6.1).

Deterministic: a transition whose name contains VOC / Medallia, or whose Confluence URL contains
``voc`` / ``medallia`` (case-insensitive), gets the VOC sample from ``seed/support_model_samples.json``;
every other transition gets a generic landscape built from the portfolio focus areas plus the typical
integrations. Component ids are ``c1..cn``. No randomness, no network.

``transition`` keys used: ``name``, ``portfolio``, ``focus_areas`` (list[str]). ``inputs`` keys used:
``confluence_url``, ``confluence`` ({title, summary, diagrams}), ``files`` ([{filename, kind}]) and
``texts`` ({filename: extracted text}).
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any

from app.config import get_settings
from app.services.mock._common import log_mock, simulate_latency

MAX_COMPONENTS = 8
MIN_COMPONENTS = 6
_FOCUS_TYPES = ("Team", "Process", "Integration")


def _load_samples() -> list[dict[str, Any]]:
    path = get_settings().seed_dir / "support_model_samples.json"
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return list(data.get("samples", []))


def _word_in(needle: str, haystack_lower: str) -> bool:
    """Whole-word, case-insensitive match ("voc" matches "Medallia VOC" but not "Advocacy")."""
    needle = needle.strip().lower()
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack_lower) is not None


def _matches(sample: Mapping[str, Any], name: str, url: str) -> bool:
    match = sample.get("match", {})
    name_l, url_l = name.lower(), url.lower()
    if any(_word_in(str(m), name_l) for m in match.get("transition_name_contains", [])):
        return True
    return any(_word_in(str(m), url_l) for m in match.get("confluence_url_contains", []))


def _short(text: str, limit: int = 60) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _focus_component(area: str, index: int) -> dict[str, Any]:
    return {
        "name": _short(area, 48),
        "type": _FOCUS_TYPES[index % len(_FOCUS_TYPES)],
        "relation": "bidirectional",
        "target": None,
    }


def _upload_sources(inputs: Mapping[str, Any]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for entry in inputs.get("files", []) or []:
        filename = str(entry.get("filename", ""))
        kind = entry.get("kind")
        if kind == "recording":
            sources.append({"type": "recording", "ref": f"{filename} @ 00:00:00"})
        elif kind == "diagram":
            sources.append({"type": "diagram", "ref": filename})
        else:  # transcript, design, other
            sources.append({"type": "document", "ref": filename})
    confluence = inputs.get("confluence") or {}
    if confluence.get("title"):
        sources.append({"type": "document", "ref": f"Confluence: {confluence['title']}"})
    for diagram in confluence.get("diagrams", []) or []:
        sources.append({"type": "diagram", "ref": str(diagram)})
    return sources


def _generic(transition: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    name = str(transition.get("name") or "Application")
    portfolio = str(transition.get("portfolio") or "")
    focus = [str(f) for f in (transition.get("focus_areas") or []) if str(f).strip()]
    text_blob = " ".join(str(v) for v in (inputs.get("texts") or {}).values()).lower()

    components: list[dict[str, Any]] = [
        {"name": "Entra ID SSO", "type": "Identity", "relation": "outbound", "target": None},
        {"name": "ServiceNow", "type": "Integration", "relation": "bidirectional", "target": None},
        {"name": "Monitoring tool", "type": "Integration", "relation": "outbound", "target": None},
        {"name": "Data platform", "type": "Data platform", "relation": "outbound", "target": None},
        {"name": "Middleware", "type": "Middleware", "relation": "bidirectional", "target": None},
    ]
    for i, area in enumerate(focus[:2]):
        components.append(_focus_component(area, i))
    if "sftp" in text_blob and len(components) < MAX_COMPONENTS:
        components.append(
            {"name": "SFTP file transfer", "type": "File transfer", "relation": "outbound"}
        )
    if len(components) < MIN_COMPONENTS:
        components.append(
            {"name": "L1 Service Desk", "type": "Team", "relation": "inbound", "target": None}
        )
    components = components[:MAX_COMPONENTS]

    return {
        "central_app": name,
        "hosting": "Shell Azure tenant (to be confirmed)",
        "vendor": "Product vendor",
        "supplier": "AMS supplier",
        "vendor_responsibilities": ["Hosting", "Development", "Configuration", "Technical access"],
        "components": components,
        "support_tiers": {
            "L1": "L1 Service Desk",
            "L2": "L2 vendor or AMS",
            "L3": "L3 product team",
        },
        "contacts": [
            {
                "party": "L1 Service Desk",
                "role": "First line support",
                "email": "to be provided",
                "sla": "to be provided",
            },
            {
                "party": "AMS supplier",
                "role": "L2 application support",
                "email": "to be provided",
                "sla": "to be provided",
            },
            {
                "party": f"{name} product team",
                "role": "L3 engineering",
                "email": "to be provided",
                "sla": "to be provided",
            },
        ],
        "open_questions": [
            f"Confirm the L2/L3 split between the vendor and the product team for {name}",
            "Who owns monitoring alerts and the on-call rota outside office hours?",
            "Confirm hosting and data platform dependencies"
            + (f" for the {portfolio} portfolio" if portfolio else ""),
        ],
        "sources": [],
    }


def _number(landscape: dict[str, Any]) -> dict[str, Any]:
    for i, component in enumerate(landscape.get("components", []), start=1):
        component["id"] = f"c{i}"
        component.setdefault("target", None)
    return landscape


class MockSupportModelGenerator:
    def generate(self, transition: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
        simulate_latency()
        name = str(transition.get("name") or "")
        url = str(inputs.get("confluence_url") or "")
        sample = next((s for s in _load_samples() if _matches(s, name, url)), None)
        if sample is not None:
            landscape = copy.deepcopy(sample["landscape"])
            kind = f"sample:{sample.get('key', '')}"
        else:
            landscape = _generic(transition, inputs)
            kind = "generic"
        landscape["sources"] = [*landscape.get("sources", []), *_upload_sources(inputs)]
        log_mock("SupportModelGenerator", "generate", transition=name, kind=kind)
        return _number(landscape)
