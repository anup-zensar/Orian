"""API error contract (spec §9).

* 401 – missing / unknown ``X-Demo-User``
* 403 – permission failure: ``{"detail": str, "reasons": [str]}``
* 404 – not found: ``{"detail": str, "reasons": []}``
* 409 – business-rule violation: ``{"detail": str, "reasons": [str]}`` (the UI shows ``reasons``)
* 422 – validation error: ``{"detail": "Validation failed", "reasons": [str], "errors": [...]}``

Raise these from routers or ``domain`` functions; ``app.main`` turns them into JSON responses.
"""

from __future__ import annotations


class ApiError(Exception):
    status_code = 400

    def __init__(self, detail: str, reasons: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reasons = list(reasons) if reasons is not None else []

    def to_dict(self) -> dict[str, object]:
        return {"detail": self.detail, "reasons": self.reasons}


class Unauthorized(ApiError):
    status_code = 401


class Forbidden(ApiError):
    status_code = 403

    def __init__(self, detail: str, reasons: list[str] | None = None) -> None:
        super().__init__(detail, reasons if reasons is not None else [detail])


class NotFound(ApiError):
    status_code = 404


class Conflict(ApiError):
    """A business rule blocks the request; ``reasons`` explain why (spec §12 disabled-state tooltips)."""

    status_code = 409

    def __init__(self, detail: str, reasons: list[str] | None = None) -> None:
        super().__init__(detail, reasons if reasons is not None else [detail])


class BadRequest(ApiError):
    status_code = 422

    def __init__(self, detail: str, reasons: list[str] | None = None) -> None:
        super().__init__(detail, reasons if reasons is not None else [detail])
