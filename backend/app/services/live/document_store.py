"""Live SharePoint document store stub (spec 10.5)."""

from __future__ import annotations

from app.services.interfaces import SavedDocument


class LiveDocumentStore:
    def save(self, transition_id: str, filename: str, content: bytes) -> SavedDocument:
        """Real call: Graph drive item upload
        ``PUT /sites/{site-id}/drive/items/{parent-id}:/{filename}:/content``."""
        raise NotImplementedError("Live SharePoint is a stub in the MVP")

    def read(self, path: str) -> bytes:
        """Real call: Graph ``GET /sites/{site-id}/drive/items/{item-id}/content``."""
        raise NotImplementedError("Live SharePoint is a stub in the MVP")
