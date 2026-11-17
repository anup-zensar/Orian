"""Live Confluence stub (spec 10.5)."""

from __future__ import annotations

from app.services.interfaces import ConfluencePage


class LiveConfluenceService:
    def fetch(self, url: str) -> ConfluencePage:
        """Real call: Confluence REST ``GET /wiki/rest/api/content?...`` (resolve the page from
        the URL, then ``expand=body.storage`` for the content to summarise)."""
        raise NotImplementedError("Live Confluence is a stub in the MVP")
