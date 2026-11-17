"""Settings typing (B5) and the demo-mode dependency."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.deps import require_demo_mode
from app.errors import NotFound


def test_modes_are_normalised(monkeypatch):
    monkeypatch.setenv("AI_MODE", " LIVE ")
    monkeypatch.setenv("MAIL_MODE", "Graph")
    settings = Settings()
    assert (settings.ai_mode, settings.mail_mode) == ("live", "graph")


@pytest.mark.parametrize(("var", "value"), [("AI_MODE", "lvie"), ("MAIL_MODE", "smtp")])
def test_mode_typo_fails_at_startup(monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(ValidationError):
        Settings()


def test_require_demo_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    require_demo_mode()
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    with pytest.raises(NotFound, match="DEMO_MODE=false"):
        require_demo_mode()
