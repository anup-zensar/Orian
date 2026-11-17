"""Service factory (spec 10, NFR-01): the only place that picks mock vs live implementations."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.interfaces import (
    AIService,
    ConfluenceService,
    DocumentStore,
    MailService,
    NotificationService,
    ServiceNowService,
    SupportModelGenerator,
    TranscriptService,
)
from app.services.live.mail import LiveMailService
from app.services.mock.ai import MockAIService
from app.services.mock.confluence import MockConfluenceService
from app.services.mock.document_store import MockDocumentStore
from app.services.mock.mail import MockMailService
from app.services.mock.notification import MockNotificationService
from app.services.mock.servicenow import MockServiceNowService
from app.services.mock.support_model_generator import MockSupportModelGenerator
from app.services.mock.transcript import MockTranscriptService

logger = logging.getLogger("orion.services")


def get_ai_service() -> AIService:
    if get_settings().ai_mode.lower() == "live":
        logger.warning("AI_MODE=live is a SHOULD item and is not enabled in the MVP; using mock AI")
    return MockAIService()


def get_mail_service(db: Session) -> MailService:
    if get_settings().mail_mode.lower() == "graph":
        return LiveMailService()
    return MockMailService(db)


def get_notification_service(db: Session) -> NotificationService:
    return MockNotificationService(db)


def get_servicenow_service() -> ServiceNowService:
    return MockServiceNowService()


def get_document_store() -> DocumentStore:
    return MockDocumentStore()


def get_confluence_service() -> ConfluenceService:
    return MockConfluenceService()


def get_transcript_service() -> TranscriptService:
    return MockTranscriptService()


def get_support_model_generator() -> SupportModelGenerator:
    return MockSupportModelGenerator()
