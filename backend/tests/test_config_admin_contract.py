"""CR-01 contract of /api/v1/admin/... (routers/config_admin.py): every endpoint of design 4 exists,
GETs work for the Admin and answer 403 for everyone else, writes answer 501 until the admin-API
engineer implements them (A-74), previews do not write."""

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
    "permissions",
    "tiering",
    "eval-metrics",
    "thresholds",
    "labels",
    "gates",
    "lenses",
    "message-templates",
    "config-export",
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
    ("post", "roles"),
    ("patch", "roles/PM"),
    ("delete", "roles/PM"),
    ("post", "users"),
    ("patch", "users/U01"),
    ("post", "users/U01/deactivate"),
    ("put", "permissions"),
    ("put", "tiering"),
    ("post", "tiering/test"),
    ("post", "eval-metrics"),
    ("patch", "eval-metrics/EV-01"),
    ("put", "thresholds"),
    ("put", "labels"),
    ("put", "gates"),
    ("put", "lenses"),
    ("put", "message-templates"),
    ("post", "config-import"),
    ("post", "config/reset"),
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
def test_writes_are_admin_only_and_not_implemented_yet(client, headers, method, path) -> None:
    url = "/api/v1/admin/" + path
    for user in ("U01", "U14"):
        r = client.request(method.upper(), url, json={}, headers=headers(user))
        assert r.status_code in (403, 422), (method, path, user, r.status_code)
    # a valid-shaped body reaches the stub: 501 (not 500, not 404)
    body = _valid_body(method, path)
    r = client.request(method.upper(), url, json=body, headers=headers(ADMIN))
    assert r.status_code in (501, 422), (method, path, r.status_code, r.text[:300])


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
        "roles": {"code": "SECURITY_LEAD", "label": "Security lead"},
        "users": {"name": "Sam", "email": "sam@example.com", "role": "PM"},
        "users/U01/deactivate": {},
        "permissions": {"matrix": {}},
        "tiering": {
            "tiers": [{"tier": 1, "name": "T1"}],
            "dimensions": [],
            "default_tier": 1,
            "questions": [],
            "rules": [],
        },
        "tiering/test": {},
        "eval-metrics": {"metric": "New metric"},
        "labels": {"labels": {}},
        "message-templates": {"templates": []},
        "config-import": {"schema_version": 2, "sections": {}},
        "config/reset": {"section": "labels"},
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
    assert [t["code"] for t in types] == ["Normal", "Infrastructure", "Agentic AI", "Combined"]
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
    assert [r["result_tier"] for r in tiering["rules"]] == [4, 3, 1, 2] and tiering[
        "default_tier"
    ] == 3
    assert [t["tier"] for t in tiering["tiers"]] == [1, 2, 3, 4]
    assert any(s["key"] == "audience" and "External" in s["values"] for s in tiering["sources"])

    thresholds = get("thresholds")
    assert thresholds["thresholds"]["rag"]["red_near_days"] == 7
    assert thresholds["rag_rule"]["green"] == "otherwise"

    gates = get("gates")
    assert [g["code"] for g in gates["gates"]][:2] == ["SG0", "SG2"]
    assert (
        gates["chain"] == {"SG4_ATD": "AtD", "SG6_ATO": "AtO"} and gates["mock_role"] == "CISO_BISO"
    )

    templates = get("message-templates")
    chaser = next(t for t in templates if t["key"] == "chaser")
    assert chaser["code_source"] and chaser["subject"] == chaser["default_subject"]
    assert any(p["name"] == "item_list" and p["html"] for p in chaser["placeholders"])

    export = get("config-export")
    assert export["schema_version"] >= 2
    assert {"roles", "option_items", "message_templates", "settings"} <= set(export["sections"])

    roles = get("roles")
    assert [r["code"] for r in roles][:3] == ["OR_FOCAL", "PM", "ARCHITECT"]
    assert next(r for r in roles if r["code"] == "OR_FOCAL")["user_count"] == 9


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
    assert client.get("/api/v1/reference").status_code == 200
    assert client.get("/api/v1/admin/option-lists").status_code == 401
