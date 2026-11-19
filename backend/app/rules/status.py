"""Item status rules (BR-030, spec 7.5). PURE: no DB, no I/O, no permission checks.

Two kinds of problems are reported separately so the API can answer with the right status code:

* :func:`input_errors` - the input is malformed (status not allowed for the lens, unknown severity,
  unknown design effectiveness) -> HTTP 422.
* :func:`rule_violations` - the input is well formed but breaks a business rule -> HTTP 409. Every
  reason is a sentence the UI can show as is.

The rules (for the *resulting* state of the item):

* Business/Technical statuses ``Not started, In progress, Complete, Gap, N/A``; Compliance statuses
  ``Not started, In review, Compliant, Compliant with conditions, Non-compliant, Not applicable``.
* ``Gap`` / ``Non-compliant`` need a severity AND a note.
* ``N/A`` / ``Not applicable`` need a reason.
* ``Compliant`` needs design effectiveness Yes or N/A.
* ``Compliant with conditions`` needs condition data (owner, due gate, text).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.rules.constants import (
    DESIGN_EFFECTIVENESS,
    GAP_STATUSES,
    LENSES,
    NA_STATUSES,
    SEVERITIES,
    STATUSES_BY_LENS,
)

COMPLIANT = "Compliant"
COMPLIANT_WITH_CONDITIONS = "Compliant with conditions"
DE_OK_FOR_COMPLIANT: frozenset[str] = frozenset({"Yes", "N/A"})


def allowed_statuses(lens: str) -> tuple[str, ...]:
    """Statuses a lens may use (``STATUSES_BY_LENS``); empty for an unknown lens."""
    return STATUSES_BY_LENS.get(lens, ())


def is_na_status(status: str) -> bool:
    return status in NA_STATUSES


def is_gap_status(status: str) -> bool:
    return status in GAP_STATUSES


def _or_list(values: Sequence[str]) -> str:
    """'Critical, Major or Minor'."""
    return " or ".join([", ".join(values[:-1]), values[-1]]) if len(values) > 1 else "".join(values)


def input_errors(
    *,
    lens: str,
    status: str | None = None,
    gap_severity: str | None = None,
    design_effectiveness: str | None = None,
    severities: Sequence[str] = SEVERITIES,
    design_options: Sequence[str] = DESIGN_EFFECTIVENESS,
) -> list[str]:
    """Malformed input (422). ``None`` values are 'not given' and never an error. ``severities`` and
    ``design_options`` are the values on offer (the Admin's dropdown lists); the defaults are the
    standard lists."""
    reasons: list[str] = []
    if lens not in LENSES:
        reasons.append(f"Unknown lens '{lens}'")
    elif status is not None and status not in allowed_statuses(lens):
        reasons.append(
            f"Status '{status}' is not allowed for the {lens} lens "
            f"(allowed: {', '.join(allowed_statuses(lens))})"
        )
    if gap_severity is not None and gap_severity not in severities:
        reasons.append(f"Gap severity must be one of {', '.join(severities)}")
    if design_effectiveness is not None and design_effectiveness not in design_options:
        reasons.append(f"Design effectiveness must be one of {', '.join(design_options)}")
    return reasons


def rule_violations(
    *,
    lens: str,
    status: str,
    gap_severity: str | None,
    note: str | None,
    design_effectiveness: str | None,
    na_reason: str | None,
    has_condition: bool,
    check_gap: bool = True,
    check_design: bool = True,
    check_na: bool = True,
    check_condition: bool = True,
    severities: Sequence[str] = SEVERITIES,
) -> list[str]:
    """BR-030 violations (409) for the RESULTING state of an item.

    The ``check_*`` switches let the caller skip a rule the request did not touch (an owner change on
    an old row must not fail because of a legacy note). ``lens`` selects the wording only.
    """
    reasons: list[str] = []
    if check_gap and status in GAP_STATUSES:
        if not gap_severity:
            reasons.append(f"'{status}' needs a gap severity ({_or_list(severities)})")
        if not (note or "").strip():
            reasons.append(f"'{status}' needs a note explaining the gap")
    if check_na and status in NA_STATUSES and not (na_reason or "").strip():
        who = "IRM" if lens == "Compliance" else "the OR focal"
        reasons.append(f"'{status}' needs a reason (only {who} can mark an item not applicable)")
    if check_design and status == COMPLIANT and design_effectiveness not in DE_OK_FOR_COMPLIANT:
        reasons.append("'Compliant' needs design effectiveness Yes or N/A")
    if check_condition and status == COMPLIANT_WITH_CONDITIONS and not has_condition:
        reasons.append("'Compliant with conditions' needs a condition (owner, due gate and text)")
    return reasons


def missing_condition_fields(
    owner_user_id: str | None, due_gate: str | None, text: str | None
) -> list[str]:
    """Reasons for an incomplete condition block (owner, due gate, text)."""
    reasons: list[str] = []
    if not owner_user_id:
        reasons.append("The condition needs an owner")
    if not due_gate:
        reasons.append("The condition needs a due gate")
    if not (text or "").strip():
        reasons.append("The condition needs a text")
    return reasons


def clears_gap_severity(status: str) -> bool:
    """Leaving a gap status clears the severity (a severity only makes sense on a gap)."""
    return status not in GAP_STATUSES
