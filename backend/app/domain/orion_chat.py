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

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.orion import ChatIn, ChatOut


def handle_chat(db: Session, user: User, body: ChatIn) -> ChatOut:
    """Route to the quick-action handler or to ``AIService.chat`` (keyword intent router returning
    {"intent", "entities", "text"}; this function turns the intent into messages using live data).
    Commits only the drafts/proposals/updates it creates. Free text that no read-only intent matches
    continues with the natural-language flow described in the module docstring (the mock keeps the
    deterministic order; the live model only replaces the extractors)."""
    raise NotImplementedError("M8")


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
    """Body of POST /orion/extract. Source = ``email`` when the text starts with a header line
    (From:/Subject:/To:), ``document`` when a file was uploaded, else ``text``. Text from a file via
    ``nl_intake.read_document_text``. ``intent_hint`` "create_transition" (default when no
    ``transition_id`` is given and the text is long or a document) goes straight to
    ``nl_intake.extract_transition_proposal``; with a ``transition_id`` (or hint "commands") the text is
    treated as commands / evidence for that transition via ``nl_intake.handle_commands`` (e.g. a pasted
    sign-off email -> ``add_evidence`` proposal, meeting notes -> several ``create_action`` proposals).
    When the flow produced no proposal the answer is the fallback text. Same write rules as
    ``handle_chat``."""
    raise NotImplementedError("M8")


def quick_action_form(
    db: Session, user: User, quick_action: str, context_transition_id: str | None
) -> ChatOut:
    """Form message for a quick action with defaults from the context transition (None -> none)."""
    raise NotImplementedError("M8")


def resolve_transition(db: Session, text: str) -> list[str]:
    """Transition ids whose id equals ``text`` or whose name contains it (case-insensitive)."""
    raise NotImplementedError("M8")
