"""Service interfaces (spec §10, NFR-01).

Every external system and every AI capability is a ``Protocol`` here, implemented by a deterministic
mock in ``services/mock/`` (default) and a documented stub in ``services/live/``. Routers and domain
code obtain implementations only through ``services/factory.py``, so swapping mock ↔ live never
touches the UI or business logic.

Mock conventions (spec §10): deterministic (same input → same output), small artificial delay
(``MOCK_DELAY_MS``), and one log line per call: ``[MOCK <Service>] <operation> <key params>``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, TypedDict


class DraftText(TypedDict):
    subject: str
    body_html: str


class SavedDocument(TypedDict):
    url: str  # fake SharePoint URL https://sharepoint.example/sites/orion/<transition>/<file>
    path: str  # storage path relative to STORAGE_DIR (POSIX separators)
    filename: str
    size: int


class ConfluencePage(TypedDict):
    title: str
    summary: str
    diagrams: list[str]
    url: str


class IntakeExtraction(TypedDict):
    """Result of ``AIService.extract_intake`` (no DB access; matching is done against ``vocab``).

    ``fields`` maps an intake field name (a ``TransitionCreateIn`` key, plus ``sites`` and the
    ``*_user_id`` role pickers) to {"value", "state" (found|inferred|ambiguous|missing), "source",
    "confidence" (0..1), "evidence" (quoted excerpt), "candidates" ([{"value","label"}]), "note"}.
    Only values that exist in ``vocab`` are returned (ids of users, exact option labels, exact
    project type / portfolio / region names) - never invented ones.
    """

    fields: dict[str, dict[str, Any]]
    servicenow_project_id: str | None
    summary: str  # one short sentence, e.g. "Found 7 of 9 intake fields"


class ParsedCommand(TypedDict):
    """One command found in a free-text message by ``AIService.parse_command``.

    ``intent`` is a key of ``domain.nl_intake.INTENT_CATALOG``; ``arguments`` holds raw, vocabulary
    matched arguments (ids already resolved, e.g. {"owner_user_id": "U13", "item_ids": ["S3-019"],
    "due_date": "2026-11-20"}); ``missing`` lists required argument names not found; ``ambiguous``
    maps an argument name to candidate options; ``confidence`` is 0..1; ``excerpt`` is the part of the
    message the command came from.
    """

    intent: str
    arguments: dict[str, Any]
    missing: list[str]
    ambiguous: dict[str, list[dict[str, str]]]
    confidence: float
    excerpt: str


class AIService(Protocol):
    """Orion agent (spec §10.1). Produces text and recommendations only – never decisions (BR-050)."""

    def readiness_narrative(self, ctx: Mapping[str, Any]) -> str:
        """3–5 sentence readiness assessment for a gate from computed facts (FR-050)."""
        ...

    def recommend_actions(self, gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Per gap/blocker: proposed action, owner, due date, chaser hint (FR-032, FR-050)."""
        ...

    def recommend_applicability(
        self, items: Sequence[Mapping[str, Any]], flavour: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """For "To confirm" golden-set rows: {item_id, recommendation: Yes|No, reason} (FR-022)."""
        ...

    def draft_message(self, kind: str, ctx: Mapping[str, Any]) -> DraftText:
        """Chaser / Reminder / Input request / Approval request / Leadership update text."""
        ...

    def leadership_update(self, scope_data: Mapping[str, Any]) -> str:
        """Markdown leadership update from live data (FR-080)."""
        ...

    def explain_ocet_change(self, diff: Mapping[str, Any]) -> str:
        """Plain-words explanation of an OCET version change (FR-060)."""
        ...

    def chat(self, message: str, context: Mapping[str, Any]) -> dict[str, Any]:
        """Keyword intent routing for free text (FR-090): {"intent": str, "entities": {...}, "text": str}."""
        ...

    def insights(self, scope_data: Mapping[str, Any]) -> list[dict[str, Any]]:
        """3–5 insight bullets with suggested action buttons (FR-010, FR-011)."""
        ...

    def extract_intake(
        self, text: str, vocab: Mapping[str, Any], servicenow: Mapping[str, Any] | None = None
    ) -> IntakeExtraction:
        """Plain language / pasted email / document text -> intake fields (spec 8.4, FR-090).
        ``vocab`` is built at runtime from the database by ``domain.nl_intake.build_vocabulary``
        (project types, portfolios, regions, option lists, users with roles, flags such as
        requires_sites / requires_tiering) - implementations must NOT carry hard-coded lists.
        ``servicenow`` is the already looked-up record for a PRJ id found in the text (or None).
        Read-only and side-effect free (BR-050)."""
        ...

    def parse_command(
        self,
        message: str,
        catalog: Sequence[Mapping[str, Any]],
        vocab: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> list[ParsedCommand]:
        """Free text -> 0..5 commands drawn from ``catalog`` (intent keys, examples and argument
        names of ``domain.nl_intake.INTENT_CATALOG``), arguments resolved against ``vocab``.
        ``context`` carries transition_id, item_id, today (ISO) and the user's role. Never returns an
        intent that is not in the catalog; unknown requests return []. Side-effect free (BR-050)."""
        ...


class MailService(Protocol):
    """Microsoft Graph mail (spec §10.2)."""

    def send_mail(
        self,
        from_mailbox: str,
        to: Sequence[str],
        cc: Sequence[str],
        subject: str,
        html_body: str,
        related_ids: Sequence[str] = (),
    ) -> int:
        """Send (mock: write an OutboxMessage, channel Email). Returns the outbox message id."""
        ...


class NotificationService(Protocol):
    """In-app notifications + Teams (spec §10.3)."""

    def notify(self, user_ids: Sequence[str], text: str, link: str) -> list[int]:
        """Create in-app (bell) notifications; returns their ids."""
        ...

    def post_teams_card(
        self,
        user_ids: Sequence[str],
        card_json: Mapping[str, Any],
        summary: str,
        related_ids: Sequence[str] = (),
    ) -> int:
        """Post an Adaptive Card (mock: OutboxMessage, channel Teams). Returns the outbox id."""
        ...


class ServiceNowService(Protocol):
    """ServiceNow project lookup (spec §10.5)."""

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Project record (name, project_type, investment_type, delivery_method, portfolio, region,
        market, pm, description) or ``None`` when not found."""
        ...


class DocumentStore(Protocol):
    """SharePoint document library (spec §10.5)."""

    def save(self, transition_id: str, filename: str, content: bytes) -> SavedDocument:
        """Store a file for a transition; returns fake SharePoint URL + local storage path."""
        ...

    def read(self, path: str) -> bytes:
        """Read a stored file by the storage path returned from ``save``."""
        ...


class ConfluenceService(Protocol):
    """Confluence / Atlassian solution pages (spec §10.5)."""

    def fetch(self, url: str) -> ConfluencePage:
        """Title + summary of the page (mock: first seed page whose ``url_contains`` matches)."""
        ...


class TranscriptService(Protocol):
    """Walkthrough transcripts (spec §10.5)."""

    def get_text(self, filename: str, content: bytes) -> str:
        """Text of a .vtt/.txt/.docx transcript; audio/video → canned transcript (mock)."""
        ...


class SupportModelGenerator(Protocol):
    """Support model landscape generation (spec §10.6.1)."""

    def generate(self, transition: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Landscape JSON (spec §8.8 schema) from transition data + inputs (confluence, files, texts)."""
        ...
