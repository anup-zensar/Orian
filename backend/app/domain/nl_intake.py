"""Orion natural-language actions (FR-090, BR-050): plain language, a pasted email or an uploaded
.txt/.md/.vtt/.docx document -> HUMAN-CONFIRMED proposals.

PRINCIPLES (binding for builders)
=================================
1. Orion only DRAFTS. Every outcome is a ``proposal`` (stored ``OrionProposal``), a read-only card, a
   ``link`` or a draft in the drafts queue. A permitted human clicks Accept / Create / Send. The only
   modules allowed to import mutating domain functions are listed in ``domain/proposals.py``; this module
   imports NONE of them (it may read the DB and call ``domain.proposals.create_proposal``).
2. NO hard-coded business enumerations. Project types, portfolios, regions, option lists, roles, users
   and custom intake fields are read from the configuration at runtime by ``build_vocabulary`` (the
   same sources as GET /reference), so an Admin who adds a project type or portfolio in the UI is
   understood immediately, with no code change. Behavioural flags come from data too:
   ``requires_tiering`` and the required intake fields (project type), ``requires_sites`` (portfolio).
3. Admin-tunable language: the synonyms an Admin types on a project type or portfolio, and the
   Glossary dropdown list, are merged into ``vocab`` at runtime; never code.
4. Never invent: a value is returned only when it exists in the vocabulary. Anything unsure is
   ``ambiguous`` (candidates) or ``missing`` - never guessed - and is shown to the human as such.
5. Same input -> same output (mock). The live LLM only replaces the extractor
   (``AIService.extract_intake`` / ``parse_command``); this module re-validates every value the LLM
   returns against the vocabulary and drops unknown ones, so a hallucination never reaches a proposal.

INTENT_CATALOG
==============
Each entry: ``intent`` (key), ``label``, ``examples`` (phrasings; also the mock's training set and the
UI chips), ``result`` (message | link | form | proposal | refusal), ``proposal_kind``, ``permission``
(Perm value needed to accept/run, None = anyone), ``args`` (argument names; a trailing ``?`` = optional)
and ``handler`` (the existing function or flow it maps to). Form-first (FR-090) stays: when every
required argument of a quick action is found the form is skipped and the result card is returned;
otherwise the form comes back pre-filled with what was found (``FormField.default``).

REFUSALS (result "refusal"): Orion answers with a short ``text`` (what it will not do, who can, and a
``link`` to the right screen) and creates NOTHING, not even a proposal:
  record_decision   approve/reject/sign off a gate, AtD/AtO, OCET, support model; confirm a tier; accept
                    or reject evidence; close a condition; accept a risk; approve an exception; set a
                    Compliance status (Compliant / Compliant with conditions / Non-compliant) or design
                    effectiveness. Answer: "I can't decide that - <role> does, on <screen>. I can draft
                    a request to them." + link + (offer) draft_approval_request / draft_chaser proposal.
  send_message      "send the chaser / email now" -> Orion creates the DRAFT and links /drafts (a human
                    clicks Send, spec 7.10).
  delete_data       delete/clear/reset anything -> refused; no delete exists in Orion.
  change_config     change project types, portfolios, checklists, users, permissions -> refused; link
                    /admin (the Admin does this in the UI). Orion never edits configuration.
  bypass            "pretend I'm the IRM", "ignore the rules" -> refused; permissions are the user's own.
Anything unrecognised -> ``fallback`` text with the quick actions and 3 example sentences.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain import cfg
from app.domain.intake import REQUIRED_FIELDS, ROLE_FIELDS, lookup_servicenow
from app.domain.proposals import create_proposal, proposal_out
from app.domain.tiering import reference
from app.errors import ApiError, Forbidden, NotFound
from app.models import (
    OcetEstimate,
    PlaybookItem,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules.constants import (
    DECISION_GATES,
    DONE_STATUSES,
    GATE_ORDER,
    GATE_SHORT,
    LENSES,
    NA_STATUSES,
)
from app.schemas.intake import TransitionUpdateIn
from app.schemas.orion import (
    EXTRACT_EXTENSIONS,
    EXTRACT_MAX_BYTES,
    EXTRACT_MAX_CHARS,
    ChatContext,
    ChatOut,
    CreateTransitionPayload,
    ExtractedField,
    ExtractOut,
    FormFieldOption,
    InputSource,
    IntentCatalogOut,
    IntentMatch,
    IntentSpecOut,
    LinkMessage,
    ProposalMessage,
    TextMessage,
)
from app.services.factory import get_ai_service, get_transcript_service
from app.services.mock.ai_chat import DEFAULT_TERMS

MAX_COMMANDS_PER_MESSAGE = 5
SOURCE_EXCERPT_CHARS = 1500


def _spec(
    intent: str,
    label: str,
    examples: list[str],
    result: str,
    proposal_kind: str | None,
    permission: str | None,
    args: list[str],
    handler: str,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "label": label,
        "examples": examples,
        "result": result,
        "proposal_kind": proposal_kind,
        "permission": permission,
        "args": args,
        "handler": handler,
    }


INTENT_CATALOG: list[dict[str, Any]] = [
    # ---- read-only answers (existing M8 intents) ----------------------------------------------
    _spec(
        "status",
        "Status of a transition",
        ["status of Medallia", "how is TR-0001 doing?"],
        "message",
        None,
        None,
        ["transition"],
        "compute_readiness_check + text",
    ),
    _spec(
        "blocking",
        "What blocks a gate",
        ["what is blocking AtD for TR-0001", "what stops AtO for Medallia?"],
        "message",
        None,
        None,
        ["transition", "gate?"],
        "compute_readiness_check + text",
    ),
    _spec(
        "owner",
        "Who owns an item",
        ["who owns S3-019?"],
        "message",
        None,
        None,
        ["item_id"],
        "item owner lookup",
    ),
    _spec(
        "glossary",
        "Explain a term",
        ["what is OCET?", "explain AtO"],
        "message",
        None,
        None,
        ["term"],
        "glossary text (terms read from reference data)",
    ),
    _spec(
        "red_transitions",
        "Show red transitions",
        ["show red transitions", "which transitions are at risk?"],
        "message",
        None,
        None,
        [],
        "control tower query + table",
    ),
    # ---- quick actions in words (form skipped when all arguments are found) -------------------
    _spec(
        "assess_gate_readiness",
        "Assess gate readiness",
        ["assess readiness of Medallia for AtD", "are we ready for SG3?"],
        "message",
        None,
        None,
        ["transition", "gate?"],
        "quick_action assess_gate_readiness",
    ),
    _spec(
        "track_owner_actions",
        "Track owner actions",
        ["who still owes us something on TR-0001?"],
        "message",
        None,
        None,
        ["transition"],
        "quick_action track_owner_actions",
    ),
    _spec(
        "draft_owner_reminders",
        "Draft owner reminders",
        ["remind everyone with overdue items on TR-0001"],
        "message",
        None,
        "run_reminders",
        ["transition"],
        "domain.reminders.run_reminders (drafts only)",
    ),
    _spec(
        "create_leadership_update",
        "Leadership update",
        ["write a leadership update for the GCC portfolio", "update for all transitions"],
        "message",
        None,
        "generate_leadership_update",
        ["scope", "scope_id?"],
        "domain.leadership.generate_update",
    ),
    _spec(
        "open_module",
        "Open OCET or support model",
        ["open the OCET for TR-0001", "create the support model for Medallia"],
        "link",
        None,
        None,
        ["transition", "module"],
        "link /transitions/<id>/ocet or /support-model",
    ),
    # ---- proposals (a permitted human accepts) -------------------------------------------------
    _spec(
        "create_transition",
        "Start a new transition from a description or document",
        [
            "Start a gate review for the Medallia VOC project, PRJ0012345, GCC, go live 1 March",
            "New transition: loyalty chatbot for Retail, architect Mei, OLM Sofia, customer data",
            "(paste an email or upload a .docx / .txt / .vtt)",
        ],
        "proposal",
        "create_transition",
        "create_transition",
        ["intake fields found in the text"],
        "hand-off to /transitions/new?proposal=<id>; the human clicks Create",
    ),
    _spec(
        "update_transition",
        "Change a transition's details",
        ["move next decision date of TR-0001 to 5 Dec", "make Sofia the OLM on Medallia"],
        "proposal",
        "update_transition",
        "edit_transition",
        ["transition", "changes"],
        "PATCH /transitions/{id} (intake fields only, never tier / gate / status)",
    ),
    _spec(
        "create_action",
        "Create an action",
        ["ask Tom to finish the DPIA for S3-019 by Friday", "action for Mei: update the diagram"],
        "proposal",
        "create_action",
        "manage_actions",
        ["title", "owner_user_id", "due_date", "item_ids?", "priority?"],
        "POST /transitions/{id}/actions",
    ),
    _spec(
        "draft_chaser",
        "Chase an owner",
        ["chase Asha on S3-019", "nudge the owners of the overdue items"],
        "proposal",
        "draft_chaser",
        "send_drafts",
        ["item_ids"],
        "domain.drafts.draft_chaser (creates a DRAFT; a human sends it)",
    ),
    _spec(
        "request_inputs",
        "Ask for OCET inputs",
        ["ask the architect for the missing OCET inputs"],
        "proposal",
        "request_inputs",
        "send_drafts",
        ["version_id", "line_ids"],
        "input-request draft",
    ),
    _spec(
        "request_exception",
        "Request an exception",
        ["we need an exception for S45-006 because the vendor cannot meet it"],
        "proposal",
        "request_exception",
        "request_exception",
        ["item_id", "text"],
        "POST /transitions/{id}/exceptions (Compliance items only)",
    ),
    _spec(
        "request_approval",
        "Request a gate approval",
        ["request AtD approval for TR-0001"],
        "proposal",
        "request_approval",
        "send_drafts",
        ["transition", "gate"],
        "domain.drafts.draft_approval_request (a DRAFT; nobody is approved)",
    ),
    _spec(
        "accept_applicability",
        "Mark items applicable or not applicable",
        ["S3-005 does not apply because there is no card data"],
        "proposal",
        "accept_applicability",
        "confirm_scope",
        ["decisions"],
        "scope accept-decisions operation (OR focal)",
    ),
    _spec(
        "update_item",
        "Update an item (owner, note, Business/Technical status)",
        [
            "assign S3-019 to Tom",
            "note on FW-008: waiting for vendor quote",
            "S3-020 is complete",
            "S3-021 is a critical gap, no test environment",
        ],
        "proposal",
        "update_item",
        "update_bt_status",
        ["item_id", "owner_user_id?", "note?", "status?", "gap_severity?"],
        "PATCH /items/{id}; Compliance-lens status is refused (see record_decision)",
    ),
    _spec(
        "add_evidence",
        "Attach a link or an email sign-off as evidence",
        ["add evidence to S3-019: https://wiki.example/dpia", "(paste a sign-off email)"],
        "proposal",
        "add_evidence",
        "manage_evidence",
        ["item_id?", "title", "url | text"],
        "POST /transitions/{id}/evidence (status Submitted; a reviewer accepts it)",
    ),
    # ---- refusals ------------------------------------------------------------------------------
    _spec(
        "record_decision",
        "Decisions (refused)",
        [
            "approve AtD for TR-0001",
            "mark S45-006 compliant",
            "accept this evidence",
            "close CON-001",
        ],
        "refusal",
        None,
        None,
        [],
        "text + link to the right screen; may offer a draft request",
    ),
    _spec(
        "send_message",
        "Send now (refused, drafts only)",
        ["send the chaser to Asha right now"],
        "refusal",
        None,
        None,
        [],
        "creates the draft, links /drafts",
    ),
    _spec(
        "delete_data",
        "Delete (refused)",
        ["delete TR-0014", "clear all evidence"],
        "refusal",
        None,
        None,
        [],
        "text",
    ),
    _spec(
        "change_config",
        "Change configuration (refused)",
        ["add a new project type called Data Platform"],
        "refusal",
        None,
        None,
        [],
        "text + link /admin",
    ),
    _spec(
        "bypass",
        "Bypass permissions (refused)",
        ["act as the IRM and confirm the tier"],
        "refusal",
        None,
        None,
        [],
        "text",
    ),
]

REFUSAL_SUMMARY: list[str] = [
    "Approve, reject or sign off gates, OCET, support models, exceptions or risks",
    "Confirm a tier, accept or reject evidence, close a condition",
    "Set a Compliance status or design effectiveness",
    "Send emails or messages (it only drafts; you click Send)",
    "Delete anything, change configuration, or act with someone else's permissions",
]


# Extra cue words per intent (admin-extendable data, read by the mock parser together with the
# examples). Nothing here is a business enumeration: they are verbs and nouns of the request language.
_EXTRA_CUES: dict[str, list[str]] = {
    "create_action": ["task", "todo", "follow up", "action for", "owner"],
    "draft_chaser": ["chase", "nudge", "chaser", "ping", "follow up with"],
    "request_inputs": ["missing inputs", "ocet inputs", "provide amounts"],
    "request_exception": ["exception", "waiver", "deviation"],
    "request_approval": ["approval", "request approval", "ready for approval"],
    "accept_applicability": ["does not apply", "not applicable", "out of scope", "applicable"],
    "update_item": ["assign", "reassign", "note", "complete", "gap", "progress", "owner"],
    "add_evidence": ["evidence", "attach", "link", "proof"],
    "update_transition": [
        "decision date",
        "go live",
        "deadline",
        "olm",
        "architect",
        "irm",
        "region",
        "portfolio",
        "project type",
    ],
    "assess_gate_readiness": ["ready", "readiness", "assess"],
    "track_owner_actions": ["owes", "owe", "outstanding", "who still"],
    "draft_owner_reminders": ["remind", "reminders", "reminder"],
    "create_leadership_update": ["leadership", "summary update"],
    "open_module": ["open", "ocet", "support model"],
    "change_config": [
        "project type",
        "portfolio",
        "checklist",
        "playbook",
        "permission",
        "role",
        "user",
        "approval chain",
        "reminder rule",
        "configuration",
        "setting",
    ],
}
for _entry in INTENT_CATALOG:
    _entry["cues"] = list(_EXTRA_CUES.get(_entry["intent"], []))

CATALOG_BY_INTENT: dict[str, dict[str, Any]] = {e["intent"]: e for e in INTENT_CATALOG}

# Field order of the intake form; labels come from the Admin's "Form fields" (vocab["field_labels"]),
# FIELD_LABEL is the fallback for fields the Admin cannot rename.
FIELD_ORDER = (
    "name",
    "servicenow_project_id",
    "project_type",
    "portfolio",
    "region",
    "market",
    "sites",
    "audience",
    "write_actions",
    "sensitive_data",
    "target_gate",
    "investment_type",
    "delivery_method",
    "description",
    "or_focal_user_id",
    "pm_user_id",
    "architect_user_id",
    "olm_user_id",
    "irm_user_id",
    "next_decision_date",
)
FIELD_LABEL = {
    "servicenow_project_id": "Project ID",
    "sites": "Sites",
    **{field: label for field, (_role, label) in ROLE_FIELDS.items()},
}
OPTION_FIELD_NAMES = (
    "audience",
    "write_actions",
    "sensitive_data",
    "target_gate",
    "investment_type",
    "delivery_method",
)
MIN_DATE = date(2000, 1, 1)
# Words that mean a status for the Business/Technical lenses (language, not business data).
_STATUS_SYNONYMS = {
    "Complete": ["done", "finished", "completed", "complete", "closed out"],
    "In progress": ["started", "working on", "underway", "in flight"],
    "Not started": ["not begun", "not yet started"],
    "Gap": ["blocked", "missing", "at risk"],
}
_MODULES = [
    {"key": "ocet", "phrases": ["ocet", "operate cost estimate", "cost estimate"]},
    {"key": "support_model", "phrases": ["support model"]},
]


# ---------------------------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------------------------
def _or_list(values: list[str]) -> str:
    """'Critical, Major or Minor'."""
    return " or ".join([", ".join(values[:-1]), values[-1]]) if len(values) > 1 else "".join(values)


def _middle(values: list[str]) -> str:
    """The option used when none was named: the middle of the list ("Medium" of High/Medium/Low)."""
    return values[len(values) // 2]


def build_vocabulary(db: Session) -> dict[str, Any]:
    """Everything the extractors may match against, loaded from the configuration on EVERY call, so
    Admin edits are live. Shape (plain JSON, deterministic order):

    ``project_types`` [{name, requires_tiering, required, synonyms}] (``synonyms`` = the label and the
    synonyms typed by the Admin; ``required`` = the intake fields required for the type);
    ``portfolios`` [{name, requires_sites, synonyms}]; ``regions`` [str]; ``options``
    {audience|write_actions|sensitive_data|target_gate|investment_type|delivery_method: [str]};
    ``field_labels`` {field: label} (built-in and additional fields); ``custom_fields`` [{key, label,
    type}] (the additional intake fields); ``gates`` [{code, short, label}]
    ("AtD" = short); ``roles`` [{code, label}] and ``role_fields`` {"or_focal_user_id": "OR_FOCAL",
    ...} (from ``domain.intake.ROLE_FIELDS``); ``users`` [{id, name, role, email}]; ``transitions``
    [{id, name, portfolio}]; ``terms`` (glossary). Read-only; no writes."""
    ref = reference(db)
    users = sorted(db.scalars(select(User)).all(), key=lambda u: u.id)
    transitions = sorted(db.scalars(select(Transition)).all(), key=lambda t: t.id)
    terms = dict(DEFAULT_TERMS)
    terms.update({o.value: o.description for o in cfg.options(db, "glossary") if o.description})
    b_t_statuses = [
        st
        for st in cfg.option_values(db, "item_statuses_business", active_only=False)
        if st not in NA_STATUSES
    ]
    status_words = []
    for st in b_t_statuses:
        status_words.append({"phrase": st.lower(), "status": st})
        label = cfg.option_label(db, "item_statuses_business", st).lower()
        if label != st.lower():
            status_words.append({"phrase": label, "status": st})
    for status, phrases in _STATUS_SYNONYMS.items():
        status_words += [{"phrase": ph, "status": status} for ph in phrases]
    options = {}
    for name in OPTION_FIELD_NAMES:
        field = cfg.intake_field(db, name)
        options[name] = cfg.option_values(db, (field.option_list if field else None) or name)
    custom = [f for f in cfg.intake_fields(db) if not f.builtin]
    field_labels = {f.key: f.label for f in cfg.intake_fields(db)}
    return {
        "today": clock.today().isoformat(),
        "project_types": [
            {
                "name": p.code,
                "requires_tiering": p.requires_tiering,
                "required": cfg.required_fields_for(db, p.code),
                "synonyms": _synonyms(p.label, p.code, p.synonyms),
            }
            for p in sorted(cfg.project_types(db), key=lambda p: p.code)
        ],
        "portfolios": [
            {
                "name": p.name,
                "requires_sites": p.requires_sites,
                "synonyms": _synonyms(p.label, p.name, p.synonyms),
            }
            for p in sorted(cfg.portfolios(db), key=lambda p: p.name)
        ],
        "regions": cfg.option_values(db, "regions"),
        "options": dict(sorted(options.items())),
        "field_labels": field_labels,
        "custom_fields": [{"key": f.key, "label": f.label, "type": f.type} for f in custom],
        "gates": [
            {"code": g["code"], "short": g.get("short", g["code"]), "label": g.get("label", "")}
            for g in ref.get("gates", [])
        ],
        "roles": [{"code": r.code, "label": r.label} for r in cfg.roles(db)],
        "role_fields": {field: role for field, (role, _label) in ROLE_FIELDS.items()},
        "users": [{"id": u.id, "name": u.name, "role": u.role, "email": u.email} for u in users],
        "transitions": [
            {"id": t.id, "name": t.name, "portfolio": t.portfolio, "current_gate": t.current_gate}
            for t in transitions
        ],
        "terms": terms,
        "synonyms": {},
        "priorities": cfg.option_values(db, "action_priorities"),
        "severities": cfg.option_values(db, "severities"),
        "status_words": status_words,
        "item_statuses": {
            lens: cfg.option_values(db, f"item_statuses_{lens.lower()}", active_only=False)
            for lens in LENSES
        },
        "modules": _MODULES,
    }


def _synonyms(label: str, code: str, typed: Any) -> list[str]:
    """Other ways to name a project type or portfolio: its label (when renamed) and the Admin's synonyms."""
    names = ([label] if label and label != code else []) + [str(x) for x in (typed or [])]
    return list(dict.fromkeys(names))


# ---------------------------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------------------------
class PayloadTooLarge(ApiError):
    status_code = 413


def read_document_text(filename: str, content: bytes) -> tuple[str, bool]:
    """Text of an uploaded document via ``TranscriptService.get_text`` (.txt, .md, .vtt, .docx).
    Returns (text, truncated) with text cut at ``EXTRACT_MAX_CHARS``. BadRequest 400 for another
    extension ("Unsupported file type - upload .txt, .md, .vtt or .docx") or empty text ("No readable
    text in the document"); 413 above ``EXTRACT_MAX_BYTES``. The document itself is NOT stored: only
    the excerpt lives in the proposal payload."""
    name = (filename or "").lower()
    if not name.endswith(EXTRACT_EXTENSIONS):
        raise ApiError("Unsupported file type - upload .txt, .md, .vtt or .docx")
    if len(content) > EXTRACT_MAX_BYTES:
        raise PayloadTooLarge("The file is larger than 5 MB")
    text = get_transcript_service().get_text(filename, content).strip()
    if not text:
        raise ApiError("No readable text in the document")
    if len(text) > EXTRACT_MAX_CHARS:
        return text[:EXTRACT_MAX_CHARS], True
    return text, False


# ---------------------------------------------------------------------------------------------
# Create a transition from words
# ---------------------------------------------------------------------------------------------
def _user_display(vocab: dict[str, Any], user_id: str) -> str | None:
    for u in vocab["users"]:
        if u["id"] == user_id:
            return str(u["name"])
    return None


def _validate_value(
    name: str, value: Any, vocab: dict[str, Any], portfolio: str | None
) -> tuple[Any, str | None]:
    """(clean value or None, reason when the value is rejected). Principle 5: only vocabulary members."""
    if value in (None, "", []):
        return None, None
    if name in ("name", "description", "market", "servicenow_project_id"):
        text = " ".join(str(value).split()) if name != "description" else str(value).strip()
        limit = {"name": 200, "description": 2000, "market": 120, "servicenow_project_id": 20}[name]
        return text[:limit] or None, None
    if name == "project_type":
        ok = value in {p["name"] for p in vocab["project_types"]}
        return (value, None) if ok else (None, "Not one of the project types")
    if name == "portfolio":
        ok = value in {p["name"] for p in vocab["portfolios"]}
        return (value, None) if ok else (None, "Not one of the portfolios")
    if name == "region":
        return (value, None) if value in vocab["regions"] else (None, "Not one of the regions")
    if name in OPTION_FIELD_NAMES:
        ok = value in vocab["options"].get(name, [])
        return (value, None) if ok else (None, "Not one of the options")
    if name in vocab["role_fields"]:
        user = next((u for u in vocab["users"] if u["id"] == value), None)
        if user is None:
            return None, "Unknown user"
        if user["role"] != vocab["role_fields"][name]:
            return None, f"{user['name']} does not have the {vocab['role_fields'][name]} role"
        return value, None
    if name == "next_decision_date":
        try:
            parsed = date.fromisoformat(str(value))
        except ValueError:
            return None, "Not a valid date"
        return (parsed.isoformat(), None) if parsed >= MIN_DATE else (None, "Date too early")
    if name == "sites":
        requires = any(p["name"] == portfolio and p["requires_sites"] for p in vocab["portfolios"])
        if not requires:
            return None, "Sites only apply to a portfolio that needs sites"
        rows = [
            {"site_id": str(r["site_id"]).strip(), "site_key": str(r["site_key"]).strip()}
            for r in value
            if isinstance(r, dict) and r.get("site_id") and r.get("site_key")
        ]
        return (rows or None), (None if rows else "No complete site rows")
    return None, "Unknown field"


def _display(name: str, value: Any, vocab: dict[str, Any]) -> str | None:
    if value in (None, "", []):
        return None
    if name in vocab["role_fields"]:
        return _user_display(vocab, str(value))
    if name == "sites":
        return ", ".join(f"{r['site_id']} / {r['site_key']}" for r in value)
    return str(value)


def required_fields(
    vocab: dict[str, Any], project_type: str | None, portfolio: str | None
) -> list[str]:
    """Required for Create: the same rules as POST /transitions (always-required fields, what the
    Admin required for the project type, and sites for a portfolio that needs them)."""
    required = list(REQUIRED_FIELDS)
    for p in vocab["project_types"]:
        if p["name"] == project_type:
            required += [k for k in p["required"] if k not in required]
    if any(p["name"] == portfolio and p["requires_sites"] for p in vocab["portfolios"]):
        required.append("sites")
    return required


def _label(vocab: dict[str, Any], name: str) -> str:
    """Field label as the Admin named it (Forms & dropdowns)."""
    return str(vocab["field_labels"].get(name) or FIELD_LABEL.get(name, name))


def _extracted_fields(
    raw: dict[str, dict[str, Any]],
    vocab: dict[str, Any],
    *,
    source: InputSource,
    user: User | None,
) -> list[ExtractedField]:
    """Re-validate the extractor output (mock or live) and return every intake field in form order."""
    portfolio_raw = raw.get("portfolio", {})
    portfolio = (
        portfolio_raw.get("value") if portfolio_raw.get("state") in ("found", "inferred") else None
    )
    text_source = "document" if source == "document" else "text"
    out: dict[str, ExtractedField] = {}
    for name in FIELD_ORDER:
        entry = raw.get(name) or {}
        state = entry.get("state", "missing")
        label = _label(vocab, name)
        if state in ("found", "inferred"):
            value, why = _validate_value(name, entry.get("value"), vocab, portfolio)
            if value is None:
                out[name] = ExtractedField(
                    name=name, label=label, state="missing", note=why or "Value not recognised"
                )
                continue
            src = entry.get("source") or "text"
            src = text_source if src == "text" else src
            if src not in ("servicenow", "text", "document", "context", "inferred"):
                src = "text"
            out[name] = ExtractedField(
                name=name,
                label=label,
                value=value,
                display=_display(name, value, vocab),
                state=state,
                source=src,
                confidence=float(entry.get("confidence") or 0.0),
                evidence=(entry.get("evidence") or None),
                note=entry.get("note"),
            )
        elif state == "ambiguous":
            options = [
                FormFieldOption(value=str(c["value"]), label=str(c["label"]))
                for c in entry.get("candidates", [])
                if c.get("value") not in (None, "")
            ]
            out[name] = ExtractedField(
                name=name,
                label=label,
                state="ambiguous" if len(options) > 1 else "missing",
                confidence=float(entry.get("confidence") or 0.0),
                evidence=entry.get("evidence"),
                candidates=options if len(options) > 1 else [],
                note=entry.get("note"),
            )
        else:
            out[name] = ExtractedField(
                name=name, label=label, state="missing", note=entry.get("note")
            )
    # OR focal defaults to the writing user (context, inferred) when none was named
    focal = out["or_focal_user_id"]
    if (
        focal.state == "missing"
        and user is not None
        and user.role == ROLE_FIELDS["or_focal_user_id"][0]
    ):
        out["or_focal_user_id"] = ExtractedField(
            name="or_focal_user_id",
            label=focal.label,
            value=user.id,
            display=user.name,
            state="inferred",
            source="context",
            confidence=0.6,
            note="Defaulted to you - change it if someone else owns this transition",
        )
    required = set(required_fields(vocab, out["project_type"].value, out["portfolio"].value))
    result = []
    for name in FIELD_ORDER:
        f = out[name]
        f.required = name in required
        result.append(f)
    # Additional details the Admin made required for this project type: Orion cannot read them from
    # text, so they are listed as missing for the human to fill in on the form.
    for field in vocab["custom_fields"]:
        if field["key"] in required:
            result.append(
                ExtractedField(
                    name=field["key"],
                    label=field["label"],
                    state="missing",
                    required=True,
                    note="Additional detail - fill it in on the form",
                )
            )
    return result


def extract_transition_proposal(
    db: Session,
    user: User,
    text: str,
    *,
    source: InputSource,
    source_name: str | None = None,
) -> ChatOut:
    """Create-transition flow (the heart of "create from words").

    1. ``vocab = build_vocabulary(db)``. If ``text`` contains ``PRJ\\d+`` (case-insensitive, first
       match, upper-cased) call ``domain.intake.lookup_servicenow`` inside try/except NotFound -> record
       ``servicenow_found`` and keep going (a failed lookup is not an error).
    2. ``AIService.extract_intake(text, vocab, servicenow_record)`` (mock or live; live falls back to
       the mock on any error).
    3. Re-validate (principle 5): option fields must equal an option string of ``vocab``; project_type,
       portfolio and region must be vocabulary members; ``*_user_id`` must be a user whose role equals
       the picker's role (``ROLE_FIELDS``); dates ISO and not before 2000-01-01; ``sites`` only when the
       portfolio ``requires_sites`` (otherwise dropped with a note); invalid -> state "missing" with a
       note. ServiceNow values win over text for name, project_type, portfolio, region, market,
       investment_type, delivery_method, description and pm (source "servicenow"); text wins for
       everything ServiceNow does not know. OR focal: if the writing user's role is OR_FOCAL and none
       was named, default to the user (source "context", state "inferred").
    4. Required for Create (``missing_fields``): name, project_type, portfolio, region, or_focal_user_id,
       plus audience / write_actions / sensitive_data when the project type ``requires_tiering``, plus
       ``sites`` when the portfolio ``requires_sites`` - the same rules as POST /transitions.
    5. ``create_proposal(kind="create_transition", transition_id=None, title="Start transition: <name
       or 'new transition'>", payload=CreateTransitionPayload)`` and return the ``proposal`` message
       preceded by one ``text`` message ("I found N of M fields. Review the card, then click Open pre-filled form to open
       the pre-filled form - nothing is created yet."). When nothing at all was found the answer is
       only "I could not find any intake details - tell me the project name, type, portfolio and
       region." and no proposal is stored.
    The ``ChatOut`` is used by both POST /orion/chat and POST /orion/extract. Writes only the
    OrionProposal row (flush, no audit)."""
    vocab = build_vocabulary(db)
    prj = re.search(r"\bPRJ\d+\b", text, re.IGNORECASE)
    prj_id = prj.group(0).upper() if prj else None
    record: dict[str, Any] | None = None
    sn_found: bool | None = None
    if prj_id:
        try:
            sn = lookup_servicenow(db, prj_id)
            record = {**sn.model_dump(), "pm": sn.pm_name}
            sn_found = True
        except NotFound:
            sn_found = False
    extraction = get_ai_service().extract_intake(text, vocab, record)
    fields = _extracted_fields(extraction["fields"], vocab, source=source, user=user)
    by_name = {f.name: f for f in fields}
    sn_field = by_name["servicenow_project_id"]
    if prj_id and not sn_field.value:
        sn_field.value, sn_field.display = prj_id, prj_id
        sn_field.state, sn_field.source, sn_field.confidence = "found", "text", 1.0
    if sn_found is False:
        sn_field.note = f"{prj_id} was not found in ServiceNow (mock) - check the id"
    for f in fields:
        if f.state == "ambiguous" and not f.note:
            f.note = "Several matches - choose one"
    anything = any(f.state in ("found", "inferred") and f.source != "context" for f in fields)
    if not anything:
        return ChatOut(
            messages=[
                TextMessage(
                    text=(
                        "I could not find any intake details - tell me the project name, type, "
                        "portfolio and region."
                    )
                ),
                LinkMessage(
                    label="Open the new transition form",
                    href="/transitions/new",
                    description="Fill it in yourself",
                ),
            ]
        )
    required = [f for f in fields if f.required]
    have = [f for f in required if f.state in ("found", "inferred")]
    missing = [f.name for f in required if f.state not in ("found", "inferred")]
    ambiguous = [f.name for f in fields if f.state == "ambiguous"]
    prefill = {f.name: f.value for f in fields if f.state in ("found", "inferred") and f.value}
    payload = CreateTransitionPayload(
        prefill=prefill,
        fields=fields,
        missing_fields=missing,
        ambiguous_fields=ambiguous,
        servicenow_project_id=prj_id,
        servicenow_found=sn_found,
        source=source,
        source_name=source_name,
        source_excerpt=text[:SOURCE_EXCERPT_CHARS],
        summary=(
            f"Found {len(have)} of {len(required)} required fields"
            + (f" - {len(missing)} need your input" if missing else " - ready to review")
        ),
    )
    warnings: list[str] = []
    if prj_id:
        existing = db.scalars(
            select(Transition.id).where(
                Transition.servicenow_project_id == prj_id, Transition.status == "Active"
            )
        ).first()
        if existing:
            warnings.append(
                f"{existing} already exists for {prj_id} - open it, or confirm to create a second transition"
            )
    payload.warnings = warnings
    proposal = create_proposal(
        db,
        kind="create_transition",
        title=f"Start transition: {by_name['name'].value or 'new transition'}",
        payload=payload.model_dump(mode="json"),
        transition_id=None,
        created_by=user.id if user is not None else None,
    )
    return ChatOut(
        messages=[
            TextMessage(
                text=(
                    f"I found {len(have)} of {len(required)} required fields. Review the card, then "
                    "click Open pre-filled form - nothing is created yet."
                    + "".join(f" Note: {w}." for w in warnings)
                )
            ),
            ProposalMessage(proposal=proposal_out(db, proposal, user)),
        ]
    )


# ---------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------
_QUICK_ACTION_OF = {
    "assess_gate_readiness": "assess_gate_readiness",
    "track_owner_actions": "track_owner_actions",
    "draft_owner_reminders": "draft_owner_reminders",
    "create_leadership_update": "create_leadership_update",
}
_NEEDS_TRANSITION = {
    "update_transition",
    "create_action",
    "draft_chaser",
    "request_inputs",
    "request_exception",
    "request_approval",
    "accept_applicability",
    "update_item",
    "add_evidence",
    "assess_gate_readiness",
    "track_owner_actions",
    "draft_owner_reminders",
    "open_module",
}


def _text(text: str) -> TextMessage:
    return TextMessage(text=text)


def _item_row(db: Session, transition_id: str, item_id: str) -> TransitionItem | None:
    return db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition_id,
            TransitionItem.playbook_item_id == item_id,
        )
    ).first()


def _open_items(db: Session, transition: Transition) -> list[TransitionItem]:
    rows = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition.id,
            TransitionItem.applicability == "Applies",
        )
    ).all()
    return [r for r in rows if r.status not in DONE_STATUSES and r.status not in NA_STATUSES]


def _derive_chaser_items(db: Session, transition: Transition, args: dict[str, Any]) -> list[str]:
    """Items to chase when the message named none: the named owner's open items, or the overdue items
    (due at an earlier gate than the current one); at most 10, deterministic."""
    rows = _open_items(db, transition)
    current = GATE_ORDER.get(transition.current_gate, 0)
    owner_id = args.get("owner_user_id")
    if owner_id:
        rows = [r for r in rows if r.owner_user_id == owner_id]
    elif args.get("overdue"):
        rows = [r for r in rows if GATE_ORDER.get(r.due_gate, 0) < current]
    else:
        return []
    rows.sort(key=lambda r: (GATE_ORDER.get(r.due_gate, 0), r.playbook_item_id))
    return [r.playbook_item_id for r in rows][:10]


def _proposal_message(
    db: Session,
    user: User,
    *,
    kind: str,
    title: str,
    payload: dict[str, Any],
    transition_id: str | None,
) -> ProposalMessage:
    row = create_proposal(
        db,
        kind=kind,  # type: ignore[arg-type]
        title=title,
        payload=payload,
        transition_id=transition_id,
        created_by=user.id,
    )
    return ProposalMessage(proposal=proposal_out(db, row, user))


def _refusal(intent: str, cmd: dict[str, Any], context_tid: str | None = None) -> list[Any]:
    excerpt = str(cmd.get("excerpt", "")).lower()
    args = cmd.get("arguments", {})
    tid = args.get("transition") or context_tid
    items = args.get("items") or []
    if intent == "record_decision":
        if re.search(r"\b(atd|ato|gate|go[\s-]?live)\b", excerpt):
            who = "the OR focal records gate decisions, after the approval chain has agreed"
            where = "the Gates tab"
            href = f"/transitions/{tid}/gates" if tid else "/approvals"
        elif re.search(r"\b(compliant|compliance|tier|evidence|design effectiveness)\b", excerpt):
            who = (
                "the IRM sets compliance status and confirms tiers, and the evidence reviewer "
                "accepts evidence"
            )
            where = "the Assessment tab"
            href = (
                f"/transitions/{tid}/assessment" + (f"?item={items[0]}" if items else "")
                if tid
                else "/transitions"
            )
        elif re.search(r"\b(condition|con\s*-?\d+|risk|exception)\b", excerpt):
            who = "the OR focal or the IRM manage conditions, risks and exceptions"
            where = "the Conditions tab"
            href = f"/transitions/{tid}/conditions" if tid else "/transitions"
        else:
            who = "the person who owns that decision does"
            where = "the transition workspace"
            href = f"/transitions/{tid}" if tid else "/transitions"
        return [
            _text(
                f"I can't decide that - {who}. I only draft and recommend; a permitted person "
                "clicks. Nothing was changed. Ask me to draft a request or a chaser if you want one."
            ),
            LinkMessage(label=f"Open {where}", href=href),
        ]
    if intent == "send_message":
        return [
            _text(
                "I never send messages myself. I can prepare a draft (for example 'chase Asha on "
                "S3-019' or 'request AtD approval for TR-0001') and the OR focal sends it from the "
                "drafts queue. Nothing was sent."
            ),
            LinkMessage(label="Open the drafts queue", href="/drafts"),
        ]
    if intent == "delete_data":
        return [
            _text(
                "I can't delete or clear anything - Orion has no delete function and records are "
                "kept for the audit trail. Nothing was changed."
            )
        ]
    if intent == "change_config":
        return [
            _text(
                "I can't change configuration (project types, portfolios, checklists, users or "
                "permissions). The Playbook admin does that in the Admin screen. Nothing was changed."
            ),
            LinkMessage(label="Open Admin", href="/admin"),
        ]
    return [
        _text(
            "I can't act with someone else's permissions or skip the rules. Everything I propose is "
            "accepted by a person who holds the permission themselves. Nothing was changed."
        )
    ]


def _labels(options: list[dict[str, str]]) -> str:
    return ", ".join(o["label"] for o in options[:5])


def handle_commands(
    db: Session, user: User, message: str, context: ChatContext, *, source: InputSource = "chat"
) -> ChatOut | None:
    """Free-text command flow, called by ``orion_chat.handle_chat`` AFTER the read-only keyword
    intents did not match (and by POST /orion/extract when the text is not a transition description).

    1. ``AIService.parse_command(message, INTENT_CATALOG, vocab, context)`` -> up to
       ``MAX_COMMANDS_PER_MESSAGE`` commands (extra ones are ignored with a text note).
       ``context`` = {transition_id, item_id, today (``app.clock.today`` ISO), role}.
    2. Per command, resolve the transition (explicit id/name > ``context.transition_id``; several
       matches -> text asking which with candidate ids; none -> text "not found"), then by ``result``:
       message/form/link intents -> same handler as the matching quick action; proposal intents ->
       build the kind's payload; refusal intents -> the refusal text + ``link`` where useful.
    3. Returns None when no command matched (the caller answers with the fallback text).
    Writes only OrionProposal / OrionDraft rows (BR-050, NFR-04)."""
    from app.domain import orion_chat  # late import: orion_chat imports this module

    vocab = build_vocabulary(db)
    ctx = {
        "transition_id": context.transition_id,
        "item_id": context.item_id,
        "today": clock.today().isoformat(),
        "role": user.role,
    }
    commands = get_ai_service().parse_command(message, INTENT_CATALOG, vocab, ctx)
    commands = [c for c in commands if c["intent"] in CATALOG_BY_INTENT]
    if not commands:
        return None
    messages: list[Any] = []
    for cmd in commands[:MAX_COMMANDS_PER_MESSAGE]:
        messages.extend(
            _run_command(db, user, dict(cmd), vocab, context, source, orion_chat, message)
        )
    if len(commands) > MAX_COMMANDS_PER_MESSAGE:
        messages.append(
            _text(
                f"I handled the first {MAX_COMMANDS_PER_MESSAGE} requests and ignored the rest - "
                "send them again in a new message."
            )
        )
    return ChatOut(messages=messages)


def _transition_picker_form(
    db: Session,
    user: User,
    intent: str,
    args: dict[str, Any],
    context: ChatContext,
    orion_chat: Any,
) -> list[Any]:
    """Form-first (spec 8.15): without a transition, a chase / reminder / readiness request gets the
    existing quick-action form with its transition picker instead of a plain-text question. A chaser
    uses the "Draft owner reminders" form. Other intents have no matching form (empty list)."""
    quick = _QUICK_ACTION_OF.get(intent) or (
        "draft_owner_reminders" if intent == "draft_chaser" else None
    )
    if quick is None or quick == "create_leadership_update":
        return []
    items = [i for i in args.get("item_ids", []) if i]
    intro = (
        f"Which transition is {', '.join(items)} on? Pick it and I will draft the reminders for "
        "its owners - nothing is sent until you do."
        if items and intent == "draft_chaser"
        else "Which transition is this for? Pick it below."
    )
    form = orion_chat.quick_action_form(db, user, quick, None, defaults={})
    return [_text(intro), *form.messages]


def _run_command(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    vocab: dict[str, Any],
    context: ChatContext,
    source: InputSource,
    orion_chat: Any,
    full_message: str,
) -> list[Any]:
    intent = cmd["intent"]
    spec = CATALOG_BY_INTENT[intent]
    args: dict[str, Any] = dict(cmd.get("arguments", {}))
    if spec["result"] == "refusal":
        return _refusal(intent, cmd, context.transition_id)
    if intent == "create_transition":
        text = str(cmd.get("excerpt") or full_message)
        return list(extract_transition_proposal(db, user, text, source=source).messages)

    transition: Transition | None = None
    tid = args.get("transition_id") or context.transition_id
    if cmd.get("ambiguous", {}).get("transition"):
        options = cmd["ambiguous"]["transition"]
        return [_text("Which transition do you mean? " + _labels(options) + ".")]
    if args.get("unknown_transition"):
        return [_text(f"I could not find transition {args['unknown_transition']}.")]
    if tid:
        transition = db.get(Transition, tid)
        if transition is None:
            return [_text(f"I could not find transition {tid}.")]
    if intent in _NEEDS_TRANSITION and transition is None:
        form = _transition_picker_form(db, user, intent, args, context, orion_chat)
        if form:
            return form
        return [
            _text(
                "Which transition is this for? Name it (for example TR-0001) or open it first. "
                f"Your request: \"{str(cmd.get('excerpt', ''))[:120]}\"."
            )
        ]

    if intent in _QUICK_ACTION_OF or intent == "open_module":
        return _quick_action_from_words(db, user, intent, args, transition, context, orion_chat)

    if transition is None:

        raise RuntimeError("transition expected")
    builder = _BUILDERS.get(intent)
    if builder is None:  # pragma: no cover - catalog and builders are kept in sync by a test
        return []
    return builder(db, user, cmd, args, transition, vocab)


def _quick_action_from_words(
    db: Session,
    user: User,
    intent: str,
    args: dict[str, Any],
    transition: Transition | None,
    context: ChatContext,
    orion_chat: Any,
) -> list[Any]:
    form: dict[str, Any] = {}
    if intent == "open_module":
        module = args.get("module")
        if not module or transition is None:
            return [
                _text(
                    "Do you want the OCET or the support model? Tell me which, for example "
                    "'open the OCET for TR-0001'."
                )
            ]
        quick = "create_update_ocet" if module == "ocet" else "create_support_model"
        form = {"transition_id": transition.id}
    elif intent == "create_leadership_update":
        quick = "create_leadership_update"
        scope = args.get("scope")
        if scope:
            form["scope"] = scope
        if args.get("scope_id"):
            form["scope_id"] = args["scope_id"]
        if not (scope == "all" or (scope and form.get("scope_id"))):
            return list(
                orion_chat.quick_action_form(
                    db, user, quick, context.transition_id, defaults=form
                ).messages
            )
    else:
        quick = _QUICK_ACTION_OF[intent]
        if transition is None:
            raise RuntimeError("transition expected")
        form = {"transition_id": transition.id}
        if intent == "assess_gate_readiness":
            form["gate"] = args.get("gate") or transition.current_gate
    try:
        return list(
            orion_chat.run_quick_action(db, user, quick, form, context.transition_id).messages
        )
    except Forbidden as exc:
        return [_text(f"I can't do that for you: {exc.detail}.")]


def _need(missing: list[str], hint: str) -> list[Any]:
    return [_text(f"To do that I still need: {', '.join(missing)}. {hint}")]


def _b_create_action(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    amb = cmd.get("ambiguous", {}).get("owner_user_id")
    if amb:
        return [_text("Which person do you mean? " + _labels(amb) + ".")]
    labels = {"owner_user_id": "an owner", "due_date": "a due date"}
    missing = [labels[m] for m in labels if not args.get(m)]
    if missing:
        return _need(missing, "For example: 'ask Tom to finish the DPIA for S3-019 by Friday'.")
    items = [i for i in args.get("item_ids", []) if i]
    unknown = [i for i in items if _item_row(db, t.id, i) is None]
    if unknown:
        return [
            _text(f"{', '.join(unknown)} is not an item of {t.id}. Check the id and try again.")
        ]
    owner = db.get(User, args["owner_user_id"])
    if owner is None:
        return [_text("I could not find that person.")]
    priorities = vocab["priorities"]
    priority = args["priority"] if args.get("priority") in priorities else _middle(priorities)
    payload = {
        "title": args.get("title") or "Follow up",
        "item_ids": items,
        "owner_user_id": owner.id,
        "due_date": args["due_date"],
        "priority": priority,
    }
    return [
        _proposal_message(
            db,
            user,
            kind="create_action",
            title=f"Create action for {owner.name}: {payload['title']} (due {payload['due_date']})",
            payload=payload,
            transition_id=t.id,
        )
    ]


def _b_draft_chaser(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    items = [i for i in args.get("item_ids", []) if i] or _derive_chaser_items(db, t, args)
    if not items:
        return _need(
            ["the items to chase"],
            "For example: 'chase Asha on S3-019' or 'nudge the owners of the overdue items'.",
        )
    open_ids = {r.playbook_item_id for r in _open_items(db, t)}
    bad = [i for i in items if i not in open_ids]
    if bad:
        return [
            _text(f"{', '.join(bad)} is not an open item of {t.id}, so there is nothing to chase.")
        ]
    return [
        _proposal_message(
            db,
            user,
            kind="draft_chaser",
            title=f"Draft a chaser for {len(items)} item(s) on {t.name}",
            payload={"item_ids": items},
            transition_id=t.id,
        )
    ]


def _b_request_inputs(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    estimate = db.scalars(select(OcetEstimate).where(OcetEstimate.transition_id == t.id)).first()
    versions = sorted(estimate.versions, key=lambda v: v.version, reverse=True) if estimate else []
    if not versions:
        return [_text(f"{t.name} has no OCET yet, so there are no inputs to request.")]
    version = versions[0]
    lines = [
        ln for ln in version.lines if ln.base_amount is None and ln.input_status != "Requested"
    ]
    if not lines:
        return [
            _text(
                f"No OCET input is missing on v{version.version} of {t.name} "
                "(or it was already requested)."
            )
        ]
    return [
        _proposal_message(
            db,
            user,
            kind="request_inputs",
            title=f"Request {len(lines)} missing OCET input(s) for {t.name} (v{version.version})",
            payload={"version_id": version.id, "line_ids": [ln.id for ln in lines]},
            transition_id=t.id,
        )
    ]


def _b_request_exception(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    if not args.get("item_id"):
        return _need(
            ["the item id"],
            "For example: 'we need an exception for S45-006 because the vendor cannot meet it'.",
        )
    row = _item_row(db, t.id, args["item_id"])
    if row is None:
        return [_text(f"{args['item_id']} is not an item of {t.id}.")]
    if row.playbook_item.lens != "Compliance":
        return [
            _text(
                f"Exceptions apply to Compliance items only, and {args['item_id']} is a "
                f"{row.playbook_item.lens} item. Nothing was proposed."
            )
        ]
    text = str(args.get("text") or "").strip()
    if not text:
        return _need(["the reason"], "Say why the exception is needed.")
    return [
        _proposal_message(
            db,
            user,
            kind="request_exception",
            title=f"Request an exception for {args['item_id']} on {t.name}",
            payload={"item_id": args["item_id"], "text": text[:4000]},
            transition_id=t.id,
        )
    ]


def _b_request_approval(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    gate = args.get("gate") or (t.current_gate if t.current_gate in DECISION_GATES else None)
    if not gate:
        return _need(
            ["the gate (AtD or AtO)"],
            f"{t.name} is at {GATE_SHORT.get(t.current_gate, t.current_gate)}, "
            "which is not a decision gate.",
        )
    if gate not in DECISION_GATES:
        return [_text("Approvals are requested for the AtD or AtO decision gates only.")]
    return [
        _proposal_message(
            db,
            user,
            kind="request_approval",
            title=f"Draft the {GATE_SHORT[gate]} approval request for {t.name}",
            payload={"gate": gate},
            transition_id=t.id,
        )
    ]


def _b_accept_applicability(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    decisions = args.get("decisions") or []
    if not decisions:
        return _need(
            ["the item and whether it applies"],
            "For example: 'S3-005 does not apply because there is no card data'.",
        )
    rows = {
        r.id: r
        for r in db.scalars(
            select(PlaybookItem).where(PlaybookItem.id.in_([d["item_id"] for d in decisions]))
        ).all()
    }
    for d in decisions:
        row = rows.get(d["item_id"])
        eligible = (
            row is not None
            and row.active
            and (
                row.source == "COMMON"
                or (row.source == "PORTFOLIO" and row.portfolio == t.portfolio)
            )
        )
        if not eligible:
            return [
                _text(
                    f"{d['item_id']} is not a golden-set or common item of {t.portfolio}, so its "
                    "applicability is not decided in the scope step. Nothing was proposed."
                )
            ]
        locked = (
            bool(row.mandatory)
            if row.source == "PORTFOLIO"
            else (row.mandatory_rule == "always" or (row.mandatory_rule is None and row.mandatory))
        )
        if locked and d["applies"] != "Yes":
            return [_text(f"{d['item_id']} is mandatory and cannot be marked as not applicable.")]
    clean = [
        {
            "item_id": d["item_id"],
            "applies": d["applies"],
            **({"reason": d["reason"]} if d.get("reason") else {}),
        }
        for d in decisions
    ]
    if any(d["applies"] == "No" and not d.get("reason") for d in clean):
        return _need(
            ["the reason"],
            "Not applicable needs a reason, for example '... because there is no card data'.",
        )
    word = {"Yes": "applies", "No": "does not apply", "To confirm": "to confirm"}
    return [
        _proposal_message(
            db,
            user,
            kind="accept_applicability",
            title="Applicability: "
            + "; ".join(f"{d['item_id']} {word[d['applies']]}" for d in clean),
            payload={"decisions": clean},
            transition_id=t.id,
        )
    ]


def _b_update_transition(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    raw = dict(args.get("changes") or {})
    allowed = set(TransitionUpdateIn.model_fields)
    changes: dict[str, Any] = {}
    fields: list[ExtractedField] = []
    for name, value in raw.items():
        if name not in allowed:
            continue
        clean, why = _validate_value(name, value, vocab, t.portfolio)
        if clean is None:
            label = _label(vocab, name)
            return [_text(f"I can't use that value for {label}: {why or 'not recognised'}.")]
        current = getattr(t, name, None)
        if str(current) == str(clean):
            continue
        changes[name] = clean
        fields.append(
            ExtractedField(
                name=name,
                label=_label(vocab, name),
                value=clean,
                display=_display(name, clean, vocab),
                state="found",
                source="text",
                confidence=0.9,
                note="Now: " + str(_display(name, current, vocab) or "empty"),
            )
        )
    if not changes and raw:
        return [_text(f"{t.name} already has those values - nothing to change.")]
    if not changes:
        return [
            _text(
                f"I could not tell what to change on {t.name}. For example: 'move next decision "
                f"date of {t.id} to 5 Dec' or 'make Sofia the OLM on {t.name}'."
            )
        ]
    payload = {
        "transition_id": t.id,
        "changes": changes,
        "fields": [f.model_dump(mode="json") for f in fields],
        "source_excerpt": str(cmd.get("excerpt", ""))[:SOURCE_EXCERPT_CHARS],
    }
    return [
        _proposal_message(
            db,
            user,
            kind="update_transition",
            title=f"Update {t.name}: " + ", ".join(f.label for f in fields),
            payload=payload,
            transition_id=t.id,
        )
    ]


def _b_update_item(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    amb = cmd.get("ambiguous", {}).get("owner_user_id")
    if amb:
        return [_text("Which person do you mean? " + _labels(amb) + ".")]
    if not args.get("item_id"):
        return _need(["the item id"], "For example: 'assign S3-019 to Tom'.")
    row = _item_row(db, t.id, args["item_id"])
    if row is None:
        return [_text(f"{args['item_id']} is not an item of {t.id}.")]
    lens = row.playbook_item.lens
    changes = {
        k: args[k] for k in ("status", "gap_severity", "note", "owner_user_id") if args.get(k)
    }
    if not changes:
        return _need(
            ["what to change"],
            "Owner, a note, a gap severity or a status (for example 'S3-020 is complete').",
        )
    if lens == "Compliance" and ("status" in changes or "gap_severity" in changes):
        return [
            _text(
                f"{args['item_id']} is a Compliance item. Only the IRM sets a compliance status, "
                f"so I won't propose that. I can chase the owner for evidence: say 'chase "
                f"{args['item_id']}'."
            ),
            LinkMessage(
                label="Open the item", href=f"/transitions/{t.id}/assessment?item={args['item_id']}"
            ),
        ]
    if "status" in changes:
        status = changes["status"]
        if status in NA_STATUSES:
            return [
                _text(
                    "Not applicable goes through the scope decision - say "
                    "'S3-005 does not apply because ...'."
                )
            ]
        if status not in vocab["item_statuses"].get(lens, ()):
            return [_text(f"'{status}' is not a status of the {lens} lens.")]
        if status == "Gap" and not (changes.get("gap_severity") and changes.get("note")):
            return _need(
                [f"a gap severity ({_or_list(vocab['severities'])})", "a note"],
                "For example: 'S3-021 is a critical gap, no test environment'.",
            )
    if "gap_severity" in changes and changes["gap_severity"] not in vocab["severities"]:
        return [_text(f"Gap severity must be {_or_list(vocab['severities'])}.")]
    if "owner_user_id" in changes and db.get(User, changes["owner_user_id"]) is None:
        return [_text("I could not find that person.")]
    payload = {
        "transition_id": t.id,
        "item_id": args["item_id"],
        "changes": changes,
        "current": {k: getattr(row, k) for k in changes},
        "source_excerpt": str(cmd.get("excerpt", ""))[:SOURCE_EXCERPT_CHARS],
    }
    parts = []
    for key, value in changes.items():
        shown = _user_display(vocab, str(value)) if key == "owner_user_id" else value
        label = {"owner_user_id": "owner", "gap_severity": "gap severity"}.get(key, key)
        parts.append(f"{label} to {shown}")
    return [
        _proposal_message(
            db,
            user,
            kind="update_item",
            title=f"Update {args['item_id']} on {t.name}: " + ", ".join(parts),
            payload=payload,
            transition_id=t.id,
        )
    ]


def _b_add_evidence(
    db: Session,
    user: User,
    cmd: dict[str, Any],
    args: dict[str, Any],
    t: Transition,
    vocab: dict[str, Any],
) -> list[Any]:
    item_id = args.get("item_id")
    if item_id and _item_row(db, t.id, item_id) is None:
        return [_text(f"{item_id} is not an item of {t.id}.")]
    link_type = cfg.evidence_type_for(db, "url")
    text_type = cfg.evidence_type_for(db, "text")
    if args.get("url"):
        if link_type is None:
            return [_text("No evidence type for links is switched on - ask your Admin.")]
        payload = {
            "transition_id": t.id,
            "item_id": item_id,
            "title": str(args.get("title") or "Evidence link")[:300],
            "type": link_type,
            "url": args["url"],
        }
    elif args.get("text"):
        if text_type is None:
            return [_text("No evidence type for pasted e-mails is switched on - ask your Admin.")]
        payload = {
            "transition_id": t.id,
            "item_id": item_id,
            "title": str(args.get("title") or "Email sign-off")[:300],
            "type": text_type,
            "text": str(args["text"]),
        }
    else:
        return _need(
            ["a link or the sign-off email text"],
            "Paste the link, or paste the email in the Orion panel (Paste an email).",
        )
    return [
        _proposal_message(
            db,
            user,
            kind="add_evidence",
            title=f"Add {payload['type'].lower()} evidence"
            + (f" to {item_id}" if item_id else "")
            + f" on {t.name}",
            payload=payload,
            transition_id=t.id,
        )
    ]


_BUILDERS = {
    "create_action": _b_create_action,
    "draft_chaser": _b_draft_chaser,
    "request_inputs": _b_request_inputs,
    "request_exception": _b_request_exception,
    "request_approval": _b_request_approval,
    "accept_applicability": _b_accept_applicability,
    "update_transition": _b_update_transition,
    "update_item": _b_update_item,
    "add_evidence": _b_add_evidence,
}


def signoff_evidence_proposal(
    db: Session, user: User, transition: Transition, text: str
) -> ChatOut | None:
    """A pasted sign-off email for a transition -> ``add_evidence`` proposal (verbatim text, status
    Submitted when accepted). None when the text does not look like a sign-off."""
    if not re.search(
        r"\b(?:approve[ds]?|sign(?:ed)?[\s-]?off|agree[ds]?|confirm(?:ed)?|no objection"
        r"|ok to proceed|go ahead)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    subject = re.search(r"^\s*subject\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    text_type = cfg.evidence_type_for(db, "text")
    if text_type is None:
        return None
    title = (
        subject.group(1).strip() if subject else cfg.option_label(db, "evidence_types", text_type)
    )[:300]
    ids = re.findall(r"\b([A-Za-z]{1,6}\d{0,3}-\d{1,4})\b", text)
    item_id = next((i.upper() for i in ids if _item_row(db, transition.id, i.upper())), None)
    payload = {
        "transition_id": transition.id,
        "item_id": item_id,
        "title": title,
        "type": text_type,
        "text": text.strip(),
    }
    return ChatOut(
        messages=[
            _text(
                "This looks like a sign-off email. I can attach it as evidence with your exact "
                "words (status Submitted); a reviewer still has to accept it."
            ),
            _proposal_message(
                db,
                user,
                kind="add_evidence",
                title=f"Add email sign-off evidence on {transition.name}",
                payload=payload,
                transition_id=transition.id,
            ),
        ]
    )


# ---------------------------------------------------------------------------------------------
# Catalog and extract wrappers
# ---------------------------------------------------------------------------------------------
def intent_catalog_for(db: Session, user: User) -> IntentCatalogOut:
    """INTENT_CATALOG projected for the UI with ``allowed`` / ``denied_reason`` from
    ``permissions.has_perm(user.role, Perm(permission))`` and ``DENIAL_REASONS``; ``refusals`` =
    ``REFUSAL_SUMMARY``. Deterministic (examples are the static strings above)."""
    rows = []
    for entry in INTENT_CATALOG:
        permission = entry["permission"]
        allowed, reason = True, None
        if permission:
            perm = Perm(permission)
            allowed = has_perm(user.role, perm) or (
                perm is Perm.UPDATE_BT_STATUS and has_perm(user.role, Perm.UPDATE_T_STATUS)
            )  # the Architect may propose Technical item updates
            reason = None if allowed else DENIAL_REASONS[perm]
        rows.append(
            IntentSpecOut(
                intent=entry["intent"],
                label=entry["label"],
                examples=list(entry["examples"]),
                result=entry["result"],
                proposal_kind=entry["proposal_kind"],
                permission=permission,
                allowed=allowed,
                denied_reason=reason,
            )
        )
    return IntentCatalogOut(intents=rows, refusals=list(REFUSAL_SUMMARY))


def to_extract_out(
    chat: ChatOut, source: InputSource, source_name: str | None, characters: int, truncated: bool
) -> ExtractOut:
    """Wrap a ``ChatOut`` with the matched intents (derived from its proposal / text messages) and the
    input metadata."""
    intents: list[IntentMatch] = []
    for message in chat.messages:
        if isinstance(message, ProposalMessage):
            p = message.proposal
            confidence = 0.9
            if p.kind == "create_transition":
                fields = p.payload.get("fields", [])
                required = [f for f in fields if f.get("required")]
                got = [f for f in required if f.get("state") in ("found", "inferred")]
                confidence = round(len(got) / len(required), 2) if required else 0.5
            intents.append(IntentMatch(intent=p.kind, confidence=confidence, summary=p.title))
    return ExtractOut(
        messages=chat.messages,
        intents=intents,
        source=source,
        source_name=source_name,
        characters_read=characters,
        truncated=truncated,
    )
