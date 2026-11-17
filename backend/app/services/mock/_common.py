"""Helpers shared by every mock service (spec section 10, PLAN A-18)."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger("orion.mock")


def simulate_latency() -> None:
    """Sleep ``MOCK_DELAY_MS`` milliseconds (0 = no sleep) to feel like a real integration."""
    delay_ms = get_settings().mock_delay_ms
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)


def log_mock(service: str, operation: str, **params: Any) -> None:
    """Log one line per mock call: ``[MOCK <Service>] <operation> key=value ...`` (spec 10)."""
    pairs = " ".join(f"{key}={value}" for key, value in params.items())
    line = f"[MOCK {service}] {operation} {pairs}".rstrip()
    # Keep the log ASCII only (Windows consoles).
    logger.info(line.encode("ascii", "replace").decode("ascii"))
