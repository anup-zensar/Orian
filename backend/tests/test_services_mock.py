"""Tests for the mock service layer (spec 10, NFR-01). Self-contained: no conftest needed."""

from __future__ import annotations

import io
import logging
import zipfile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.config import get_settings
from app.db import Base
from app.errors import BadRequest, NotFound
from app.models.orion import Notification, OutboxMessage
from app.models.reference import User
from app.services import factory
from app.services.live.mail import LiveMailService
from app.services.mock.ai import MockAIService
from app.services.mock.confluence import MockConfluenceService
from app.services.mock.document_store import MockDocumentStore, sanitize_filename
from app.services.mock.mail import MockMailService
from app.services.mock.notification import MockNotificationService
from app.services.mock.servicenow import MockServiceNowService
from app.services.mock.support_model_generator import MockSupportModelGenerator
from app.services.mock.transcript import MockTranscriptService


@pytest.fixture(autouse=True)
def _settings(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(settings, "mock_delay_ms", 0)
    return settings


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id="U01", name="Ann", email="ann@example.com", role="PM"))
        session.add(User(id="U02", name="Bob", email="bob@example.com", role="PM"))
        session.flush()
        yield session


def test_servicenow_hit_and_miss():
    svc = MockServiceNowService()
    project = svc.get_project("  prj0052210 ")
    assert project is not None
    assert project["project_id"] == "PRJ0052210"
    assert project["pm"] == "Daniel Brooks"
    assert project["project_type"] == "Agentic AI"
    assert svc.get_project("PRJ0000000") is None


def test_confluence_voc_and_generic():
    svc = MockConfluenceService()
    voc = svc.fetch("https://wiki.example/display/VOC/Design")
    assert "Medallia" in voc["title"]
    assert voc["diagrams"] == ["voc_landscape.png"]
    assert voc["url"] == "https://wiki.example/display/VOC/Design"
    generic = svc.fetch("https://wiki.example/other")
    assert "generic" in generic["title"].lower()


def test_document_store_save_read_and_no_overwrite():
    store = MockDocumentStore()
    first = store.save("TR-0001", "notes.txt", b"one")
    second = store.save("TR-0001", "notes.txt", b"two")
    assert first["path"] == "TR-0001/notes.txt"
    assert first["url"] == "https://sharepoint.example/sites/orion/TR-0001/notes.txt"
    assert first["size"] == 3
    assert second["filename"] == "notes-1.txt"
    assert store.read(first["path"]) == b"one"
    assert store.read(second["path"]) == b"two"
    generated = store.save_generated("TR-0001", "deck.pptx", b"x")
    assert generated["filename"] == "deck.pptx"


def test_document_store_sanitizes_filename():
    assert sanitize_filename("../../etc/pass wd.txt") == "pass wd.txt"
    assert sanitize_filename("C:\\temp\\a<b>.pdf") == "a_b_.pdf"
    assert sanitize_filename("") == "file"
    assert len(sanitize_filename("a" * 300 + ".pdf")) <= 120
    saved = MockDocumentStore().save("TR-0002", "../evil/x.txt", b"hi")
    assert saved["path"] == "TR-0002/x.txt"


def test_document_store_rejects_bad_input(monkeypatch):
    store = MockDocumentStore()
    with pytest.raises(BadRequest):
        store.save("../TR-0001", "a.txt", b"x")
    with pytest.raises(BadRequest):
        store.save("TR-1", "a.txt", b"x")
    with pytest.raises(BadRequest):
        store.save("TR-0001", "malware.exe", b"x")
    with pytest.raises(BadRequest):
        store.save("TR-0001", "noext", b"x")
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    with pytest.raises(BadRequest):
        store.save("TR-0001", "big.txt", b"x" * (1024 * 1024 + 1))
    store.save("TR-0001", "ok.txt", b"x" * 1024 * 1024)


def test_document_store_read_traversal(tmp_path):
    store = MockDocumentStore()
    store.save("TR-0001", "a.txt", b"x")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    for bad in ("../secret.txt", "TR-0001/../../secret.txt", "missing/none.txt"):
        with pytest.raises(NotFound):
            store.read(bad)


def test_transcript_text_and_markdown():
    svc = MockTranscriptService()
    assert svc.get_text("a.txt", "caf\u00e9".encode()) == "caf\u00e9"
    assert svc.get_text("a.md", b"\xff# hi").endswith("# hi")


def test_transcript_vtt():
    vtt = (
        b"WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nHello team\n\n"
        b"2\n00:00:03.500 --> 00:00:05.000\nThis is the app\n"
    )
    assert MockTranscriptService().get_text("t.VTT", vtt) == "Hello team\nThis is the app"


def test_transcript_docx():
    buf = io.BytesIO()
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>First</w:t></w:r><w:r><w:t> line</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Second</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", xml)
    svc = MockTranscriptService()
    assert svc.get_text("t.docx", buf.getvalue()) == "First line\nSecond"
    assert svc.get_text("bad.docx", b"not a zip") == ""


def test_transcript_audio_and_unknown(caplog):
    svc = MockTranscriptService()
    with caplog.at_level(logging.INFO, logger="orion.mock"):
        text = svc.get_text("call.mp4", b"\x00")
    for word in ("central app", "integrations", "SSO", "monitoring", "L1", "L2", "L3"):
        assert word.lower() in text.lower()
    assert "Azure AI Speech" in caplog.text
    assert svc.get_text("x.bin", b"abc") == ""


def test_mail_writes_outbox(db):
    msg_id = MockMailService(db).send_mail(
        "orion@example.com", ["ann@example.com"], ["bob@example.com"], "Hi", "<p>x</p>", ["TR-0001"]
    )
    row = db.get(OutboxMessage, msg_id)
    assert row is not None
    assert (row.channel, row.mode, row.from_address) == ("Email", "mock", "orion@example.com")
    assert row.to == ["ann@example.com"] and row.cc == ["bob@example.com"]
    assert row.related_ids == ["TR-0001"]


def test_notification_rows(db):
    svc = MockNotificationService(db)
    ids = svc.notify(["U01", "U02"], "Hello", "/x")
    assert len(ids) == 2
    assert db.scalars(select(Notification)).all()[0].text == "Hello"
    out_id = svc.post_teams_card(["U01", "U02"], {"type": "AdaptiveCard"}, "Summary", ["TR-0001"])
    row = db.get(OutboxMessage, out_id)
    assert row is not None
    assert row.channel == "Teams"
    assert sorted(row.to) == ["ann@example.com", "bob@example.com"]
    assert row.subject == "Summary" and row.body_html == "Summary"
    assert row.adaptive_card_json == {"type": "AdaptiveCard"}


def test_factory_selection(db, monkeypatch, caplog):
    settings = get_settings()
    assert isinstance(factory.get_mail_service(db), MockMailService)
    assert isinstance(factory.get_notification_service(db), MockNotificationService)
    assert isinstance(factory.get_servicenow_service(), MockServiceNowService)
    assert isinstance(factory.get_document_store(), MockDocumentStore)
    assert isinstance(factory.get_confluence_service(), MockConfluenceService)
    assert isinstance(factory.get_transcript_service(), MockTranscriptService)
    assert isinstance(factory.get_support_model_generator(), MockSupportModelGenerator)
    assert isinstance(factory.get_ai_service(), MockAIService)
    monkeypatch.setattr(settings, "mail_mode", "graph")
    assert isinstance(factory.get_mail_service(db), LiveMailService)
    monkeypatch.setattr(settings, "ai_mode", "live")
    with caplog.at_level(logging.WARNING, logger="orion.services"):
        assert isinstance(factory.get_ai_service(), MockAIService)
    assert "SHOULD" in caplog.text


def test_ai_service_methods_implemented_and_later_milestones_pending():
    ai = MockAIService()
    for call in (
        lambda: ai.readiness_narrative({}),
        lambda: ai.recommend_actions([]),
        lambda: ai.recommend_applicability([], {}),
        lambda: ai.draft_message("Chaser", {}),
    ):
        assert call() is not None
    for call in (
        lambda: ai.leadership_update({}),
        lambda: ai.explain_ocet_change({}),
        lambda: MockSupportModelGenerator().generate({}, {}),
    ):
        with pytest.raises(NotImplementedError, match=r"is implemented in M\d"):
            call()
