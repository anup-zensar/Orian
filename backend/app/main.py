"""FastAPI application entry point (spec §5). Run: ``uvicorn app.main:app --reload --port 8000``."""

from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import clock
from app.config import get_settings
from app.db import SessionLocal, configure_engine, create_all
from app.deps import get_current_user
from app.errors import ApiError
from app.middleware import install_middleware
from app.models import AppSetting
from app.routers import (
    actions,
    admin,
    ai_playbook,
    approvals,
    audit,
    conditions,
    control_tower,
    dashboard,
    defects,
    drafts,
    evidence,
    exceptions,
    gates,
    integrations,
    items,
    notifications,
    ocet,
    orion,
    outbox,
    reference,
    reminders,
    risks,
    scope,
    support_models,
    tiering,
    transitions,
    users,
)
from app.seed.loader import seed_if_empty

API_PREFIX = "/api/v1"
ROUTERS = (
    reference,
    users,
    transitions,
    control_tower,
    dashboard,
    tiering,
    scope,
    items,
    evidence,
    actions,
    conditions,
    exceptions,
    risks,
    defects,
    ai_playbook,
    gates,
    approvals,
    ocet,
    support_models,
    orion,
    drafts,
    reminders,
    outbox,
    notifications,
    integrations,
    admin,
    audit,
)

# Windows consoles may not encode "→" etc.; never let a log line crash a request.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):  # non-standard streams
        _stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("orion")


def restore_today_override() -> None:
    """Re-apply a demo "Set today" value persisted by the admin endpoint (A-15)."""
    with SessionLocal() as db:
        row = db.get(AppSetting, "today_override")
        value = row.value if row is not None else None
        clock.set_today_override(date.fromisoformat(value) if value else None)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_engine()
    create_all()
    with SessionLocal() as db:
        if seed_if_empty(db):
            logger.info("Database was empty - demo data seeded")
    restore_today_override()
    yield


app = FastAPI(
    title="Orion – Operate Readiness Agent API",
    version="0.1.0",
    description="Demo API. Every external system and AI capability is a mock behind an interface.",
    lifespan=lifespan,
)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = jsonable_encoder(exc.errors())
    reasons = []
    for err in errors:
        loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")]
        reasons.append(f"{'.'.join(loc) or 'request'}: {err.get('msg', 'invalid value')}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "reasons": reasons, "errors": errors},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Framework 404/405/... follow the same {detail, reasons} contract (spec §9)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail), "reasons": []},
        headers=exc.headers,
    )


install_middleware(app, get_settings())

# Only these routers are public (PLAN.md A-27); everything else requires a signed-in user, enforced
# here at include time so a new router cannot forget it (the modules keep their own dependency too).
PUBLIC_ROUTERS = (reference, users)
for module in ROUTERS:
    if module in PUBLIC_ROUTERS:
        app.include_router(module.router, prefix=API_PREFIX)
    else:
        app.include_router(
            module.router, prefix=API_PREFIX, dependencies=[Depends(get_current_user)]
        )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
