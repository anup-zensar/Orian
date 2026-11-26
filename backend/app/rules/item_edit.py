"""Checklist edit window (CR-03 item 8). PURE: no database, no I/O.

Assessment items of ANY gate (past, current, future) stay editable while the transition is open and
Agreement to Operate (AtO) is not yet approved. Once AtO is approved the transition moves to CLOSURE
and the checklist is read-only, except items due at CLOSURE (the AI playbook ones), which stay
editable until the transition is closed.
"""

from __future__ import annotations

from app.rules.constants import GATES

CLOSED_REASON = "The transition is closed"
LOCKED_REASON = "Checklist is locked after Agreement to Operate"
_CLOSURE = GATES[-1]


def edit_lock_reason(*, transition_closed: bool, current_gate: str, item_gate: str) -> str | None:
    """None when the item may be edited, else the sentence to show (tooltip / 409)."""
    if transition_closed:
        return CLOSED_REASON
    if current_gate == _CLOSURE and item_gate != _CLOSURE:
        return LOCKED_REASON
    return None
