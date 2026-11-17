"""Mock Confluence page fetch (spec 10.5)."""

from __future__ import annotations

from app.services.interfaces import ConfluencePage
from app.services.mock._common import log_mock, simulate_latency
from app.services.mock.servicenow import load_external_seed


class MockConfluenceService:
    def fetch(self, url: str) -> ConfluencePage:
        simulate_latency()
        log_mock("Confluence", "fetch", url=url)
        lowered = (url or "").lower()
        pages = load_external_seed().get("confluence_pages", [])
        # First specific match wins; the entry with empty url_contains is the generic fallback.
        chosen = None
        for page in pages:
            marker = str(page.get("url_contains", "")).lower()
            if marker and marker in lowered:
                chosen = page
                break
        if chosen is None:
            chosen = next((p for p in pages if not p.get("url_contains")), None)
        if chosen is None:
            return {"title": "Solution Design Document", "summary": "", "diagrams": [], "url": url}
        return {
            "title": chosen["title"],
            "summary": chosen["summary"],
            "diagrams": list(chosen.get("diagrams", [])),
            "url": url,
        }
