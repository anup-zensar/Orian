"""CR-01 admin sections that need no special test file of their own: project types, checklists and
items, portfolios, intake fields, thresholds, tiering wording, eval metrics, reminder rules, approval
chains, usage. Every write is audited as Human / config:<section> and refreshes the caches."""

from __future__ import annotations

from app.domain import cfg
from app.models import AuditEvent, IntakeField, Transition

API = "/api/v1"
ADMIN = "U16"


def _h(headers):
    return headers(ADMIN)


def _audit_last(db, entity: str) -> AuditEvent:
    db.expire_all()
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.entity == entity)
        .order_by(AuditEvent.id.desc())
        .first()
    )


def _type(client, headers, code: str) -> dict:
    return next(
        t
        for t in client.get(f"{API}/admin/project-types", headers=_h(headers)).json()
        if t["code"] == code
    )


# --- project types, checklists, items (acceptance journey A, by data only) -------------------------------


def test_new_project_type_with_its_own_checklist(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    made = client.post(
        f"{API}/admin/checklists",
        json={
            "code": "SECURITY_PLAYBOOK",
            "label": "Security playbook",
            "description": "Pen test and threat model",
        },
        headers=h,
    )
    assert made.status_code == 201
    item = client.post(
        f"{API}/admin/playbook-items",
        json={
            "source": "SECURITY_PLAYBOOK",
            "title": "Threat model reviewed",
            "gate": "SG2",
            "lens": "Compliance",
            "default_owner_role": "IRM",
        },
        headers=h,
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["id"]
    assert (
        item_id == "SP-001" and item.json()["source"] == "SECURITY_PLAYBOOK"
    )  # initials: ids are <= 20 chars
    second = client.post(
        f"{API}/admin/playbook-items",
        json={
            "source": "SECURITY_PLAYBOOK",
            "title": "Pen test passed",
            "gate": "SG3",
            "lens": "Technical",
        },
        headers=h,
    )
    assert second.json()["id"] == "SP-002"
    r = client.post(
        f"{API}/admin/project-types",
        json={
            "code": "Security Review",
            "label": "Security review",
            "description": "A security-only review",
            "checklists": ["FRAMEWORK", "SECURITY_PLAYBOOK"],
            "requires_tiering": True,
            "required_intake_fields": ["audience"],
            "synonyms": ["sec review", "Sec Review", " "],
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    created = next(t for t in r.json() if t["code"] == "Security Review")
    assert created["label"] == "Security review" and created["active"] and created["used_by"] == 0
    assert (
        created["synonyms"] == ["sec review"]
        and not created["has_ai_profile"]
        and not created["has_eval_metrics"]
    )
    assert created["sort_order"] > max(
        t["sort_order"] for t in r.json() if t["code"] != "Security Review"
    )
    # visible to the forms: reference, preview counts, cfg flags
    ref = client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()
    assert "Security Review" in [t["code"] for t in ref["project_types"]]
    assert (
        "SECURITY_PLAYBOOK" in [c["code"] for c in ref["checklists"]]
        and "SECURITY_PLAYBOOK" in ref["enums"]["item_sources"]
    )
    preview = client.get(f"{API}/admin/project-types/Security%20Review/preview", headers=h).json()
    assert (
        preview["items_by_checklist"]["SECURITY_PLAYBOOK"] == 2
        and preview["items_by_checklist"]["FRAMEWORK"] > 0
    )
    assert (
        preview["shows_tiering"]
        and not preview["shows_ai_profile"]
        and "audience" in preview["required_intake_fields"]
    )
    assert cfg.project_type(db, "Security Review").requires_tiering
    event = _audit_last(db, "config:project_types")
    assert (
        event.actor_type == "Human"
        and event.action == "created"
        and event.entity_id == "Security Review"
    )
    # the type's required fields are written to BOTH sides
    audience = next(
        f
        for f in client.get(f"{API}/admin/intake-fields", headers=h).json()
        if f["key"] == "audience"
    )
    assert (
        "Security Review" in audience["required_for_project_types"]
        and audience["required_mode"] == "by_project_type"
    )


def test_project_type_validation(client, headers, fresh_seed) -> None:
    h = _h(headers)

    def post(**body):
        return client.post(
            f"{API}/admin/project-types",
            json={"code": "Valid Type", "checklists": ["FRAMEWORK"], **body},
            headers=h,
        )

    assert post(code="normal").status_code == 409  # codes are unique whatever the letter case
    assert post(code="Bad!Code").status_code == 422
    assert post(checklists=[]).status_code == 422
    assert post(checklists=["NOPE"]).status_code == 422
    assert post(checklists=["COMMON"]).status_code == 422  # added automatically
    assert post(required_intake_fields=["no_such_field"]).status_code == 422
    assert post().status_code == 201


def test_update_deactivate_and_delete_project_types(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    r = client.patch(
        f"{API}/admin/project-types/Normal",
        json={
            "label": "Standard",
            "has_ai_profile": True,
            "requires_tiering": True,
            "synonyms": ["std"],
        },
        headers=h,
    )
    assert r.status_code == 200
    normal = next(t for t in r.json() if t["code"] == "Normal")
    assert (
        normal["label"] == "Standard" and normal["has_ai_profile"] and normal["synonyms"] == ["std"]
    )
    assert cfg.project_type_label(db, "Normal") == "Standard" and normal["code"] == "Normal"
    before = _audit_last(db, "config:project_types").before
    assert before["label"] == "Standard Transition" and before["has_ai_profile"] is False
    # a used type is deactivated, never deleted
    r = client.delete(f"{API}/admin/project-types/Normal", headers=h)
    assert r.status_code == 409 and "deactivate instead" in r.json()["detail"]
    off = client.patch(f"{API}/admin/project-types/Normal", json={"active": False}, headers=h)
    assert off.status_code == 200
    assert "Normal" not in [
        t["code"]
        for t in client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()[
            "project_types"
        ]
    ]
    assert "Normal" in [
        t["code"]
        for t in client.get(
            f"{API}/reference", params={"include_inactive": "true"}, headers={"X-Demo-User": "U01"}
        ).json()["project_types"]
    ]
    assert cfg.project_type(db, "Normal") is not None  # old transitions still resolve it
    # unused: deletable
    client.post(
        f"{API}/admin/project-types",
        json={"code": "Temp", "checklists": ["FRAMEWORK"], "required_intake_fields": ["audience"]},
        headers=h,
    )
    assert client.delete(f"{API}/admin/project-types/Temp", headers=h).status_code == 200
    audience = next(
        f
        for f in client.get(f"{API}/admin/intake-fields", headers=h).json()
        if f["key"] == "audience"
    )
    assert "Temp" not in audience["required_for_project_types"]
    assert (
        client.patch(f"{API}/admin/project-types/Nope", json={"label": "x"}, headers=h).status_code
        == 404
    )
    assert client.delete(f"{API}/admin/project-types/Nope", headers=h).status_code == 404


def test_the_last_active_project_type_stays(client, headers, fresh_seed) -> None:
    h = _h(headers)
    for code in ("Normal", "Infrastructure"):
        assert (
            client.patch(
                f"{API}/admin/project-types/{code}", json={"active": False}, headers=h
            ).status_code
            == 200
        )
    r = client.patch(f"{API}/admin/project-types/Agentic AI", json={"active": False}, headers=h)
    assert r.status_code == 422 and "At least one project type" in r.json()["reasons"][0]


def test_required_fields_are_one_truth_on_both_sides(client, headers, fresh_seed) -> None:
    h = _h(headers)
    assert "audience" in _type(client, headers, "Agentic AI")["required_intake_fields"]
    # edit the FIELD side: refused, built-in fields follow their project types
    r = client.patch(
        f"{API}/admin/intake-fields/audience",
        json={"required_mode": "by_project_type", "required_for_project_types": ["Agentic AI"]},
        headers=h,
    )
    assert r.status_code == 422  # built-in fields are changed through their project types
    # edit the TYPE side
    r = client.patch(
        f"{API}/admin/project-types/Infrastructure",
        json={"required_intake_fields": ["write_actions"]},
        headers=h,
    )
    assert r.status_code == 200
    fields = {f["key"]: f for f in client.get(f"{API}/admin/intake-fields", headers=h).json()}
    assert "Infrastructure" not in fields["audience"]["required_for_project_types"]
    assert "Infrastructure" in fields["write_actions"]["required_for_project_types"]
    assert _type(client, headers, "Infrastructure")["required_intake_fields"] == ["write_actions"]
    assert "Agentic AI" in fields["audience"]["required_for_project_types"]


def test_checklist_rules(client, headers, fresh_seed) -> None:
    h = _h(headers)
    body = {"code": "VENDOR_CHECKS", "label": "Vendor checks"}
    assert client.post(f"{API}/admin/checklists", json=body, headers=h).status_code == 201
    assert client.post(f"{API}/admin/checklists", json=body, headers=h).status_code == 409
    assert (
        client.post(
            f"{API}/admin/checklists", json={"code": "lowercase", "label": "x"}, headers=h
        ).status_code
        == 422
    )
    # listed by a project type: cannot be switched off, cannot be deleted
    client.patch(
        f"{API}/admin/project-types/Normal",
        json={"checklists": ["FRAMEWORK", "VENDOR_CHECKS"]},
        headers=h,
    )
    listing = {c["code"]: c for c in client.get(f"{API}/admin/checklists", headers=h).json()}
    assert (
        listing["VENDOR_CHECKS"]["project_types"] == ["Normal"]
        and listing["VENDOR_CHECKS"]["item_count"] == 0
    )
    assert (
        client.patch(
            f"{API}/admin/checklists/VENDOR_CHECKS", json={"active": False}, headers=h
        ).status_code
        == 409
    )
    assert client.delete(f"{API}/admin/checklists/VENDOR_CHECKS", headers=h).status_code == 409
    client.patch(f"{API}/admin/project-types/Normal", json={"checklists": ["FRAMEWORK"]}, headers=h)
    r = client.patch(
        f"{API}/admin/checklists/VENDOR_CHECKS",
        json={"label": "Vendor review", "tier_filtered": True},
        headers=h,
    )
    assert (
        r.status_code == 200
        and next(c for c in r.json() if c["code"] == "VENDOR_CHECKS")["tier_filtered"]
    )
    assert client.delete(f"{API}/admin/checklists/VENDOR_CHECKS", headers=h).status_code == 200
    # built-ins
    assert client.delete(f"{API}/admin/checklists/FRAMEWORK", headers=h).status_code == 409
    assert (
        client.patch(
            f"{API}/admin/checklists/COMMON", json={"tier_filtered": True}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{API}/admin/checklists/FRAMEWORK",
            json={"label": "Operate Readiness Framework v2"},
            headers=h,
        ).status_code
        == 200
    )
    assert (
        client.patch(f"{API}/admin/checklists/NOPE", json={"label": "x"}, headers=h).status_code
        == 404
    )


def test_new_playbook_item_validation(client, headers, fresh_seed) -> None:
    h = _h(headers)
    ok = {
        "source": "FRAMEWORK",
        "title": "A new check",
        "gate": "SG3",
        "lens": "Business",
        "applicable_tiers": [1, 2],
    }

    def post(**changes):
        return client.post(f"{API}/admin/playbook-items", json={**ok, **changes}, headers=h)

    first = post()
    assert first.status_code == 201 and first.json()["id"] == "FRAMEWORK-001"
    assert (
        first.json()["applicable_tiers"] == [1, 2]
        and first.json()["applies_to_project_types"] == []
    )
    assert post(gate="SG9").status_code == 422
    assert post(applicable_tiers=[7]).status_code == 422
    assert post(default_owner_role="WIZARD").status_code == 422
    assert post(applies_to_project_types=["Nope"]).status_code == 422
    assert post(portfolio="GCC").status_code == 422  # only golden-set items belong to a portfolio
    assert post(source="PORTFOLIO").status_code == 422  # a golden-set item needs a portfolio
    assert post(source="PORTFOLIO", portfolio="Nope").status_code == 422
    golden = post(source="PORTFOLIO", portfolio="GCC", title="GCC special")
    assert golden.status_code == 201 and golden.json()["portfolio"] == "GCC"
    assert post(source="NOPE").status_code == 404
    assert post(id="FRAMEWORK-001").status_code == 409
    explicit = post(id="MY-1")
    assert explicit.status_code == 201 and explicit.json()["id"] == "MY-1"
    client.patch(f"{API}/admin/checklists/COMMON", json={"active": False}, headers=h)
    assert post(source="COMMON").status_code == 422  # inactive checklist


# --- portfolios (acceptance journey B) --------------------------------------------------------------------


def test_new_portfolio_with_a_golden_set(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    r = client.post(
        f"{API}/admin/portfolios",
        json={
            "name": "Fuels EU",
            "code": "FEU",
            "label": "Fuels Europe",
            "focus_areas": ["Pricing", "Pricing", "Supply"],
            "requires_sites": True,
            "sites_label": "Stations",
            "synonyms": ["fuels eu"],
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    created = next(p for p in r.json() if p["name"] == "Fuels EU")
    assert created["label"] == "Fuels Europe" and created["focus_areas"] == ["Pricing", "Supply"]
    assert (
        created["requires_sites"] and created["golden_set_count"] == 0 and created["used_by"] == 0
    )
    golden = client.put(
        f"{API}/admin/portfolios/Fuels%20EU/golden-set",
        json={
            "items": [
                {"title": "Price feed live", "gate": "SG3", "lens": "Technical", "mandatory": True}
            ]
        },
        headers=h,
    )
    assert golden.status_code == 200 and golden.json()["items"][0]["id"] == "FEU-01"
    ref = client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()
    assert "Fuels EU" in ref["portfolios"]
    detail = next(p for p in ref["portfolio_details"] if p["name"] == "Fuels EU")
    assert (
        detail["requires_sites"]
        and detail["golden_set_count"] == 1
        and detail["sites_label"] == "Stations"
    )
    assert (
        cfg.portfolio_requires_sites(db, "Fuels EU")
        and cfg.portfolio_label(db, "Fuels EU") == "Fuels Europe"
    )
    assert _audit_last(db, "config:portfolios").entity_id == "Fuels EU"


def test_portfolio_rules(client, headers, fresh_seed) -> None:
    h = _h(headers)
    body = {"name": "Fuels EU", "code": "FEU"}
    assert client.post(f"{API}/admin/portfolios", json=body, headers=h).status_code == 201
    assert (
        client.post(
            f"{API}/admin/portfolios", json={**body, "name": "fuels eu"}, headers=h
        ).status_code
        == 409
    )
    clash = client.post(f"{API}/admin/portfolios", json={"name": "Other", "code": "feu"}, headers=h)
    assert clash.status_code == 422 and "already used" in clash.json()["reasons"][0]
    r = client.patch(
        f"{API}/admin/portfolios/GCC",
        json={"label": "Global cards", "requires_sites": True, "active": True},
        headers=h,
    )
    assert (
        r.status_code == 200
        and next(p for p in r.json() if p["name"] == "GCC")["label"] == "Global cards"
    )
    # used: deactivate only; unused: deletable together with its golden set
    used = client.delete(f"{API}/admin/portfolios/GCC", headers=h)
    assert used.status_code == 409 and "deactivate instead" in used.json()["detail"]
    client.put(
        f"{API}/admin/portfolios/Fuels%20EU/golden-set",
        json={"items": [{"title": "t", "gate": "SG3", "lens": "Technical"}]},
        headers=h,
    )
    gone = client.delete(f"{API}/admin/portfolios/Fuels%20EU", headers=h)
    assert gone.status_code == 200 and "Fuels EU" not in [p["name"] for p in gone.json()]
    assert client.get(f"{API}/admin/portfolios/Fuels%20EU/golden-set", headers=h).status_code == 404
    assert (
        client.patch(f"{API}/admin/portfolios/Nope", json={"label": "x"}, headers=h).status_code
        == 404
    )
    for name in [p["name"] for p in client.get(f"{API}/admin/portfolios", headers=h).json()][:-1]:
        assert (
            client.patch(
                f"{API}/admin/portfolios/{name}", json={"active": False}, headers=h
            ).status_code
            == 200
        )
    last = [
        p["name"] for p in client.get(f"{API}/admin/portfolios", headers=h).json() if p["active"]
    ][0]
    r = client.patch(f"{API}/admin/portfolios/{last}", json={"active": False}, headers=h)
    assert r.status_code == 422 and "At least one portfolio" in r.json()["reasons"][0]


# --- intake fields -----------------------------------------------------------------------------------------


def test_custom_field_lifecycle(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    r = client.post(
        f"{API}/admin/intake-fields",
        json={
            "label": "Cost centre",
            "type": "text",
            "max_length": 20,
            "help": "Finance code",
            "required_mode": "by_project_type",
            "required_for_project_types": ["Normal"],
            "show_on_overview": True,
            "filterable": True,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    field = next(f for f in r.json() if f["key"] == "cf_cost_centre")
    assert (
        field["builtin"] is False
        and field["section"] == "Additional details"
        and field["max_length"] == 20
    )
    assert field["required_mode"] == "by_project_type" and field["sort_order"] == len(r.json()) - 1
    assert "cf_cost_centre" in _type(client, headers, "Normal")["required_intake_fields"]
    assert [f.key for f in cfg.intake_fields(db)][-1] == "cf_cost_centre"
    ref_fields = client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()[
        "intake_fields"
    ]
    assert any(f["key"] == "cf_cost_centre" and f["label"] == "Cost centre" for f in ref_fields)
    # same label -> a new unique key
    again = client.post(f"{API}/admin/intake-fields", json={"label": "Cost centre"}, headers=h)
    assert "cf_cost_centre_2" in [f["key"] for f in again.json()]
    # edit freely while unused, including the type
    r = client.patch(
        f"{API}/admin/intake-fields/cf_cost_centre",
        json={"type": "number", "min": 1, "max": 9, "max_length": None},
        headers=h,
    )
    assert r.status_code == 200, r.text
    # once a transition holds a value the type is fixed and the field cannot be deleted
    db.get(Transition, "TR-0001").custom_fields = {"cf_cost_centre": 5}
    db.commit()
    shown = next(
        f
        for f in client.get(f"{API}/admin/intake-fields", headers=h).json()
        if f["key"] == "cf_cost_centre"
    )
    assert (
        shown["used_by"] == 1 and shown["type_locked"] and "1 transitions" in shown["lock_reason"]
    )
    r = client.patch(f"{API}/admin/intake-fields/cf_cost_centre", json={"type": "text"}, headers=h)
    assert r.status_code == 422 and "type cannot change" in r.json()["reasons"][0]
    assert (
        client.patch(
            f"{API}/admin/intake-fields/cf_cost_centre",
            json={"label": "Cost center (US)"},
            headers=h,
        ).status_code
        == 200
    )
    gone = client.delete(f"{API}/admin/intake-fields/cf_cost_centre", headers=h)
    assert gone.status_code == 409 and "deactivate instead" in gone.json()["detail"]
    off = client.patch(
        f"{API}/admin/intake-fields/cf_cost_centre", json={"active": False}, headers=h
    )
    assert off.status_code == 200
    assert "cf_cost_centre" not in [
        f["key"]
        for f in client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()[
            "intake_fields"
        ]
    ]
    assert (
        client.delete(f"{API}/admin/intake-fields/cf_cost_centre_2", headers=h).status_code == 200
    )


def test_custom_field_validation(client, headers, fresh_seed) -> None:
    h = _h(headers)

    def post(**body):
        return client.post(f"{API}/admin/intake-fields", json={"label": "Thing", **body}, headers=h)

    assert post(type="select").status_code == 422  # needs a list
    assert post(type="select", option_list="no_such_list").status_code == 422
    assert post(type="select", option_list="regions").status_code == 201
    assert post(type="text", option_list="regions").status_code == 422
    assert post(type="text", min=1).status_code == 422
    assert post(type="number", min=5, max=1).status_code == 422
    assert post(type="number", max_length=5).status_code == 422
    assert post(required_mode="by_project_type").status_code == 422  # which types?
    assert (
        post(required_mode="by_project_type", required_for_project_types=["Nope"]).status_code
        == 422
    )
    assert post(applies_to_portfolios=["Nope"]).status_code == 422
    assert post(applies_to_project_types=["Nope"]).status_code == 422
    assert post(key="cost_centre").status_code == 422  # must start with cf_
    assert post(key="cf_explicit").status_code == 201
    assert post(key="cf_explicit").status_code == 422  # unique
    assert post(type="user", option_list="PM").status_code == 201
    assert post(type="user", option_list="NOPE").status_code == 422
    assert post(type="date").status_code == 201 and post(type="boolean").status_code == 201
    assert post(type="multiselect", option_list="regions").status_code == 201


def test_built_in_fields_change_label_help_and_visibility_only(
    client, headers, fresh_seed, db
) -> None:
    h = _h(headers)
    r = client.patch(
        f"{API}/admin/intake-fields/market",
        json={"label": "Country", "help": "Where it runs", "visible": False},
        headers=h,
    )
    assert r.status_code == 200
    market = next(f for f in r.json() if f["key"] == "market")
    assert (
        market["label"] == "Country"
        and market["help"] == "Where it runs"
        and market["visible"] is False
    )
    assert cfg.intake_field(db, "market").label == "Country"
    for change in (
        {"type": "textarea"},
        {"section": "X"},
        {"filterable": True},
        {"active": False},
        {"applies_to_portfolios": ["GCC"]},
    ):
        r = client.patch(f"{API}/admin/intake-fields/market", json=change, headers=h)
        assert r.status_code == 422 and "only its label" in r.json()["reasons"][0], change
    for key in ("name", "project_type", "portfolio", "region", "or_focal_user_id"):  # structural
        r = client.patch(f"{API}/admin/intake-fields/{key}", json={"visible": False}, headers=h)
        assert r.status_code == 422 and "cannot be hidden" in r.json()["reasons"][0], key
        assert (
            client.patch(
                f"{API}/admin/intake-fields/{key}", json={"label": f"{key} label"}, headers=h
            ).status_code
            == 200
        )
    assert client.delete(f"{API}/admin/intake-fields/market", headers=h).status_code == 409
    assert (
        client.patch(f"{API}/admin/intake-fields/nope", json={"label": "x"}, headers=h).status_code
        == 404
    )
    assert (
        client.patch(
            f"{API}/admin/intake-fields/market", json={"label": " "}, headers=h
        ).status_code
        == 422
    )


def test_field_order(client, headers, fresh_seed) -> None:
    h = _h(headers)
    keys = [f["key"] for f in client.get(f"{API}/admin/intake-fields", headers=h).json()]
    new = [keys[1], keys[0], *keys[2:]]
    r = client.put(f"{API}/admin/intake-fields/order", json={"keys": new}, headers=h)
    assert r.status_code == 200 and [f["key"] for f in r.json()] == new
    assert (
        client.put(
            f"{API}/admin/intake-fields/order", json={"keys": new[:-1]}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"{API}/admin/intake-fields/order", json={"keys": [*new, "ghost"]}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"{API}/admin/intake-fields/order", json={"keys": [*new[:-1], new[0]]}, headers=h
        ).status_code
        == 422
    )


# --- thresholds, tiering, eval metrics ----------------------------------------------------------------------


def _thresholds(client, headers) -> dict:
    return client.get(f"{API}/admin/thresholds", headers=_h(headers)).json()["thresholds"]


def test_thresholds_are_live_and_the_rag_rule_text_follows(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    doc = _thresholds(client, headers)
    doc["rag"].update(red_critical_gaps=3, red_lens_below=40, amber_lens_below=65)
    doc["calendar_horizon_days"] = 60
    r = client.put(f"{API}/admin/thresholds", json={"thresholds": doc}, headers=h)
    assert r.status_code == 200, r.text
    assert (
        "critical_gaps >= 3" in r.json()["rag_rule"]["red"]
        and "min_lens_readiness < 40" in r.json()["rag_rule"]["red"]
    )
    assert "min_lens_readiness < 65" in r.json()["rag_rule"]["amber"]
    assert (
        cfg.rag_thresholds(db).red_critical_gaps == 3
        and cfg.thresholds(db)["calendar_horizon_days"] == 60
    )
    ref = client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()
    assert (
        ref["rag_rule"]["red"] == r.json()["rag_rule"]["red"]
        and ref["thresholds"]["rag"]["red_lens_below"] == 40
    )
    event = _audit_last(db, "config:thresholds")
    assert (
        event.before["rag"]["red_critical_gaps"] == 2
        and event.after["rag"]["red_critical_gaps"] == 3
    )
    assert "immediately" in r.json()["notice"]


def test_threshold_guardrails(client, headers, fresh_seed) -> None:
    h = _h(headers)

    def put(**rag):
        doc = _thresholds(client, headers)
        extra = rag.pop("extra", {})
        doc["rag"].update(rag)
        doc.update(extra)
        return client.put(f"{API}/admin/thresholds", json={"thresholds": doc}, headers=h)

    assert put(amber_critical_gaps=5).status_code == 422  # amber stricter than red (2)
    assert put(amber_lens_below=30).status_code == 422
    assert put(red_lens_below=101).status_code == 422  # range
    assert put(red_near_days=400).status_code == 422
    assert put(extra={"default_tier": 9}).status_code == 422  # not a defined tier
    assert put(extra={"default_pricing_basis": "Barter"}).status_code == 422
    assert (
        put(extra={"default_tier": 2, "default_pricing_basis": "Fixed (contract)"}).status_code
        == 200
    )
    assert (
        _thresholds(client, headers)["rag"]["red_critical_gaps"] == 2
    )  # failed saves changed nothing


def test_tiering_wording(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    cfgdoc = client.get(f"{API}/admin/tiering", headers=h).json()
    assert [q["id"] for q in cfgdoc["questions"]] == ["TQ1", "TQ2", "TQ3", "TQ4", "TQ5"]
    body = {
        "tiers": [
            {k: t[k] for k in ("tier", "name", "definition", "examples", "builder_persona")}
            for t in cfgdoc["tiers"]
        ],
        "questions": [
            {"id": q["id"], "text": q["text"], "hint": q["hint"]} for q in cfgdoc["questions"]
        ],
    }
    body["tiers"][0]["name"] = "Light touch"
    body["questions"][0]["text"] = "Does it talk to customers directly?"
    body["questions"][0]["hint"] = "Pushes the tier up"
    r = client.put(f"{API}/admin/tiering", json=body, headers=h)
    assert r.status_code == 200, r.text
    ref = client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()
    assert ref["tiers"][0]["name"] == "Light touch"
    assert ref["tier_questions"][0] == {
        "id": "TQ1",
        "text": "Does it talk to customers directly?",
        "if_yes": "Pushes the tier up",
    }
    assert [t["tier"] for t in ref["tiers"]] == [1, 2, 3, 4]
    assert cfg.tier_questions(db)[0].hint == "Pushes the tier up"
    assert (
        _audit_last(db, "config:tiering")
        .after["questions"]["TQ1"]["text"]
        .startswith("Does it talk")
    )
    # tiers and questions cannot be added or removed: the rules (BR-011) are in code
    extra_tier = {**body, "tiers": [*body["tiers"], {"tier": 5, "name": "Tier 5"}]}
    assert client.put(f"{API}/admin/tiering", json=extra_tier, headers=h).status_code == 422
    assert (
        client.put(
            f"{API}/admin/tiering", json={**body, "tiers": body["tiers"][:3]}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"{API}/admin/tiering", json={**body, "questions": body["questions"][:4]}, headers=h
        ).status_code
        == 422
    )
    new_question = {**body, "questions": [*body["questions"], {"id": "TQ6", "text": "New?"}]}
    assert client.put(f"{API}/admin/tiering", json=new_question, headers=h).status_code == 422
    empty = {**body, "questions": [{**body["questions"][0], "text": ""}, *body["questions"][1:]]}
    assert client.put(f"{API}/admin/tiering", json=empty, headers=h).status_code == 422


def test_eval_metrics_add_edit_deactivate(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    metrics = client.get(f"{API}/admin/eval-metrics", headers=h).json()
    next_id = f"EV-{max(int(m['id'][3:]) for m in metrics) + 1:02d}"
    targets = {str(t): f">= {90 + t}%" for t in (1, 2, 3, 4)}
    r = client.post(
        f"{API}/admin/eval-metrics",
        json={
            "metric": "Answer accuracy",
            "evaluation": "auto",
            "operator": ">=",
            "value": 90,
            "unit": "%",
            "targets_by_tier": targets,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert (
        r.json()["id"] == next_id and r.json()["targets_by_tier"] == targets and r.json()["active"]
    )
    grid = client.get(f"{API}/admin/eval-targets", headers=h).json()
    new = next(m for m in grid["metrics"] if m["metric_id"] == next_id)
    assert [t["tier"] for t in new["tiers"]] == [1, 2, 3, 4] and new["tiers"][0]["operator"] == ">="
    # validation
    bad_tiers = {**{"metric": "x", "targets_by_tier": {"1": "a"}}}
    assert client.post(f"{API}/admin/eval-metrics", json=bad_tiers, headers=h).status_code == 422
    assert (
        client.post(
            f"{API}/admin/eval-metrics",
            json={
                "metric": "x",
                "evaluation": "auto",
                "targets_by_tier": {tier: "high" for tier in targets},
            },
            headers=h,
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/admin/eval-metrics",
            json={"metric": "x", "operator": ">=", "value": 1, "targets_by_tier": targets},
            headers=h,
        ).status_code
        == 422
    )
    # edit and deactivate
    r = client.patch(
        f"{API}/admin/eval-metrics/{next_id}",
        json={"metric": "Accuracy", "unit": "pct", "active": False},
        headers=h,
    )
    assert (
        r.status_code == 200
        and r.json()["metric"] == "Accuracy"
        and r.json()["active"] is False
        and r.json()["unit"] == "pct"
    )
    assert (
        client.patch(
            f"{API}/admin/eval-metrics/EV-99", json={"active": False}, headers=h
        ).status_code
        == 404
    )
    manual = next(m for m in metrics if m["evaluation"] == "manual")
    to_auto = client.patch(
        f"{API}/admin/eval-metrics/{manual['id']}", json={"evaluation": "auto"}, headers=h
    )
    assert to_auto.status_code == 422
    event = _audit_last(db, "config:eval_metrics")
    assert (
        event.entity_id == next_id
        and event.before["active"] is True
        and event.after["active"] is False
    )


# --- reminders, approval chains, usage ---------------------------------------------------------------------------


def test_reminder_autonomy_is_only_lowered_and_r6_takes_items(
    client, headers, fresh_seed, db
) -> None:
    h = _h(headers)
    rules = {r["id"]: r for r in client.get(f"{API}/admin/reminder-rules", headers=h).json()}
    assert rules["R1"]["autonomous_eligible"] and not rules["R4"]["autonomous_eligible"]

    def put(rule: str, **changes):
        entry = {"id": rule, "enabled": rules[rule]["enabled"], "params": {}, **changes}
        return client.put(f"{API}/admin/reminder-rules", json={"rules": [entry]}, headers=h)

    r = put("R4", autonomous_eligible=True)
    assert r.status_code == 422 and "switched off" in r.json()["reasons"][0]
    assert put("R1", autonomous_eligible=False).status_code == 200
    assert put("R1", autonomous_eligible=True).status_code == 422  # and not back on
    after = {x["id"]: x for x in client.get(f"{API}/admin/reminder-rules", headers=h).json()}
    assert after["R1"]["autonomous_eligible"] is False
    assert _audit_last(db, "config:reminder_rules").after["autonomous_eligible"] is False
    ok = put("R6", params={"item_ids": ["FW-048", "FW-049"], "category": "Monitoring"})
    assert ok.status_code == 200
    r6 = next(x for x in ok.json() if x["id"] == "R6")
    assert r6["params"] == {"item_ids": ["FW-048", "FW-049"], "category": "Monitoring"}
    assert put("R6", params={"item_ids": ["NOPE-1"]}).status_code == 422
    assert put("R6", params={"item_ids": "FW-048"}).status_code == 422
    assert put("R6", params={"category": 5}).status_code == 422
    assert put("R1", params={"item_ids": ["FW-048"]}).status_code == 422  # R6 only
    assert put("R1", params={"days_before_decision": 0}).status_code == 422
    assert put("R1", params={"days_before_decision": 10}).status_code == 200


def test_approval_chain_labels_and_mock_flag(client, headers, fresh_seed) -> None:
    h = _h(headers)
    out = client.get(f"{API}/admin/approval-chains", headers=h).json()
    assert (
        "CISO_BISO" in out["roles"]
        and "ADMIN" not in out["roles"]
        and "LEADERSHIP" not in out["roles"]
        and "ORION" not in out["roles"]
    )
    chains = out["chains"]
    exc = next(c for c in chains if c["type"] == "EXCEPTION")
    assert [s["is_mock"] for s in exc["steps"]] == [False, True]
    exc["label"] = "Exception sign-off"
    exc["steps"][0]["label"] = "Risk owner"
    exc["steps"][0]["is_mock"] = True
    r = client.put(f"{API}/admin/approval-chains", json={"chains": [exc]}, headers=h)
    assert r.status_code == 200, r.text
    saved = next(c for c in r.json()["chains"] if c["type"] == "EXCEPTION")
    assert saved["label"] == "Exception sign-off" and saved["steps"][0]["label"] == "Risk owner"
    assert saved["steps"][0]["is_mock"] is True and saved["steps"][1]["is_mock"] is True
    assert (
        client.get(f"{API}/reference", headers={"X-Demo-User": "U01"}).json()[
            "approval_chain_labels"
        ]["EXCEPTION"]
        == "Exception sign-off"
    )
    exc["steps"][0]["role"] = "WIZARD"
    assert (
        client.put(f"{API}/admin/approval-chains", json={"chains": [exc]}, headers=h).status_code
        == 422
    )


def test_usage_counts(client, headers, fresh_seed) -> None:
    h = _h(headers)

    def usage(kind: str, key: str) -> dict:
        return client.get(f"{API}/admin/usage", params={"kind": kind, "key": key}, headers=h).json()

    assert usage("portfolio", "GCC")["count"] >= 1
    assert usage("role", "OR_FOCAL")["count"] == 2  # U01 + the test-only U02
    assert (
        usage("checklist", "AI_PLAYBOOK")["count"] == 1
    )  # the one project type that includes it (Agentic AI)
    assert usage("option", "regions:Nowhere")["count"] == 0
    assert usage("option", "severities:Critical")["count"] >= 1


def test_every_config_write_is_audited_by_a_human(client, headers, fresh_seed, db) -> None:
    h = _h(headers)
    before = db.query(AuditEvent).filter(AuditEvent.entity.like("config:%")).count()
    client.post(f"{API}/admin/checklists", json={"code": "X_LIST", "label": "x"}, headers=h)
    client.post(f"{API}/admin/portfolios", json={"name": "Zed", "code": "ZED"}, headers=h)
    client.post(f"{API}/admin/intake-fields", json={"label": "Zed field"}, headers=h)
    db.expire_all()
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity.like("config:%"))
        .order_by(AuditEvent.id)
        .all()
    )
    assert len(events) == before + 3
    assert all(e.actor_type == "Human" and e.actor_user_id == ADMIN for e in events[-3:])
    assert [e.entity for e in events[-3:]] == [
        "config:checklists",
        "config:portfolios",
        "config:intake_fields",
    ]
    assert db.get(IntakeField, "cf_zed_field") is not None
