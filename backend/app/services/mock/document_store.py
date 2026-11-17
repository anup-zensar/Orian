"""Mock SharePoint document library on local disk (spec 10.5, PLAN A-24).

Files live under ``STORAGE_DIR/<transition_id>/<safe filename>``. Security rules: the filename is
reduced to a safe basename, transition ids must look like ``TR-0001``, size and extension are
limited, existing files are never overwritten, and ``read`` refuses paths outside STORAGE_DIR.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.config import get_settings
from app.errors import BadRequest, NotFound
from app.services.interfaces import SavedDocument
from app.services.mock._common import log_mock, simulate_latency

ALLOWED_EXTENSIONS = frozenset(
    {
        *(".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".vtt", ".md"),
        *(".csv", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".m4a", ".mp3", ".wav"),
        *(".eml", ".msg", ".json"),
    }
)
SHAREPOINT_BASE = "https://sharepoint.example/sites/orion"
_TRANSITION_RE = re.compile(r"TR-\d{4,}")
_RESERVED_STEMS = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
)
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9 ._-]")
MAX_FILENAME_LEN = 120


def sanitize_filename(filename: str) -> str:
    """Basename only; letters/digits/space/.-_ kept, others become ``_``; max 120; never empty."""
    name = PureWindowsPath(PurePosixPath(filename or "").name).name  # strips / and \ paths
    name = _UNSAFE_RE.sub("_", name).strip(" .")
    if len(name) > MAX_FILENAME_LEN:
        stem, dot, ext = name.rpartition(".")
        if dot and 0 < len(ext) <= 10:
            name = stem[: MAX_FILENAME_LEN - len(ext) - 1] + "." + ext
        else:
            name = name[:MAX_FILENAME_LEN]
    return name or "file"


class MockDocumentStore:
    def _root(self) -> Path:
        return get_settings().storage_dir.resolve()

    def save(self, transition_id: str, filename: str, content: bytes) -> SavedDocument:
        simulate_latency()
        return self._store(transition_id, filename, content)

    def save_generated(self, transition_id: str, filename: str, content: bytes) -> SavedDocument:
        """Store a generated artefact (PPT/XLSX/JSON); same rules as uploads."""
        return self._store(transition_id, filename, content)

    def _store(self, transition_id: str, filename: str, content: bytes) -> SavedDocument:
        if not _TRANSITION_RE.fullmatch(transition_id or ""):
            raise BadRequest("Invalid transition id", [f"'{transition_id}' is not like TR-0001"])
        limit_mb = get_settings().max_upload_mb
        if len(content) > limit_mb * 1024 * 1024:
            raise BadRequest("File too large", [f"Maximum upload size is {limit_mb} MB"])
        safe = sanitize_filename(filename)
        ext = Path(safe).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise BadRequest(
                "File type not allowed",
                [f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"],
            )
        stem = Path(safe).stem
        if safe.split(".", 1)[0].strip().lower() in _RESERVED_STEMS:  # Windows device names
            raise BadRequest("File name not allowed", [f"'{safe}' is a reserved device name"])
        folder = self._root() / transition_id
        try:
            folder.mkdir(parents=True, exist_ok=True)
            stored = safe
            counter = 0
            while True:  # never overwrite: name-1.ext, name-2.ext ... ("xb" creates atomically)
                try:
                    with open(folder / stored, "xb") as handle:
                        handle.write(content)
                    break
                except FileExistsError:
                    counter += 1
                    stored = f"{stem}-{counter}{ext}"
        except OSError:
            raise BadRequest("Could not store the file") from None
        log_mock("DocumentStore", "save", transition=transition_id, file=stored, size=len(content))
        return {
            "url": f"{SHAREPOINT_BASE}/{transition_id}/{stored}",
            "path": f"{transition_id}/{stored}",
            "filename": stored,
            "size": len(content),
        }

    def read(self, path: str) -> bytes:
        simulate_latency()
        root = self._root()
        try:
            target = (root / path).resolve()
        except (OSError, ValueError):
            raise NotFound("File not found") from None
        if not target.is_relative_to(root) or not target.is_file():
            raise NotFound("File not found")
        log_mock("DocumentStore", "read", path=path)
        return target.read_bytes()
