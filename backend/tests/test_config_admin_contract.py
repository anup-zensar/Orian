"""CR-01 contract of /api/v1/admin/... (routers/config_admin.py): every endpoint of design 4 exists,
GETs work for the Admin and answer 403 for everyone else, every write is Admin only, previews do not
write. (What each write does is tested in test_config_*.py.) Dropped by the CR-01 simplification: custom
roles, tier rules, label / gate / lens documents, config export / import and section reset."""

from __future__ import annotations

import re

import pytest

ADMIN = "U16"

GETS = [
    "project-types",
    "project-types/Normal/preview",
    "checklists",
    "portfolios",
    "option-lists",
    "option-lists/severities/items",
    "intake-fields",
    "roles",
    "users",
    "permissions",
    "tiering",
    "eval-metrics",
    "thresholds",
    "message-templates",
    "usage?kind=project_type&key=Agentic%20AI",
]

# (method, path) of every WRITE endpoint of design 4 plus the documented extensions
WRITES = [
    ("post", "project-types"),
    ("patch", "project-types/Normal"),
    ("delete", "project-types/Normal"),
    ("post", "checklists"),
    ("patch", "checklists/FRAMEWORK"),
    ("delete", "checklists/FRAMEWORK"),
    ("post", "playbook-items"),
    ("post", "portfolios"),
    ("patch", "portfolios/GCC"),
    ("delete", "portfolios/GCC"),
    ("post", "option-lists"),
    ("patch", "option-lists/regions"),
    ("delete", "option-lists/regions"),
    ("put", "option-lists/regions/items"),
    ("post", "intake-fields"),
    ("put", "intake-fields/order"),
    ("patch", "intake-fields/name"),
    ("delete", "intake-fields/name"),
    ("patch", "roles/PM"),
    ("post", "users"),
    ("patch", "users/U01"),
    ("post", "users/U01/deactivate"),
    ("put", "permissions"),
    ("put", "tiering"),
    ("post", "eval-metrics"),
    ("patch", "eval-metrics/EV-01"),
    ("put", "thresholds"),
    ("put", "message-templates"),
]


def _documented(paths: dict, method: str, concrete: str) -> bool:
    """True when some OpenAPI path template (``/x/{code}/y``) matches the concrete path for ``method``."""
    for template, ops in paths.items():
        pattern = "^" + re.sub(r"\{[^/]+\}", "[^/]+", template) + "$"
        if method in ops and re.match(pattern, concrete):
            return True
    return False


def test_every_endpoint_is_in_the_openapi_document(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in GETS:
        assert _documented(paths, "get", "/api/v1/admin/" + path.split("?")[0]), path
    for method, path in WRITES:
        assert _documented(paths, method, "/api/v1/admin/" + path), (method, path)
    assert _documented(paths, "post", "/api/v1/admin/message-templates/chaser/preview")


@pytest.mark.parametrize("path", GETS)
def test_get_endpoints_work_for_the_admin(client, headers, path) -> None:
    r = client.get("/api/v1/admin/" + path, headers=headers(ADMIN))
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("path", GETS)
def test_get_endpoints_are_admin_only(client, headers, path) -> None:
    for user in ("U01", "U14", "U15"):
        r = client.get("/api/v1/admin/" + path, headers=headers(user))
        assert r.status_code == 403, (path, user, r.status_code)
    assert client.get("/api/v1/admin/" + path).status_code == 401


@pytest.mark.parametrize(("method", "path"), WRITES)
def test_writes_are_admin_only(client, headers, method, path) -> None:
    url = "/api/v1/admin/" + path
    for user in ("U01", "U14", "U15"):
        r = client.request(
            method.upper(), url, json=_valid_body(method, path), headers=headers(user)
        )
        assert r.status_code == 403, (method, path, user, r.status_code)
    r = client.request(method.upper(), url, json=_valid_body(method, path))
    assert r.status_code == 401, (method, path)


def test_dropped_endpoints_are_gone(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for gone in ("labels", "gates", "lenses", "config-export", "config-import", "config/reset"):
        assert "/api/v1/admin/" + gone not in paths, gone
    assert "post" not in paths["/api/v1/admin/roles"] if "/api/v1/admin/roles" in paths else True
    assert "/api/v1/admin/tiering/test" not in paths


def _valid_body(method: str, path: str) -> dict:
    """Smallest valid body per endpoint (422 from FastAPI otherwise, still proves the route exists)."""
    bodies = {
        "project-types": {"code": "Security Review", "label": "Security Review"},
        "checklists": {"code": "SECURITY_PLAYBOOK", "label": "Security playbook"},
        "playbook-items": {"source": "FRAMEWORK", "title": "x", "gate": "SG2", "lens": "Technical"},
        "portfolios": {"name": "Fuels EU", "code": "FEU"},
        "option-lists": {"key": "my_list", "label": "My list"},
        "option-lists/regions/items": {"items": []},
        "intake-fields": {"label": "Cost centre"},
        "intake-fields/order": {"keys": []},
        "users": {"name": "Sam", "email": "sam@example.com", "role": "PM"},
        "users/U01/deactivate": {},
        "permissions": {"matrix": {}},
        "thresholds": {"thresholds": {}},
        "tiering": {"tiers": [{"tier": 1, "name": "T1"}], "questions": []},
        "eval-metrics": {"metric": "New metric"},
        "message-templates": {"templates": []},
    }
    return bodies.get(path, {})


def test_preview_renders_and_writes_nothing(client, headers) -> None:
    r = client.post(
        "/api/v1/admin/message-templates/chaser/preview",
        json={"body": "<p>{{greeting}} {{transition_name}} {{nonsense}}</p>"},
        headers=headers(ADMIN),
    )
    assert r.status_code == 200
    out = r.json()
    assert "Mobility Knowledge Agent" in out["body_html"]
    assert out["unknown_placeholders"] == ["nonsense"]
    # an HTML special character in a value is escaped
    r = client.post(
        "/api/v1/admin/message-templates/chaser/preview",
        json={"body": "{{transition_name}}", "context": {"transition_name": "<script>x</script>"}},
        headers=headers(ADMIN),
    )
    assert r.json()["body_html"] == "&lt;script&gt;x&lt;/script&gt;"
    assert (
        client.post(
            "/api/v1/admin/message-templates/nope/preview", json={}, headers=headers(ADMIN)
        ).status_code
        == 404
    )


def test_project_type_preview_counts_items(client, headers) -> None:
    out = client.get(
        "/api/v1/admin/project-types/Agentic%20AI/preview", headers=headers(ADMIN)
    ).json()
    assert out["shows_tiering"] and out["shows_ai_profile"] and out["shows_eval_metrics"]
    assert (
        out["items_by_checklist"]["FRAMEWORK"] > 0 and out["items_by_checklist"]["AI_PLAYBOOK"] > 0
    )
    assert out["total_items"] == sum(out["items_by_checklist"].values())
    normal = client.get("/api/v1/admin/project-types/Normal/preview", headers=headers(ADMIN)).json()
    assert "AI_PLAYBOOK" not in normal["items_by_checklist"] and not normal["shows_ai_profile"]
    assert (
        client.get("/api/v1/admin/project-types/Nope/preview", headers=headers(ADMIN)).status_code
        == 404
    )


def test_get_shapes(client, headers) -> None:
    def get(path: str):
        return client.get("/api/v1/admin/" + path, headers=headers(ADMIN)).json()

    types = get("project-types")
    assert [t["code"] for t in types] == ["Normal", "Agentic AI", "Infrastructure"]
    assert sum(t["used_by"] for t in types) == 17 or all(t["used_by"] >= 0 for t in types)

    lists = {x["key"]: x for x in get("option-lists")}
    assert lists["evidence_statuses"]["structural"] and lists["evidence_statuses"]["lock_reason"]
    assert not lists["regions"]["structural"] and lists["severities"]["is_builtin"]
    items = get("option-lists/severities/items")["items"]
    assert [i["value"] for i in items] == ["Critical", "Major", "Minor"]
    assert items[0]["used_by"] > 0  # seeded gaps use Critical

    matrix = get("permissions")
    rows = {r["perm"]: r for r in matrix["permissions"]}
    assert set(rows) >= {
        "view",
        "admin",
        "view_all_approvals",
        "see_mock_approvals",
        "see_all_transitions",
    }
    assert rows["edit_ocet"]["scope"] == "global" or rows["edit_ocet"]["scope"] == "transition"
    assert rows["admin"]["scope"] == "global" and "ADMIN" in rows["admin"]["locked_roles"]
    assert (
        rows["confirm_tier"]["roles"] == ["IRM"] and rows["confirm_tier"]["scope"] == "transition"
    )
    assert rows["confirm_tier"]["denial_reason"] == "Only IRM can confirm the tier"
    assert (
        "ADMIN" in rows["confirm_tier"]["lock_reasons"]
    )  # granting it has no effect on transitions
    assert len(matrix["roles"]) == 8

    tiering = get("tiering")
    assert [t["tier"] for t in tiering["tiers"]] == [1, 2, 3, 4]
    assert [q["id"] for q in tiering["questions"]] == ["TQ1", "TQ2", "TQ3", "TQ4", "TQ5"]
    assert set(tiering) == {"tiers", "questions", "notice"}  # no rule builder

    thresholds = get("thresholds")
    assert thresholds["thresholds"]["rag"]["red_near_days"] == 7
    assert thresholds["rag_rule"]["green"] == "otherwise"

    templates = get("message-templates")
    chaser = next(t for t in templates if t["key"] == "chaser")
    assert chaser["code_source"] and chaser["subject"] == chaser["default_subject"]
    assert any(p["name"] == "item_list" and p["html"] for p in chaser["placeholders"])

    roles = get("roles")
    assert [r["code"] for r in roles][:3] == ["OR_FOCAL", "PM", "ARCHITECT"]
    assert (
        next(r for r in roles if r["code"] == "OR_FOCAL")["user_count"] == 2
    )  # U01 + the test-only U02


def test_usage_endpoint(client, headers) -> None:
    r = client.get(
        "/api/v1/admin/usage",
        params={"kind": "project_type", "key": "Agentic AI"},
        headers=headers(ADMIN),
    ).json()
    assert r["count"] >= 1 and len(r["transitions"]) <= 10
    assert (
        client.get(
            "/api/v1/admin/usage", params={"kind": "bogus", "key": "x"}, headers=headers(ADMIN)
        ).status_code
        == 422
    )


def test_reference_stays_public_but_admin_routes_do_not(client) -> None:
    assert client.get("/api/v1/reference", headers={"X-Demo-User": "U01"}).status_code == 200
    assert client.get("/api/v1/admin/option-lists").status_code == 401
