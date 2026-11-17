"""Live transcript stub (spec 10.5)."""

from __future__ import annotations


class LiveTranscriptService:
    def get_text(self, filename: str, content: bytes) -> str:
        """Real call: Azure AI Speech batch transcription for audio/video; text formats are
        parsed locally."""
        raise NotImplementedError("Live transcription is a stub in the MVP")
