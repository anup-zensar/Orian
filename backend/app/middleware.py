"""Pure ASGI middlewares (no BaseHTTPMiddleware, so they also wrap unhandled errors, spec §5.5, A-24).

Order, outermost -> innermost: SecurityHeaders, CORS, BodySizeLimit, UnhandledError. Because
UnhandledError is innermost, a 500 response still passes through CORS and security headers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings

logger = logging.getLogger("orion")

API_PREFIX = "/api/"

# Must allow embedding in Microsoft Teams (spec §5.5) - so frame-ancestors, not X-Frame-Options: DENY.
FRAME_ANCESTORS = (
    "frame-ancestors 'self' https://teams.microsoft.com https://*.teams.microsoft.com "
    "https://*.cloud.microsoft https://*.office.com https://*.skype.com"
)
_BASE_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"content-security-policy", FRAME_ANCESTORS.encode("latin-1")),
)


def _json_body(detail: str, reasons: list[str]) -> bytes:
    return json.dumps({"detail": detail, "reasons": reasons}).encode("utf-8")


async def _send_json(send: Send, status: int, detail: str, reasons: list[str]) -> None:
    body = _json_body(detail, reasons)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith(API_PREFIX)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = list(_BASE_HEADERS)
                if is_api:
                    extra.append((b"cache-control", b"no-store"))
                headers.extend(h for h in extra if h[0] not in present)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


class _BodyTooLargeError(Exception):
    pass


class UnhandledErrorMiddleware:
    """Last-resort JSON 500; never leaks stack traces or internals (VAPT, PLAN.md A-24)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except _BodyTooLargeError:
            raise  # answered with 413 by BodySizeLimitMiddleware (outside this one)
        except Exception:
            logger.exception("Unhandled error")
            if not started:
                await _send_json(send, 500, "Internal server error", [])


class BodySizeLimitMiddleware:
    """413 for oversized bodies: by Content-Length up front, or while a streamed body is received."""

    def __init__(self, app: ASGIApp, max_bytes: int, max_mb: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.detail = f"Request too large (max {max_mb} MB)"
        self.reasons = [f"The request body must not exceed {max_mb} MB"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    too_large = int(value) > self.max_bytes
                except ValueError:
                    too_large = False
                if too_large:
                    await _send_json(send, 413, self.detail, self.reasons)
                    return
        received = 0
        started = False

        async def receive_wrapper() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLargeError
            return message

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except _BodyTooLargeError:
            if not started:
                await _send_json(send, 413, self.detail, self.reasons)


def install_middleware(app: FastAPI, settings: Settings) -> None:
    """Add the middlewares so the result is SecurityHeaders > CORS > BodySizeLimit > UnhandledError.

    Starlette makes the LAST added middleware the outermost, so they are added innermost first.
    """
    max_mb = settings.max_upload_mb
    limit_args: dict[str, Any] = {"max_bytes": (max_mb + 1) * 1024 * 1024, "max_mb": max_mb}
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, **limit_args)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Demo-User"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
