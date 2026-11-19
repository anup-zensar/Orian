"""Orion assistant chat (FR-090). Quick actions are FORM-FIRST: the first call returns a ``form``
message; the call that carries ``form_data`` returns the result card(s). Every message is labelled
"Orion agent" (BR-050).

NFR-04: the chat never writes statuses, applicability, tiers, evidence, conditions, approvals or gate
decisions. Its only writes are OrionDraft rows (via the reminder engine, R1/R2), OrionProposal rows
(``domain.proposals.create_proposal``) and LeadershipUpdate rows. When it recommends a change it
returns a ``proposal`` message that a permitted human accepts.

Behaviour by intent (spec 8.15):

* ``start_gate_review``: ``link`` to /transitions/new + short ``text`` (no form).
* ``assess_gate_readiness``: form fields ``transition_id`` (kind transition, default = context
  transition) and ``gate`` (kind gate, options = valid gate codes, default = its current gate); with
  form_data -> ``readiness`` message (``compute_readiness_check``) + short text.
* ``track_owner_actions``: form ``transition_id``; then ``table`` "Open actions and items by owner"
  columns owner, open_actions, open_items, overdue, next_due; rows overdue first (overdue desc, then
  owner name); footnote with totals.
* ``draft_owner_reminders``: form ``transition_id``; then run
  ``run_reminders(db, rules=["R1","R2"], transition_id=...)`` from the reminder engine (drafts only,
  nothing is sent) -> ``drafts`` message listing the drafts (link "/drafts"); when none are due a
  ``text`` says so. Requires Perm.RUN_REMINDERS (403 reason otherwise) when form_data is submitted.
* ``create_leadership_update``: form ``scope`` (all|portfolio|transition) + ``scope_id`` (select,
  required unless all); then ``domain.leadership.generate_update`` (Perm.GENERATE_LEADERSHIP_UPDATE)
  -> ``leadership`` message.
* ``create_support_model``: form ``transition_id`` -> ``link`` /transitions/<id>/support-model.
* ``create_update_ocet``: form ``transition_id`` -> ``link`` /transitions/<id>/ocet.

Free text (case-insensitive; transition matched by id or name substring; several matches -> text
asking which; none -> text saying not found): ``status of <transition>`` -> text + readiness card for
its current gate; ``what is blocking AtD|AtO for <transition>`` -> readiness card for that gate +
text; ``who owns <item id>`` -> text naming the owner (and a link); ``what is OCET|AtD|AtO`` ->
glossary text; ``show red transitions`` -> table (id, name, portfolio, gate, readiness, days);
anything else -> text fallback listing the 7 quick actions and example questions. The footer
"Orion drafts and recommends. You decide." is rendered by the UI, not added as a message.

Natural-language actions (after the keyword intents above did not match; see ``domain/nl_intake.py``):
free text that describes a new transition ("start a gate review for ...", ``PRJ`` ids, several fields
in one sentence) -> ``nl_intake.extract_transition_proposal`` (proposal ``create_transition``); other
requests ("ask Tom to ... by Friday", "assign S3-019 to Tom", "request AtD approval") ->
``nl_intake.handle_commands`` (proposal cards, quick-action results, links or refusals). Order of
routing: (1) read-only keyword intents, (2) create-transition detection (message mentions a PRJ id or
>= 2 intake fields matched by ``AIService.extract_intake`` with "new/start/create/launch" cue),
(3) ``handle_commands``, (4) fallback text. The 2000 character limit of ``ChatIn.message`` stays; long
pasted emails and documents go to POST /orion/extract (limit ``EXTRACT_MAX_CHARS``).

Errors: NotFound 404 for an unknown ``transition_id`` in form_data; BadRequest 400 for a gate not valid
for the transition, or when neither/both of message and quick_action are given.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain import cfg, nl_intake
from app.domain.leadership import generate_update, leadership_out
from app.domain.metrics import compute_metrics
from app.domain.readiness_check import compute_readiness_check
from app.domain.reminders import run_reminders
from app.errors import ApiError, BadRequest, Forbidden, NotFound
from app.models import (
    Action,
    OrionDraft,
    Portfolio,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules.constants import DONE_STATUSES, GATE_ORDER, GATE_SHORT, GATES, NA_STATUSES
from app.schemas.orion import (
    EXTRACT_MAX_CHARS,
    ChatContext,
    ChatIn,
    ChatOut,
    DraftsMessage,
    DraftSummary,
    ExtractOut,
    FormField,
    FormFieldOption,
    FormMessage,
    InputSource,
    LeadershipMessage,
    LinkMessage,
    ReadinessMessage,
    TableColumn,
    TableMessage,
    TextMessage,
)
from app.services.factory import get_ai_service

QUICK_ACTION_TITLES: dict[str, tuple[str, str]] = {
    "assess_gate_readiness": ("Assess gate readiness", "Assess readiness"),
    "track_owner_actions": ("Track owner actions", "Show owner actions"),
    "draft_owner_reminders": ("Draft owner reminders", "Draft reminders"),
    "create_leadership_update": ("Create leadership update", "Generate update"),
    "create_support_model": ("Create support model", "Open support model"),
    "create_update_ocet": ("Create or update the OCET", "Open OCET"),
}
_NEW_TRANSITION_CUE = re.compile(
    r"\b(?:new|start|create|launch|kick[\s-]?off|set\s+up|onboard|begin)\b", re.IGNORECASE
)
_NOT_NEW_CUE = re.compile(
    r"\b(?:action|task|remind|chase|nudge|evidence|exception|owner|assign)\b|\b[A-Za-z]{1,6}\d{0,3}-\d{1,4}\b",
    re.IGNORECASE,
)
_EMAIL_HEADER = re.compile(r"^\s*(?:from|subject|to)\s*:", re.IGNORECASE)


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------
def _text(text: str) -> TextMessage:
    return TextMessage(text=text)


def resolve_transition(db: Session, text: str) -> list[str]:
    """Transition ids whose id equals ``text`` or whose name contains it (case-insensitive)."""
    wanted = " ".join((text or "").split()).strip(" ?.!\"'").lower()
    wanted = re.sub(r"^(?:the|our|my)\s+", "", wanted)
    if not wanted:
        return []
    rows = db.scalars(select(Transition).order_by(Transition.id)).all()
    exact = [t.id for t in rows if t.id.lower() == wanted]
    if exact:
        return exact
    return [t.id for t in rows if wanted in t.name.lower()]


def _get_transition(db: Session, transition_id: str) -> Transition:
    t = db.get(Transition, transition_id)
    if t is None:
        raise NotFound(f"Transition {transition_id} not found")
    return t


def _transition_options(db: Session) -> list[FormFieldOption]:
    rows = db.scalars(select(Transition).order_by(Transition.id)).all()
    return [FormFieldOption(value=t.id, label=f"{t.name} ({t.id})") for t in rows]


def _gate_options() -> list[FormFieldOption]:
    return [FormFieldOption(value=code, label=GATE_SHORT[code]) for code in GATES]


def _scope_id_options(db: Session) -> list[FormFieldOption]:
    portfolios = db.scalars(select(Portfolio).order_by(Portfolio.name)).all()
    out = [FormFieldOption(value=p.name, label=f"Portfolio - {p.name}") for p in portfolios]
    out += [
        FormFieldOption(value=o.value, label=f"Transition - {o.label}")
        for o in _transition_options(db)
    ]
    return out


# ---------------------------------------------------------------------------------------------
# Quick actions: form first, then the result cards
# ---------------------------------------------------------------------------------------------
def quick_action_form(
    db: Session,
    user: User,
    quick_action: str,
    context_transition_id: str | None,
    defaults: dict[str, Any] | None = None,
) -> ChatOut:
    """Form message for a quick action with defaults from the context transition (None -> none).
    ``defaults`` (found by the natural-language flow) override the context defaults."""
    defaults = defaults or {}
    if quick_action == "start_gate_review":
        return ChatOut(
            messages=[
                _text(
                    "Let's start a gate review. Open the intake form - you can fetch the project "
                    "from ServiceNow or describe it to me and I will pre-fill it."
                ),
                LinkMessage(
                    label="Start gate review",
                    href="/transitions/new",
                    description="Opens the new transition form",
                ),
            ]
        )
    title, submit = QUICK_ACTION_TITLES[quick_action]
    tid = defaults.get("transition_id") or context_transition_id
    transition = db.get(Transition, tid) if tid else None
    tid_default = transition.id if transition else None
    fields: list[FormField] = []
    if quick_action == "create_leadership_update":
        fields = [
            FormField(
                name="scope",
                label="Scope",
                kind="scope",
                options=[
                    FormFieldOption(value="all", label="All transitions"),
                    FormFieldOption(value="portfolio", label="One portfolio"),
                    FormFieldOption(value="transition", label="One transition"),
                ],
                default=defaults.get("scope") or ("transition" if tid_default else "all"),
            ),
            FormField(
                name="scope_id",
                label="Portfolio or transition",
                kind="select",
                options=_scope_id_options(db),
                required=False,
                default=defaults.get("scope_id") or tid_default,
            ),
        ]
    else:
        fields.append(
            FormField(
                name="transition_id",
                label="Transition",
                kind="transition",
                options=_transition_options(db),
                default=tid_default,
            )
        )
        if quick_action == "assess_gate_readiness":
            fields.append(
                FormField(
                    name="gate",
                    label="Gate",
                    kind="gate",
                    options=_gate_options(),
                    default=defaults.get("gate")
                    or (transition.current_gate if transition else None),
                )
            )
    return ChatOut(
        messages=[
            FormMessage(
                form_id=quick_action,
                title=title,
                fields=fields,
                submit_label=submit,
                quick_action=quick_action,  # type: ignore[arg-type]
            )
        ]
    )


def _readiness_messages(db: Session, user: User, t: Transition, gate: str) -> list[Any]:
    if t.assessment_launched_at is None:
        return [
            _text(
                f"The assessment of {t.name} has not been launched yet, so there is nothing to "
                "assess. Confirm scope and launch it first."
            ),
            LinkMessage(label="Open scope", href=f"/transitions/{t.id}/scope"),
        ]
    check = compute_readiness_check(db, t, gate, user)
    blockers = sum(len(g.items) for g in check.blocking)
    text = f"{t.name} - {check.verdict_label}."
    if blockers or check.critical_gaps:
        text += f" {blockers} blocking item(s), {len(check.critical_gaps)} critical gap(s)."
    return [ReadinessMessage(check=check), _text(text)]


def _owner_table(db: Session, t: Transition) -> TableMessage:
    today = clock.today()
    users = {u.id: u.name for u in db.scalars(select(User)).all()}
    rows: dict[str, dict[str, Any]] = {}

    def row_for(owner_id: str | None) -> dict[str, Any]:
        key = owner_id or ""
        return rows.setdefault(
            key,
            {
                "owner": users.get(owner_id or "", "Unassigned"),
                "open_actions": 0,
                "open_items": 0,
                "overdue": 0,
                "next_due": None,
            },
        )

    for a in db.scalars(
        select(Action).where(
            Action.transition_id == t.id, Action.status.in_(("Open", "In progress"))
        )
    ).all():
        r = row_for(a.owner_user_id)
        r["open_actions"] += 1
        if a.due_date is not None:
            if a.due_date < today:
                r["overdue"] += 1
            due = a.due_date.isoformat()
            if r["next_due"] is None or due < r["next_due"]:
                r["next_due"] = due
    current = GATE_ORDER.get(t.current_gate, 0)
    for i in db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == t.id, TransitionItem.applicability == "Applies"
        )
    ).all():
        if i.status in DONE_STATUSES or i.status in NA_STATUSES:
            continue
        if GATE_ORDER.get(i.due_gate, 0) > current:
            continue
        r = row_for(i.owner_user_id)
        r["open_items"] += 1
        if GATE_ORDER.get(i.due_gate, 0) < current:
            r["overdue"] += 1
    ordered = sorted(rows.values(), key=lambda r: (-r["overdue"], r["owner"]))
    for r in ordered:
        r["next_due"] = r["next_due"] or "-"
    total_actions = sum(r["open_actions"] for r in ordered)
    total_items = sum(r["open_items"] for r in ordered)
    return TableMessage(
        title=f"Open actions and items by owner - {t.name}",
        columns=[
            TableColumn(key="owner", label="Owner"),
            TableColumn(key="open_actions", label="Open actions"),
            TableColumn(key="open_items", label="Open items"),
            TableColumn(key="overdue", label="Overdue"),
            TableColumn(key="next_due", label="Next due"),
        ],
        rows=ordered,
        footnote=f"{total_actions} open action(s), {total_items} open item(s) at or before "
        f"{GATE_SHORT.get(t.current_gate, t.current_gate)}.",
    )


def run_quick_action(
    db: Session,
    user: User,
    quick_action: str,
    form_data: dict[str, Any],
    context_transition_id: str | None,
) -> ChatOut:
    """The result cards of a quick action whose form was submitted (``form_data``)."""
    if quick_action == "start_gate_review":
        return quick_action_form(db, user, quick_action, context_transition_id)
    if quick_action == "create_leadership_update":
        if not has_perm(user.role, Perm.GENERATE_LEADERSHIP_UPDATE):
            raise Forbidden(DENIAL_REASONS[Perm.GENERATE_LEADERSHIP_UPDATE])
        scope = str(form_data.get("scope") or "all")
        if scope not in ("all", "portfolio", "transition"):
            raise BadRequest("Unknown scope", ["scope must be all, portfolio or transition"])
        scope_id = form_data.get("scope_id") or None
        row = generate_update(db, user, scope, None if scope == "all" else scope_id)  # type: ignore[arg-type]
        return ChatOut(
            messages=[
                LeadershipMessage(update=leadership_out(db, row)),
                _text("Here is the draft. Review it, then send it from Leadership updates."),
            ]
        )
    tid = form_data.get("transition_id") or context_transition_id
    if not tid:
        raise BadRequest("Pick a transition", ["transition_id is required"])
    t = _get_transition(db, str(tid))
    if quick_action == "assess_gate_readiness":
        gate = str(form_data.get("gate") or t.current_gate)
        if gate not in GATE_ORDER:
            raise ApiError(f"Unknown gate '{gate}'", [f"Valid gates: {', '.join(GATES)}"])
        return ChatOut(messages=_readiness_messages(db, user, t, gate))
    if quick_action == "track_owner_actions":
        return ChatOut(messages=[_owner_table(db, t)])
    if quick_action == "draft_owner_reminders":
        if not has_perm(user.role, Perm.RUN_REMINDERS):
            raise Forbidden(DENIAL_REASONS[Perm.RUN_REMINDERS])
        run = run_reminders(db, user=user, rules=["R1", "R2"], transition_id=t.id)
        drafts = [db.get(OrionDraft, i) for i in run.drafts]
        summaries = [
            DraftSummary(
                id=d.id,
                kind=d.kind,
                subject=d.subject,
                to=list(d.to),
                transition_id=d.transition_id,
            )
            for d in drafts
            if d is not None
        ]
        if not summaries:
            return ChatOut(
                messages=[
                    _text(
                        f"Nothing is due for a reminder on {t.name} right now (or the reminders "
                        "were already drafted today)."
                    ),
                    LinkMessage(label="Open the drafts queue", href="/drafts"),
                ]
            )
        return ChatOut(
            messages=[
                DraftsMessage(title=f"Reminder drafts for {t.name}", drafts=summaries),
                _text("Nothing was sent. Review the drafts in the queue, then send them."),
            ]
        )
    if quick_action == "create_support_model":
        return ChatOut(
            messages=[
                LinkMessage(
                    label="Open the support model",
                    href=f"/transitions/{t.id}/support-model",
                    description=t.name,
                )
            ]
        )
    if quick_action == "create_update_ocet":
        return ChatOut(
            messages=[
                LinkMessage(
                    label="Open the OCET", href=f"/transitions/{t.id}/ocet", description=t.name
                )
            ]
        )
    raise BadRequest("Unknown quick action", [quick_action])


# ---------------------------------------------------------------------------------------------
# Free text
# ---------------------------------------------------------------------------------------------
def _pick_transition(
    db: Session, query: str, context_tid: str | None
) -> tuple[Transition | None, list[Any]]:
    """(transition, messages): messages are set when the transition could not be resolved."""
    query = (query or "").strip()
    if not query and context_tid:
        query = context_tid
    ids = resolve_transition(db, query)
    if not ids:
        return None, [_text(f"I could not find a transition matching '{query}'.")]
    if len(ids) > 1:
        names = {t.id: t.name for t in db.scalars(select(Transition).where(Transition.id.in_(ids)))}
        listing = ", ".join(f"{names[i]} ({i})" for i in ids[:6])
        return None, [
            _text(f"Several transitions match '{query}': {listing}. Which one do you mean?")
        ]
    return _get_transition(db, ids[0]), []


def _gate_code(db: Session, words: str) -> str | None:
    from app.domain.tiering import reference

    wanted = " ".join((words or "").lower().split())
    for g in reference(db).get("gates", []):
        if wanted and wanted in (g["code"].lower(), g.get("short", "").lower()):
            return str(g["code"])
    return None


def _owner_answer(db: Session, item_id: str, context_tid: str | None) -> list[Any]:
    query = select(TransitionItem).where(TransitionItem.playbook_item_id == item_id)
    if context_tid:
        query = query.where(TransitionItem.transition_id == context_tid)
    rows = db.scalars(query.order_by(TransitionItem.transition_id)).all()
    if not rows:
        return [
            _text(
                f"I could not find item {item_id}" + (f" in {context_tid}." if context_tid else ".")
            )
        ]
    users = {u.id: u for u in db.scalars(select(User)).all()}
    names = {t.id: t.name for t in db.scalars(select(Transition)).all()}
    title = rows[0].playbook_item.title
    messages: list[Any] = []
    for r in rows[:6]:
        owner = users.get(r.owner_user_id or "")
        where = f"{names.get(r.transition_id, r.transition_id)} ({r.transition_id})"
        if owner:
            text = f"{item_id} {title} is owned by {owner.name} ({cfg.role_short_label(db, owner.role)}) on {where}"
        else:
            text = f"{item_id} {title} has no owner yet on {where}"
        messages.append(_text(text))
    if len(rows) > 6:
        messages.append(_text(f"(+{len(rows) - 6} more transitions)"))
    first = rows[0]
    messages.append(
        LinkMessage(
            label=f"Open {item_id}",
            href=f"/transitions/{first.transition_id}/assessment?item={item_id}",
        )
    )
    return messages


def _red_table(db: Session) -> list[Any]:
    transitions = list(
        db.scalars(
            select(Transition).where(Transition.status == "Active").order_by(Transition.id)
        ).all()
    )
    red = [m for m in compute_metrics(db, transitions) if m.rag == "Red"]
    red.sort(
        key=lambda m: (
            m.days_to_next_decision if m.days_to_next_decision is not None else 10**6,
            m.id,
        )
    )
    if not red:
        return [_text("No transition is Red right now.")]
    rows = [
        {
            "id": m.id,
            "name": m.transition.name,
            "portfolio": m.transition.portfolio,
            "gate": GATE_SHORT.get(m.transition.current_gate, m.transition.current_gate),
            "readiness": f"{m.readiness.overall}%",
            "days": "-" if m.days_to_next_decision is None else m.days_to_next_decision,
        }
        for m in red
    ]
    return [
        TableMessage(
            title="Red transitions",
            columns=[
                TableColumn(key="id", label="ID"),
                TableColumn(key="name", label="Transition"),
                TableColumn(key="portfolio", label="Portfolio"),
                TableColumn(key="gate", label="Gate"),
                TableColumn(key="readiness", label="Readiness"),
                TableColumn(key="days", label="Days to decision"),
            ],
            rows=rows,
            footnote=f"{len(rows)} Red transition(s), most urgent first.",
        )
    ]


def _looks_like_new_transition(db: Session, message: str) -> bool:
    if re.search(r"\bPRJ\d+\b", message, re.IGNORECASE):
        return True
    if not _NEW_TRANSITION_CUE.search(message) or _NOT_NEW_CUE.search(message):
        return False
    vocab = nl_intake.build_vocabulary(db)
    fields = get_ai_service().extract_intake(message, vocab, None)["fields"]
    hits = sum(
        1
        for name in ("project_type", "portfolio", "region", "name")
        if fields.get(name, {}).get("state") in ("found", "inferred")
    )
    return hits >= 2


def _free_text(db: Session, user: User, message: str, context: ChatContext) -> ChatOut:
    ai = get_ai_service()
    vocab_terms = nl_intake.build_vocabulary(db)["terms"]
    routed = ai.chat(message, {"transition_id": context.transition_id, "terms": vocab_terms})
    intent = routed["intent"]
    entities = routed.get("entities", {})
    if intent == "glossary":
        return ChatOut(messages=[_text(routed["text"])])
    if intent == "status":
        t, problem = _pick_transition(db, entities.get("query", ""), context.transition_id)
        if t is None:
            return ChatOut(messages=problem)
        return ChatOut(messages=_readiness_messages(db, user, t, t.current_gate))
    if intent == "blocking":
        t, problem = _pick_transition(db, entities.get("query", ""), context.transition_id)
        if t is None:
            return ChatOut(messages=problem)
        gate = _gate_code(db, entities.get("gate_short", "")) or t.current_gate
        return ChatOut(messages=_readiness_messages(db, user, t, gate))
    if intent == "owner":
        return ChatOut(messages=_owner_answer(db, entities["item_id"], context.transition_id))
    if intent == "red_transitions":
        return ChatOut(messages=_red_table(db))
    # natural-language actions (CR-02): create a transition from words, then commands
    if _looks_like_new_transition(db, message):
        return nl_intake.extract_transition_proposal(db, user, message, source="chat")
    result = nl_intake.handle_commands(db, user, message, context)
    if result is not None and result.messages:
        return result
    return ChatOut(messages=[_text(routed["text"] or "I did not understand that.")])


def handle_chat(db: Session, user: User, body: ChatIn) -> ChatOut:
    """Route to the quick-action handler or to ``AIService.chat`` (keyword intent router returning
    {"intent", "entities", "text"}; this function turns the intent into messages using live data).
    Commits only the drafts/proposals/updates it creates. Free text that no read-only intent matches
    continues with the natural-language flow described in the module docstring (the mock keeps the
    deterministic order; the live model only replaces the extractors)."""
    if (body.message is None) == (body.quick_action is None):
        raise ApiError(
            "Send either a message or a quick action", ["Exactly one of message / quick_action"]
        )
    if body.quick_action is not None:
        if body.form_data is None:
            out = quick_action_form(db, user, body.quick_action, body.context.transition_id)
        else:
            out = run_quick_action(
                db, user, body.quick_action, body.form_data, body.context.transition_id
            )
    else:
        message = (body.message or "").strip()
        if not message:
            raise ApiError("The message is empty", ["Type something"])
        out = _free_text(db, user, message, body.context)
    db.commit()
    return out


# ---------------------------------------------------------------------------------------------
# Extract (pasted text / documents)
# ---------------------------------------------------------------------------------------------
def handle_extract_full(
    db: Session,
    user: User,
    *,
    text: str | None,
    filename: str | None,
    content: bytes | None,
    transition_id: str | None,
    intent_hint: str | None,
) -> ExtractOut:
    """Same as ``handle_extract`` but returns the ``ExtractOut`` of POST /orion/extract (cards, matched
    intents, source, characters read, truncated)."""
    has_file = content is not None and bool(filename)
    has_text = text is not None and text.strip() != ""
    if has_file == has_text:
        raise ApiError("Send either text or a file", ["Exactly one of text / file is required"])
    transition = _get_transition(db, transition_id) if transition_id else None
    truncated = False
    source: InputSource
    if has_file:
        if content is None or filename is None:
            raise RuntimeError("file expected")
        body_text, truncated = nl_intake.read_document_text(filename, content)
        source, source_name = "document", filename
    else:
        body_text = (text or "").strip()
        if len(body_text) > EXTRACT_MAX_CHARS:
            raise BadRequest("The text is too long", [f"At most {EXTRACT_MAX_CHARS} characters"])
        source = "email" if _EMAIL_HEADER.match(body_text) else "text"
        source_name = None
    mode = intent_hint or ("commands" if transition is not None else "create_transition")
    if mode == "commands" and transition is None:
        mode = "create_transition"
    chat: ChatOut | None = None
    if mode == "create_transition":
        chat = nl_intake.extract_transition_proposal(
            db, user, body_text, source=source, source_name=source_name
        )
    else:
        if transition is None:
            raise RuntimeError("transition expected")
        if source in ("email", "document", "text"):
            chat = nl_intake.signoff_evidence_proposal(db, user, transition, body_text)
        if chat is None:
            chat = nl_intake.handle_commands(
                db, user, body_text, ChatContext(transition_id=transition.id), source=source
            )
        if chat is None:
            chat = ChatOut(
                messages=[
                    _text(
                        "I could not find anything to do in that text. Try one request per line, "
                        "for example 'ask Tom to finish the DPIA by Friday'."
                    )
                ]
            )
    db.commit()
    return nl_intake.to_extract_out(chat, source, source_name, len(body_text), truncated)


def handle_extract(
    db: Session,
    user: User,
    *,
    text: str | None,
    filename: str | None,
    content: bytes | None,
    transition_id: str | None,
    intent_hint: str | None,
) -> ChatOut:
    """Body of POST /orion/extract (cards only; the router uses ``handle_extract_full``).
    Source = ``email`` when the text starts with a header line (From:/Subject:/To:), ``document`` when a
    file was uploaded, else ``text``. Without ``transition_id`` (or hint create_transition) the text is a
    NEW TRANSITION description; with a ``transition_id`` (or hint commands) it is read as commands /
    evidence for that transition (a pasted sign-off email -> ``add_evidence`` proposal, meeting notes ->
    several ``create_action`` proposals). When the flow produced no proposal the answer is text."""
    out = handle_extract_full(
        db,
        user,
        text=text,
        filename=filename,
        content=content,
        transition_id=transition_id,
        intent_hint=intent_hint,
    )
    return ChatOut(messages=out.messages)
