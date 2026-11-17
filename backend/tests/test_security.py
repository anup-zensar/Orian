"""Auth on every private route (B1), framework error contract (B2), pure-ASGI middleware (B3)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.middleware import install_middleware

API = "/api/v1"
PUBLIC = {("GET", f"{API}/reference"), ("GET", f"{API}/users")}
ORIGIN = get_settings().cors_origins[0]


def _api_routes() -> list[tuple[str, str, set[str]]]:
    """(path, template-with-dummies, methods) for every API route, nested includes resolved.

    Newer FastAPI keeps included routers as ``_IncludedRouter`` nodes in ``app.routes`` instead of
    flattening them, so those are expanded through ``effective_route_contexts``.
    """
    found: list[tuple[str, APIRoute]] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            found.append((route.path, route))
        elif hasattr(route, "effective_route_contexts"):
            found.extend((ctx.path, ctx.original_route) for ctx in route.effective_route_contexts())
    out = []
    for path, route in found:
        if not path.startswith(API) or not isinstance(route, APIRoute):
            continue
        concrete = path
        for name in route.param_convertors:
            value = "TR-0001" if "transition" in name or name == "tid" else "1"
            concrete = concrete.replace("{" + name + ":path}", value).replace(
                "{" + name + "}", value
            )
        out.append((path, concrete, set(route.methods)))
    return out


def test_every_private_route_requires_auth(client):
    routes = _api_routes()
    assert len(routes) >= 3  # reference, users, me (a refactor of app.routes must not empty this)
    checked = 0
    for path, concrete, methods in routes:
        for method in sorted(methods - {"HEAD", "OPTIONS"}):
            if (method, path) in PUBLIC:
                continue
            res = client.request(method, concrete)  # no X-Demo-User header
            assert res.status_code == 401, f"{method} {path} -> {res.status_code}"
            body = res.json()
            assert "detail" in body and "reasons" in body, f"{method} {path}"
            checked += 1
    assert checked >= 1  # GET /me at least


def test_unknown_path_uses_error_contract(client):
    res = client.get(f"{API}/does-not-exist")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found", "reasons": []}


def test_method_not_allowed_keeps_allow_header(client):
    res = client.post(f"{API}/reference")
    assert res.status_code == 405
    assert res.json()["reasons"] == []
    assert "GET" in res.headers["allow"]


def _mini_app() -> FastAPI:
    mini = FastAPI()
    install_middleware(mini, get_settings())

    @mini.get("/api/v1/boom")
    def boom() -> None:
        raise RuntimeError("secret internals")

    @mini.post("/api/v1/upload")
    async def upload() -> dict[str, bool]:
        return {"ok": True}

    @mini.post("/api/v1/stream")
    async def stream(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    return mini


def test_unhandled_error_is_json_with_security_and_cors_headers(caplog):
    with (
        caplog.at_level(logging.ERROR, logger="orion"),
        TestClient(_mini_app(), raise_server_exceptions=False) as mini,
    ):
        res = mini.get("/api/v1/boom", headers={"Origin": ORIGIN})
    assert res.status_code == 500
    assert res.json() == {"detail": "Internal server error", "reasons": []}
    assert "secret internals" not in res.text
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors" in res.headers["content-security-policy"]
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["access-control-allow-origin"] == ORIGIN
    assert any("Unhandled error" in r.getMessage() for r in caplog.records)


def test_oversized_content_length_gets_413():
    limit_mb = get_settings().max_upload_mb
    with TestClient(_mini_app()) as mini:
        res = mini.post(
            "/api/v1/upload",
            content=b"x" * ((limit_mb + 1) * 1024 * 1024 + 1),
            headers={"Origin": ORIGIN},
        )
    assert res.status_code == 413
    body = res.json()
    assert body["detail"] == f"Request too large (max {limit_mb} MB)" and body["reasons"]
    assert res.headers["access-control-allow-origin"] == ORIGIN


def test_streamed_oversized_body_without_content_length_gets_413(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    mini = _mini_app()  # built after the patch: limit is 1 MB + 1 MB

    def chunks():
        for _ in range(3):
            yield b"x" * (1024 * 1024)

    with TestClient(mini) as client:
        res = client.post("/api/v1/stream", content=chunks())  # chunked: no Content-Length
    assert res.status_code == 413
    assert res.json()["detail"] == "Request too large (max 1 MB)"


def test_real_app_responses_carry_security_headers(client):
    res = client.get(f"{API}/reference")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert res.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert "frame-ancestors" in res.headers["content-security-policy"]
    assert res.headers["cache-control"] == "no-store"
