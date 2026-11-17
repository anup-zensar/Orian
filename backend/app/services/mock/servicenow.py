"""Mock ServiceNow project lookup (spec 10.5) backed by seed/mock_external_systems.json."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.services.mock._common import log_mock, simulate_latency

_FIELDS = (
    "project_id",
    "name",
    "project_type",
    "investment_type",
    "delivery_method",
    "portfolio",
    "region",
    "market",
    "pm",
    "description",
)


def load_external_seed() -> dict[str, Any]:
    """Read the mock external systems seed file (always utf-8, PLAN conventions)."""
    path = get_settings().seed_dir / "mock_external_systems.json"
    with open(path, encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


class MockServiceNowService:
    def get_project(self, project_id: str) -> dict[str, Any] | None:
        simulate_latency()
        log_mock("ServiceNow", "get_project", project_id=project_id)
        wanted = (project_id or "").strip().lower()
        for record in load_external_seed().get("servicenow_projects", []):
            if str(record.get("project_id", "")).strip().lower() == wanted:
                return {field: record.get(field) for field in _FIELDS}
        return None
