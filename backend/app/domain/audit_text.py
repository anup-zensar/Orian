"""Human-readable one-line summary of an audit event ("Drafted Orion draft 1"), for the dashboard
and the audit API. The raw ``action`` / ``entity`` codes stay in the API unchanged."""

from __future__ import annotations

import re

_ENTITY_LABEL: dict[str, str] = {
    "TransitionItem": "checklist item",
    "OrionDraft": "Orion draft",
    "OrionProposal": "Orion proposal",
    "ApprovalRequest": "approval request",
    "ApprovalStep": "approval step",
    "ExceptionRecord": "exception",
    "GateReview": "gate review",
    "HypercareDefect": "hypercare defect",
    "OcetEstimate": "OCET estimate",
    "OcetLine": "OCET line",
    "OcetVersion": "OCET version",
    "TierAssessment": "tier assessment",
    "AIProfile": "AI profile",
    "ReminderRun": "reminder run",
    "EvalResult": "eval result",
    "LeadershipUpdate": "leadership update",
    "SupportModel": "support model",
    "AppSetting": "setting",
}
_ACTION_VERB: dict[str, str] = {
    "step_approved": "approved step of",
    "step_activated": "activated step of",
    "approval_requested": "requested approval for",
    "sent_for_review": "sent for review",
    "returned_to_draft": "returned to draft",
    "gate_advanced": "advanced the gate of",
    "pptx_generated": "generated a PowerPoint for",
    "lines_saved": "saved the lines of",
    "inputs_saved": "saved the inputs of",
    "input_requested": "requested inputs for",
    "landscape_edited": "edited the landscape of",
    "status_changed": "changed the status of",
    "fast_forward": "fast-forwarded",
}


def _words(code: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", code).replace("_", " ").strip()


def describe_event(entity: str, entity_id: str, action: str) -> str:
    """e.g. ("OrionDraft", "1", "drafted") -> "Drafted Orion draft 1"."""
    verb = _ACTION_VERB.get(action) or _words(action).lower()
    label = _ENTITY_LABEL.get(entity) or _words(entity).lower()
    text = f"{verb} {label} {entity_id}".strip()
    return text[:1].upper() + text[1:]
