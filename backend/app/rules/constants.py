"""Fixed domain vocabulary (spec §4, reference.json). Pure constants – no I/O.

One gate model everywhere: SG0 → SG2 → SG3 → SG4_ATD → SG5_HYPERCARE → SG6_ATO → CLOSURE.
"""

from __future__ import annotations

GATES: tuple[str, ...] = ("SG0", "SG2", "SG3", "SG4_ATD", "SG5_HYPERCARE", "SG6_ATO", "CLOSURE")
GATE_ORDER: dict[str, int] = {code: i for i, code in enumerate(GATES)}
GATE_TYPE: dict[str, str] = {
    "SG0": "stage_review",
    "SG2": "stage_review",
    "SG3": "stage_review",
    "SG4_ATD": "decision",
    "SG5_HYPERCARE": "stage_review",
    "SG6_ATO": "decision",
    "CLOSURE": "closure",
}
GATE_SHORT: dict[str, str] = {
    "SG0": "SG0",
    "SG2": "SG0–SG2",
    "SG3": "SG3",
    "SG4_ATD": "SG4 (AtD)",
    "SG5_HYPERCARE": "Hypercare",
    "SG6_ATO": "SG6 (AtO)",
    "CLOSURE": "Closure",
}
DECISION_GATES: frozenset[str] = frozenset({"SG4_ATD", "SG6_ATO"})

GATE_OUTCOMES: dict[str, tuple[str, ...]] = {
    "stage_review": ("Proceed", "Proceed with conditions", "Hold"),
    "decision": ("Approve", "Approve with conditions", "Return"),
    "closure": ("Close", "Return"),
}

LENSES: tuple[str, ...] = ("Business", "Technical", "Compliance")

STATUSES_BY_LENS: dict[str, tuple[str, ...]] = {
    "Business": ("Not started", "In progress", "Complete", "Gap", "N/A"),
    "Technical": ("Not started", "In progress", "Complete", "Gap", "N/A"),
    "Compliance": (
        "Not started",
        "In review",
        "Compliant",
        "Compliant with conditions",
        "Non-compliant",
        "Not applicable",
    ),
}
DONE_STATUSES: frozenset[str] = frozenset({"Complete", "Compliant", "Compliant with conditions"})
NA_STATUSES: frozenset[str] = frozenset({"N/A", "Not applicable"})
GAP_STATUSES: frozenset[str] = frozenset({"Gap", "Non-compliant"})
IN_PROGRESS_STATUSES: frozenset[str] = frozenset({"In progress", "In review"})
NOT_STARTED = "Not started"
SEVERITIES: tuple[str, ...] = ("Critical", "Major", "Minor")
DESIGN_EFFECTIVENESS: tuple[str, ...] = ("–", "Yes", "No", "N/A")

# Applicability of a TransitionItem
APPLIES = "Applies"
NOT_APPLICABLE = "Not applicable"
TO_CONFIRM = "To confirm"


def done_status_for(lens: str) -> str:
    return "Compliant" if lens == "Compliance" else "Complete"


def in_progress_status_for(lens: str) -> str:
    return "In review" if lens == "Compliance" else "In progress"


def gap_status_for(lens: str) -> str:
    return "Non-compliant" if lens == "Compliance" else "Gap"


def na_status_for(lens: str) -> str:
    return "Not applicable" if lens == "Compliance" else "N/A"


def is_open_status(status: str) -> bool:
    """Open = not done and not N/A (Not started, In progress/review, Gap, Non-compliant)."""
    return status not in DONE_STATUSES and status not in NA_STATUSES


# Linked modules (BR-030, PLAN.md A-10)
OCET_LINKED_ITEMS: frozenset[str] = frozenset({"FW-008", "S45-006"})
SUPPORT_MODEL_LINKED_FW: frozenset[str] = frozenset(f"FW-{n:03d}" for n in range(27, 36))
SUPPORT_MODEL_SHEET = "Support Model"

# Actor types for AuditEvent (NFR-03)
ACTOR_HUMAN = "Human"
ACTOR_WORKFLOW = "Workflow rule"
ACTOR_ORION = "Orion agent"
ACTOR_SYSTEM = "System"
ACTOR_TYPES: tuple[str, ...] = (ACTOR_HUMAN, ACTOR_WORKFLOW, ACTOR_ORION, ACTOR_SYSTEM)
