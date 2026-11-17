"""Live ServiceNow stub (spec 10.5)."""

from __future__ import annotations

from typing import Any


class LiveServiceNowService:
    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Real call: ServiceNow Table API ``GET /api/now/table/pm_project?number=<id>``."""
        raise NotImplementedError("Live ServiceNow is a stub in the MVP")
