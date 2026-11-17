"""Core API (M1.8): reference, users, me, auth errors, security headers (A-23, A-24, A-27)."""

from __future__ import annotations

API = "/api/v1"


def test_reference_is_public_and_complete(client):
    res = client.get(f"{API}/reference")  # no X-Demo-User header
    assert res.status_code == 200
    body = res.json()
    assert len(body["gates"]) == 7
    assert len(body["portfolios"]) == 6
    counts = body["checklist_counts"]
    assert counts["framework"] == 72
    assert counts["ai_playbook_total"] == 216
    assert counts["ai_playbook_by_tier"]["2"] == 208
    assert counts["ai_playbook_by_tier"]["1"] == 192
    assert counts["common"] == 2
    types = {p["code"]: p for p in body["project_types"]}
    assert types["Normal"]["checklists"] == ["FRAMEWORK"]
    assert types["Agentic AI"]["requires_tiering"] is True
    assert "EXCEPTION" in body["approval_chains"]


def test_users_public_and_sixteen(client):
    res = client.get(f"{API}/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 16
    assert {u["id"] for u in users} >= {"U01", "U14", "U16"}
    assert next(u for u in users if u["id"] == "U14")["role"] == "IRM"


def test_me_requires_header(client):
    res = client.get(f"{API}/me")
    assert res.status_code == 401
    assert res.json()["detail"]
    assert "X-Demo-User" in res.json()["detail"]


def test_me_unknown_user(client, headers):
    res = client.get(f"{API}/me", headers=headers("U99"))
    assert res.status_code == 401
    assert "U99" in res.json()["detail"]


def test_me_irm_can_confirm_tier(client, headers):
    res = client.get(f"{API}/me", headers=headers("U14"))
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["id"] == "U14"
    assert "confirm_tier" in body["permissions"]
    assert "confirm_tier" not in body["denied_reasons"]


def test_me_or_focal_denied_confirm_tier_with_reason(client, headers):
    body = client.get(f"{API}/me", headers=headers("U01")).json()
    assert "confirm_tier" not in body["permissions"]
    assert body["denied_reasons"]["confirm_tier"] == "Only IRM can confirm the tier"
    assert "propose_tier" in body["permissions"]


def test_security_headers(client):
    res = client.get(f"{API}/users")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors" in res.headers["Content-Security-Policy"]
    assert res.headers["Cache-Control"] == "no-store"
    assert res.headers["Referrer-Policy"]
    health = client.get("/health")
    assert health.status_code == 200
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert "Cache-Control" not in health.headers or health.headers["Cache-Control"] != "no-store"
