"""Mock transcript extraction (spec 10.5)."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from lxml import etree

from app.services.mock._common import log_mock, simulate_latency

MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
AUDIO_VIDEO = {".mp4", ".m4a", ".mp3", ".wav"}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_TIMESTAMP_RE = re.compile(r"^\s*(\d+:)?\d{2}:\d{2}[.,]\d{3}\s*-->")

CANNED_TRANSCRIPT = (
    "Walkthrough transcript (mock). The project team explains the central app that all markets "
    "use, and its integrations with the supplier platform and internal systems. Users sign in "
    "with SSO. Monitoring and alerting are configured and reviewed by the support team. Support "
    "is organised as L1 service desk triage, L2 application support and L3 vendor engineering, "
    "with escalation contacts agreed for each level."
)


def _vtt_text(raw: str) -> str:
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("WEBVTT") or stripped.isdigit():
            continue
        if _TIMESTAMP_RE.match(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:  # zip-bomb guard
                return ""
            raw = archive.read(info)
        # Uploaded files are untrusted: lxml with entities unresolved, no DTD loading, no network.
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
        )
        root = etree.fromstring(raw, parser)
    except (zipfile.BadZipFile, KeyError, ValueError, etree.XMLSyntaxError):
        return ""
    paragraphs = []
    for para in root.iter(f"{_W}p"):
        text = "".join(node.text or "" for node in para.iter(f"{_W}t"))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


class MockTranscriptService:
    def get_text(self, filename: str, content: bytes) -> str:
        simulate_latency()
        ext = Path(filename or "").suffix.lower()
        log_mock("Transcript", "get_text", filename=filename, size=len(content))
        if ext in (".txt", ".md"):
            return content.decode("utf-8", errors="replace")
        if ext == ".vtt":
            return _vtt_text(content.decode("utf-8", errors="replace"))
        if ext == ".docx":
            return _docx_text(content)
        if ext in AUDIO_VIDEO:
            log_mock("Transcript", "would transcribe with Azure AI Speech", filename=filename)
            return CANNED_TRANSCRIPT
        return ""
