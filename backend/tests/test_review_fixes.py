"""Regression tests for the M1 review: document store (B6), docx XML (B7), reassemble (B8), seed (B9)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from app.config import get_settings
from app.errors import BadRequest
from app.rules.checklist import (
    ExistingItem,
    LibraryItem,
    TransitionRoles,
    assemble_checklist,
    reassemble,
)
from app.seed import loader
from app.services.mock.document_store import MockDocumentStore
from app.services.mock.transcript import MockTranscriptService

ROLES = TransitionRoles(or_focal="U01", pm="U10", architect="U11", olm="U12", irm="U14")
FRAMEWORK_ONLY = ["FRAMEWORK"]
WITH_AI = ["FRAMEWORK", "AI_PLAYBOOK"]


# --- B6 ----------------------------------------------------------------------------------------


def test_document_store_rejects_newline_id_and_accepts_long_ids():
    store = MockDocumentStore()
    with pytest.raises(BadRequest):
        store.save("TR-0001\n", "a.txt", b"x")
    assert store.save("TR-10000", "long-id.txt", b"x")["path"] == "TR-10000/long-id.txt"


@pytest.mark.parametrize("name", ["CON.txt", "nul.pdf", "COM1.csv", "lpt9.txt", "Aux.md"])
def test_document_store_rejects_windows_device_names(name):
    with pytest.raises(BadRequest):
        MockDocumentStore().save("TR-0001", name, b"x")


def test_document_store_same_name_twice_makes_two_files():
    store = MockDocumentStore()
    one = store.save("TR-0003", "same.txt", b"1")
    two = store.save("TR-0003", "same.txt", b"2")
    assert one["filename"] != two["filename"]
    assert store.read(one["path"]) == b"1"
    assert store.read(two["path"]) == b"2"


def test_document_store_os_error_becomes_bad_request(monkeypatch):
    def boom(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("app.services.mock.document_store.open", boom, raising=False)
    with pytest.raises(BadRequest, match="Could not store the file"):
        MockDocumentStore().save("TR-0004", "x.txt", b"x")


# --- B7 ----------------------------------------------------------------------------------------


def test_transcript_docx_entity_is_not_expanded_utf16():
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<!DOCTYPE w:document [<!ENTITY secret "LEAKED">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Hi &secret;</w:t></w:r></w:p></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", xml.encode("utf-16"))
    text = MockTranscriptService().get_text("t.docx", buf.getvalue())
    assert "LEAKED" not in text


# --- B8 ----------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def library() -> list[LibraryItem]:
    seed_dir = Path(get_settings().seed_dir)
    rows = loader._library_rows(
        loader._read(seed_dir, "framework_activities.json"),
        loader._read(seed_dir, "ai_playbook_items.json"),
        loader._read(seed_dir, "portfolios.json"),
    )
    return [loader._to_library_item(r) for r in rows]


def _assemble(library, project_type, portfolio="GCC", tier=None, checklists=FRAMEWORK_ONLY):
    return assemble_checklist(library, project_type, portfolio, tier, checklists, ROLES)


def _existing(planned):
    return [
        ExistingItem(p.playbook_item_id, p.applicability, p.excluded_by, "In progress")
        for p in planned
    ]


def test_reassemble_project_type_change_excludes_dropped_ai_items(library):
    ai = _assemble(library, "Agentic AI", tier=2, checklists=WITH_AI)
    normal = _assemble(library, "Normal")
    result = reassemble(_existing(ai), normal, library)
    ai_applicable = {
        p.playbook_item_id
        for p in ai
        if p.source == "AI_PLAYBOOK" and p.applicability != "Not applicable"
    }
    assert len(ai_applicable) == 208
    assert {c.playbook_item_id for c in result.changes} == ai_applicable
    assert result.counts["excluded"] == 208
    for change in result.changes:
        assert change.change == "excluded" and change.excluded_by == "project_type"
        assert change.applicability == "Not applicable"
        assert change.status in {"N/A", "Not applicable"}


def test_reassemble_portfolio_change_excludes_old_golden_set_and_adds_new(library):
    gcc = _assemble(library, "Normal", "GCC")
    fleets = _assemble(library, "Normal", "Fleets")
    result = reassemble(_existing(gcc), fleets, library)
    excluded = [c for c in result.changes if c.change == "excluded"]
    added = [c for c in result.changes if c.change == "added"]
    assert excluded
    assert all(c.playbook_item_id.startswith("GCC-") for c in excluded)
    assert {c.excluded_by for c in excluded} == {"portfolio"}
    assert added
    assert all(c.playbook_item_id.startswith("FLT-") for c in added)
    assert "To confirm" in {c.applicability for c in added}
    assert result.counts["excluded"] == len(excluded)


def test_reassemble_dropped_item_keeps_human_na_and_retired_lines(library):
    gcc = _assemble(library, "Normal", "GCC")
    fleets = _assemble(library, "Normal", "Fleets")
    existing = _existing(gcc)
    gcc_idx = [i for i, e in enumerate(existing) if e.playbook_item_id.startswith("GCC-")]
    human_na = existing[gcc_idx[0]].playbook_item_id
    existing[gcc_idx[0]] = replace(
        existing[gcc_idx[0]], applicability="Not applicable", excluded_by=None, status="N/A"
    )
    retired = {existing[i].playbook_item_id for i in gcc_idx[1:3]}
    lib = [replace(item, active=False) if item.id in retired else item for item in library]
    touched = {c.playbook_item_id for c in reassemble(existing, fleets, lib).changes}
    assert human_na not in touched
    assert not touched & retired
    assert any(i.startswith("GCC-") for i in touched)  # the remaining GCC items are excluded


# --- B9 ----------------------------------------------------------------------------------------


def test_flagship_gate_history_dates_keep_their_offsets(db):
    from sqlalchemy import select

    from app import clock
    from app.models import GateReview

    today = clock.today()
    rows = db.scalars(select(GateReview).where(GateReview.transition_id == "TR-0001")).all()
    offsets = {r.gate: (today - r.decided_at.date()).days for r in rows}
    assert {g: offsets[g] for g in ("SG0", "SG2", "SG3") if g in offsets} == {
        g: d for g, d in {"SG0": 120, "SG2": 75, "SG3": 30}.items() if g in offsets
    }
