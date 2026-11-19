"""Code defaults of the runtime configuration (CR-01 design 6 "with code defaults").

``app.domain.cfg`` falls back to these values when a configuration row is missing (an empty or
partly seeded database, a section never saved). Where the defaults live:

* scalar settings documents (thresholds, labels ...) and message templates: HERE (code);
* registries (project types, checklists, option lists, intake fields, roles, tier rules, gates,
  lenses ...): ``seed/config.json`` - the single source also used by the seed loader and by the
  admin "Reset section to defaults";
* the permission matrix and denial texts: ``app.permissions`` (``MATRIX``, ``DEFAULT_DENIAL_REASONS``).

Pure module: no database access.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import Any

from app.config import get_settings

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "rag": {
        "red_critical_gaps": 2,
        "red_lens_below": 50,
        "red_near_days": 7,
        "amber_critical_gaps": 1,
        "amber_lens_below": 70,
    },
    "insights": {"low_readiness_below": 70, "within_days": 45},
    "calendar_horizon_days": 45,
    "leadership_decision_window_days": 30,
    "dashboard": {"my_work_limit": 200, "recent_activity_limit": 10},
    "narrative_top": 3,
    "default_tier": 3,
    "default_pricing_basis": "Fixed (contract)",
    "default_horizon_years": 5,
    "default_growth_pct": 0,
}

DEFAULT_MOCK_APPROVER: dict[str, str] = {
    "mock_role": "CISO_BISO",
    "approver_role": "IRM",
    "mock_label": "CISO/BISO",
}
DEFAULT_GATE_CHAIN: dict[str, str] = {"SG4_ATD": "AtD", "SG6_ATO": "AtO"}
DEFAULT_CRITICAL_SEVERITY = "Critical"


@lru_cache(maxsize=1)
def _read_seed_config(seed_dir: str) -> dict[str, Any]:
    with open(f"{seed_dir}/config.json", encoding="utf-8") as fh:
        return json.load(fh)


def seed_config() -> dict[str, Any]:
    """``seed/config.json`` (cached). A deep copy, so callers may modify it."""
    return copy.deepcopy(_read_seed_config(str(get_settings().seed_dir)))


# --- message templates --------------------------------------------------------------------------
# Placeholder catalogue: name -> (description, is_html). HTML placeholders are inserted as given
# (the code builds them from escaped parts); every other value is HTML-escaped by ``cfg.render``.
PLACEHOLDERS: dict[str, tuple[str, bool]] = {
    "recipient_name": ("Name of the person the message is for", False),
    "transition_name": ("Name of the transition", False),
    "gate_short": ("Short gate name, e.g. AtD", False),
    "days": ("Days to the decision (negative = overdue)", False),
    "or_focal_name": ("Name of the OR focal the message is sent on behalf of", False),
    "item_list": ("Bulleted list of the open items or inputs (links included)", True),
    "deep_link": ("Link to the page in Orion", False),
    "approver_role": ("Role of the first approver", False),
    "verdict": ("Readiness verdict, e.g. Ready with conditions", False),
    "orion_name": ("The assistant's name (Orion)", False),
    "greeting": ("'Hi <name>,' or 'Hello,'", True),
    "sign_off": ("'Thank you, Orion, on behalf of <OR focal>'", True),
    "when": ("When the decision is, e.g. 'AtD in 21 days'", False),
    "when_suffix": ("' (AtD in 21 days)' or nothing", False),
    "when_or_next_gate": ("'AtD in 21 days' or 'its next gate'", False),
    "item_title": ("First item title, plus 'and N other items'", False),
    "item_phrase": ("'this item' or 'these items'", False),
    "item_count_text": ("'1 item' / '3 items'", False),
    "open_item_count_text": ("'1 open item' / '3 open items'", False),
    "is_are": ("'is' or 'are' (matches the item count)", False),
    "input_count_text": ("'1 input' / '3 inputs'", False),
    "verdict_suffix": ("' (readiness: Ready)' or nothing", False),
    "summary_html": ("Optional summary paragraph", True),
    "approver_line": ("Optional 'First approver: OLM.' paragraph", True),
    "scope": ("Scope of a leadership update (transition, portfolio or all)", False),
    "paragraphs": ("The update text as paragraphs", True),
    "action_title": ("Title of the overdue action", False),
    "due_date": ("Due date", False),
    "days_overdue_text": ("'1 day' / '3 days'", False),
    "days_pending_text": ("'1 day' / '3 days'", False),
    "approver_name": ("Name of the approver who has not decided", False),
}
COMMON_PLACEHOLDERS: tuple[str, ...] = (
    "recipient_name",
    "transition_name",
    "gate_short",
    "days",
    "or_focal_name",
    "item_list",
    "deep_link",
    "approver_role",
    "verdict",
    "orion_name",
)
_LINK = '<p><a href="{{deep_link}}">Open in Orion</a></p>'

# key -> (name, subject, body, code source). The code source is the function in
# services/mock/ai_messages.py that produced the same text before CR-01 (B2 re-syncs them).
DEFAULT_TEMPLATES: dict[str, tuple[str, str, str, str]] = {
    "chaser": (
        "Chaser (open items)",
        "Action needed: {{item_title}} for {{transition_name}}{{when_suffix}}",
        "<p>{{greeting}}</p><p>{{transition_name}} is heading to {{when_or_next_gate}}. "
        "Could you please update {{item_phrase}} or let us know what is blocking you?</p>"
        '{{item_list}}<p><a href="{{deep_link}}">Open in Orion</a></p>{{sign_off}}',
        "ai_messages._chaser (items branch)",
    ),
    "reminder": (
        "Reminder / open items digest",
        "Reminder: {{open_item_count_text}} for {{transition_name}}{{when_suffix}}",
        "<p>{{greeting}}</p><p>A friendly reminder that {{item_count_text}} for {{transition_name}} "
        "{{is_are}} still open.</p>{{item_list}}{{sign_off}}",
        "ai_messages._reminder (default branch; also the R1 digest)",
    ),
    "input_request": (
        "Input request (OCET)",
        "Input needed: {{input_count_text}} for {{transition_name}}",
        "<p>{{greeting}}</p><p>To complete the estimate for {{transition_name}} we still need your "
        "input on:</p>{{item_list}}<p>Please reply with the figures or add them directly in "
        "Orion.</p>{{sign_off}}",
        "ai_messages._input_request",
    ),
    "approval_request": (
        "Approval request",
        "Approval request: {{gate_short}} for {{transition_name}}",
        "<p>{{greeting}}</p><p>{{transition_name}} is ready for your approval at "
        "{{gate_short}}{{verdict_suffix}}.</p>{{summary_html}}{{approver_line}}"
        '<p><a href="{{deep_link}}">Review and approve in Orion</a></p>{{sign_off}}',
        'ai_messages._approval_request (also the R4 draft: its own subject arrives in ctx["subject"])',
    ),
    "leadership_update": (
        "Leadership update",
        "Leadership update: {{scope}}",
        "<p>{{greeting}}</p>{{paragraphs}}{{sign_off}}",
        "ai_messages._leadership_update",
    ),
    "overdue_action": (
        "Overdue action chaser (R2)",
        "Overdue action: {{action_title}} for {{transition_name}} ({{days_overdue_text}} overdue)",
        "<p>{{greeting}}</p><p>The action <strong>{{action_title}}</strong> for {{transition_name}} "
        "was due {{due_date}} and is now overdue by {{days_overdue_text}}. Could you please update "
        "it or let us know what is blocking you?</p>" + _LINK + "{{sign_off}}",
        "ai_messages._overdue_action (R2)",
    ),
    "escalation": (
        "Escalation to the OR focal (R3)",
        "Escalation: {{gate_short}} approval for {{transition_name}} pending {{days_pending_text}}",
        "<p>{{greeting}}</p><p>{{approver_name}} has not yet decided the {{gate_short}} approval for "
        "{{transition_name}}; it has been pending for {{days_pending_text}}. You may want to follow "
        "up with them directly.</p>" + _LINK + "{{sign_off}}",
        "ai_messages._escalation (R3)",
    ),
    "pending_approval": (
        "Pending approval reminder (R3)",
        "Reminder: {{gate_short}} approval for {{transition_name}} is waiting for you",
        "<p>{{greeting}}</p><p>Your approval of {{gate_short}} for {{transition_name}} has been "
        "pending for {{days_pending_text}}. Please review and decide in Orion.</p>{{item_list}}"
        + _LINK
        + "{{sign_off}}",
        "ai_messages._reminder (pending_step branch, R3)",
    ),
    "monitoring_request": (
        "Monitoring requirements (R6)",
        "Monitoring requirements for {{transition_name}}",
        "<p>{{greeting}}</p><p>{{transition_name}} is in the design stage. Please capture the "
        "monitoring requirements below with the team.</p>{{item_list}}" + _LINK + "{{sign_off}}",
        "ai_messages._reminder (monitoring branch, R6)",
    ),
    "support_model_prompt": (
        "Support model prompt (R7)",
        "Create support model now?",
        "<p>{{greeting}}</p><p>The support-model evidence for {{transition_name}} has been accepted. "
        "Orion can now prepare the support model.</p>{{item_list}}" + _LINK + "{{sign_off}}",
        "ai_messages._reminder (support_model branch, R7)",
    ),
}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")


def placeholders_in(*texts: str) -> list[str]:
    """Placeholder names used in ``texts``, in first-use order."""
    seen: list[str] = []
    for text in texts:
        for name in _PLACEHOLDER_RE.findall(text or ""):
            if name not in seen:
                seen.append(name)
    return seen


def placeholder_specs(key: str) -> list[dict[str, Any]]:
    """The placeholders a template of ``key`` may use: the common set plus what its default uses."""
    _name, subject, body, _src = DEFAULT_TEMPLATES[key]
    names = list(COMMON_PLACEHOLDERS) + [
        n for n in placeholders_in(subject, body) if n not in COMMON_PLACEHOLDERS
    ]
    return [
        {"name": n, "description": PLACEHOLDERS[n][0], "html": PLACEHOLDERS[n][1]} for n in names
    ]
