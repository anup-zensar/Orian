"""CR-01 (workflow modules): values the Admin can change in "Forms & dropdowns", "Rules & thresholds"
and "People & permissions" now drive evidence, actions, risks, defects, OCET, the support model, the
dashboard, the control tower, approvals and the reminder rules. Each test changes the configuration
rows (what an Admin save does), calls ``cfg.invalidate()`` and checks the behaviour through the API.
"""

from __future__ import annotations

import io
from datetime import date

from sqlalchemy import select

from app.domain import cfg
from app.models import AppSetting, OptionItem, RolePermission
from app.rules import reminders as rm

API = "/api/v1"
T = "TR-0001"
TECH_ITEM = "S3-019"


def _add_option(db, list_key: str, value: str, sort_order: int = 99, **meta) -> None:
    db.add(
        OptionItem(
            list_key=list_key,
            value=value,
            label=value,
            meta=meta,
            active=True,
            sort_order=sort_order,
        )
    )
    db.commit()
    cfg.invalidate()


def _edit_option(db, list_key: str, value: str, **fields) -> OptionItem:
    row = db.scalars(
        select(OptionItem).where(OptionItem.list_key == list_key, OptionItem.value == value)
    ).one()
    for name, val in fields.items():
        setattr(row, name, val)
    db.commit()
    cfg.invalidate()
    return row


def _set_thresholds(db, **changes) -> None:
    row = db.get(AppSetting, "cfg.thresholds")
    value = dict(row.value or {}) if row else {}
    value.update(changes)
    if row is None:
        db.add(AppSetting(key="cfg.thresholds", value=value))
    else:
        row.value = value
    db.commit()
    cfg.invalidate()


def _evidence(client, headers, user="U10", file=True, **form):
    data = {"title": "Proof", "type": "Document", "item_id": TECH_ITEM, **form}
    files = {"file": ("proof.pdf", b"%PDF-1.4 x", "application/pdf")} if file else None
    return client.post(
        f"{API}/transitions/{T}/evidence", data=data, files=files, headers=headers(user)
    )


# --- evidence types ---------------------------------------------------------------------------------
def test_new_evidence_type_follows_its_needs(client, headers, db, fresh_seed):
    assert _evidence(client, headers, type="Screenshot").status_code == 422  # not on the list yet
    _add_option(db, "evidence_types", "Screenshot", needs="file", system=False)
    res = _evidence(client, headers, type="Screenshot")
    assert res.status_code == 201, res.text
    assert res.json()["type"] == "Screenshot" and res.json()["has_file"] is True
    # needs=file also accepts a link instead of a file
    assert _evidence(client, headers, file=False, type="Screenshot").status_code == 422
    link = _evidence(client, headers, file=False, type="Screenshot", url="https://x.example/a.png")
    assert link.status_code == 201 and link.json()["has_file"] is False


def test_needs_decides_what_is_required_and_system_types_are_refused(
    client, headers, db, fresh_seed
):
    _edit_option(db, "evidence_types", "Recording", meta={"needs": "text", "system": False})
    res = _evidence(client, headers, file=False, type="Recording")
    assert res.status_code == 422 and "needs the e-mail text" in " ".join(res.json()["reasons"])
    ok = _evidence(client, headers, file=False, type="Recording", text="Signed off by mail")
    assert ok.status_code == 201 and ok.json()["text"] == "Signed off by mail"
    generated = _evidence(client, headers, type="Generated")
    assert generated.status_code == 422
    assert "created by the system only" in " ".join(generated.json()["reasons"])


def test_a_retired_evidence_type_is_no_longer_offered(client, headers, db, fresh_seed):
    _edit_option(db, "evidence_types", "Link", active=False)
    res = _evidence(client, headers, file=False, type="Link", url="https://x.example")
    assert res.status_code == 422 and "no longer offered" in " ".join(res.json()["reasons"])


# --- priorities, ratings ----------------------------------------------------------------------------
def _action(client, headers, **changes):
    body = {"title": "Do it", "item_ids": [], "owner_user_id": "U11", "due_date": "2026-11-20"}
    return client.post(
        f"{API}/transitions/{T}/actions", json={**body, **changes}, headers=headers("U10")
    )


def test_action_priorities_follow_the_list(client, headers, db, fresh_seed):
    assert _action(client, headers, priority="Urgent").status_code == 422
    _add_option(db, "action_priorities", "Urgent", sort_order=0)
    assert _action(client, headers, priority="Urgent").status_code == 201
    assert _action(client, headers, priority="Nonsense").status_code == 422
    # no priority given = the middle option of the active list (High, Medium, Low -> Medium)
    _edit_option(db, "action_priorities", "Urgent", active=False)
    assert _action(client, headers).json()["priority"] == "Medium"


def test_risk_ratings_and_defect_priorities_follow_the_lists(client, headers, db, fresh_seed):
    risk = {"title": "Vendor", "rating": "Severe", "decision": "", "item_ids": []}
    assert (
        client.post(f"{API}/transitions/{T}/risks", json=risk, headers=headers()).status_code == 422
    )
    _add_option(db, "risk_ratings", "Severe", sort_order=-1)
    assert (
        client.post(f"{API}/transitions/{T}/risks", json=risk, headers=headers()).status_code == 201
    )
    rows = client.get(f"{API}/transitions/{T}/risks", headers=headers()).json()
    assert rows[0]["rating"] == "Severe"  # the first value of the list sorts first

    defect = {"title": "Crash", "priority": "P5"}
    url = f"{API}/transitions/{T}/defects"
    assert client.post(url, json=defect, headers=headers("U01")).status_code == 422
    _add_option(db, "defect_priorities", "P5", sort_order=10)
    assert client.post(url, json=defect, headers=headers("U01")).status_code == 201


def test_the_critical_severity_comes_from_the_list(db, fresh_seed) -> None:
    from app.domain import insights

    assert cfg.critical_severity(db) == "Critical"
    _edit_option(db, "severities", "Critical", meta={"rank": 1, "counts_as_critical": False})
    _edit_option(db, "severities", "Major", meta={"rank": 2, "counts_as_critical": True})
    assert cfg.critical_severity(db) == "Major"
    _edit_option(db, "severities", "Critical", sort_order=50)  # last on the list
    rank = insights._severity_rank(db)
    assert rank["Critical"] > rank["Minor"]  # gaps are sorted by the list order, not by name


# --- thresholds, operating rhythm ------------------------------------------------------------------------
def test_dashboard_limits_come_from_the_thresholds(client, headers, db, fresh_seed):
    before = client.get(f"{API}/dashboard", headers=headers("U01")).json()
    assert before["my_work_total"] > 1 and len(before["my_work"]) == before["my_work_total"]
    _set_thresholds(db, dashboard={"my_work_limit": 1, "recent_activity_limit": 2})
    after = client.get(f"{API}/dashboard", headers=headers("U01")).json()
    assert len(after["my_work"]) == 1 and after["my_work_total"] == before["my_work_total"]
    assert len(after["recent_activity"]) <= 2


def test_control_tower_calendar_horizon_and_operating_rhythm(client, headers, db, fresh_seed):
    wide = client.get(f"{API}/control-tower", headers=headers("U15")).json()
    assert [r["forum"] for r in wide["operating_rhythm"]][0] == "OR team stand-up"
    assert wide["operating_rhythm"][0]["frequency"] == "Weekly"
    _set_thresholds(db, calendar_horizon_days=0)
    _edit_option(db, "operating_rhythm", "OR team stand-up", label="Daily huddle")
    narrow = client.get(f"{API}/control-tower", headers=headers("U15")).json()
    assert all(e["days"] <= 0 for e in narrow["calendar"])
    assert len(narrow["calendar"]) < len(wide["calendar"])
    assert narrow["operating_rhythm"][0]["forum"] == "Daily huddle"


# --- permissions instead of role names -------------------------------------------------------------------
def test_approvals_scope_all_follows_the_permission(client, headers, db, fresh_seed):
    url = f"{API}/approvals"
    assert client.get(url, params={"scope": "all"}, headers=headers("U16")).status_code == 200
    assert client.get(url, params={"scope": "all"}, headers=headers("U15")).status_code == 403
    db.query(RolePermission).filter_by(perm="view_all_approvals", role_code="ADMIN").delete()
    db.add(RolePermission(perm="view_all_approvals", role_code="LEADERSHIP"))
    db.commit()
    cfg.invalidate()
    assert client.get(url, params={"scope": "all"}, headers=headers("U16")).status_code == 403
    assert client.get(url, params={"scope": "all"}, headers=headers("U15")).status_code == 200


def test_dashboard_view_follows_the_see_all_permission(client, headers, db, fresh_seed):
    assert client.get(f"{API}/dashboard", headers=headers("U15")).json()["portfolio_tiles"]
    db.query(RolePermission).filter_by(perm="see_all_transitions", role_code="LEADERSHIP").delete()
    db.commit()
    cfg.invalidate()
    plain = client.get(f"{API}/dashboard", headers=headers("U15")).json()
    assert plain["portfolio_tiles"] == []  # no longer the portfolio-wide view


# --- OCET lists ------------------------------------------------------------------------------------------
def _ocet_line(body, **changes):
    line = next(ln for ln in body["lines"] if ln["line_key"] == "L6")
    out = {
        "id": line["id"],
        "line_key": line["line_key"],
        "category": line["category"],
        "description": line["description"],
        "vendor": line["vendor"],
        "pricing_basis": line["pricing_basis"],
        "base_amount": line["base_amount"],
        "growth_pct": line["growth_pct"],
        "year_overrides": line["year_overrides"],
        "override_reason": line["override_reason"],
        "input_owner_role": line["input_owner_role"],
        "input_owner_user_id": line["input_owner"]["id"] if line["input_owner"] else None,
        "input_status": line["input_status"],
    }
    return {**out, **changes}


def _save_ocet(client, headers, body, **changes):
    return client.put(
        f"{API}/ocet/versions/{body['version']['id']}/lines",
        json={"lines": [_ocet_line(body, **changes)], "deleted_line_ids": []},
        headers=headers("U01"),
    )


def test_ocet_categories_and_pricing_follow_the_lists(client, headers, db, fresh_seed):
    body = client.get(f"{API}/transitions/{T}/ocet", headers=headers("U01")).json()
    assert _save_ocet(client, headers, body, category="Security tooling").status_code == 422
    _add_option(db, "ocet_categories", "Security tooling", default_growth_pct=7)
    assert _save_ocet(client, headers, body, category="Security tooling").status_code == 200
    again = client.get(f"{API}/transitions/{T}/ocet", headers=headers("U01")).json()
    assert "Security tooling" in again["categories"]
    assert again["default_growth_pct"]["Security tooling"] == 7
    assert _save_ocet(client, headers, again, pricing_basis="Per seat").status_code == 422
    _add_option(db, "ocet_pricing_basis", "Per seat")
    assert _save_ocet(client, headers, again, pricing_basis="Per seat").status_code == 200


def test_a_retired_category_stays_valid_on_the_line_that_has_it(client, headers, db, fresh_seed):
    body = client.get(f"{API}/transitions/{T}/ocet", headers=headers("U01")).json()
    current = next(ln["category"] for ln in body["lines"] if ln["line_key"] == "L6")
    _edit_option(db, "ocet_categories", current, active=False)
    assert _save_ocet(client, headers, body, base_amount=123.0).status_code == 200  # unchanged
    other = next(c for c in body["categories"] if c != current)
    assert _save_ocet(client, headers, body, category=other).status_code == 200
    back = _save_ocet(client, headers, body, category=current)
    assert back.status_code == 422  # a new choice must be on offer


def test_new_estimate_uses_the_first_active_currency_and_horizon(client, headers, db, fresh_seed):
    _edit_option(db, "ocet_currencies", "USD", active=False)
    _set_thresholds(db, default_horizon_years=3)
    res = client.post(f"{API}/transitions/TR-0014/ocet", headers=headers("U01"))
    assert res.status_code == 201, res.text
    assert res.json()["estimate"]["currency"] == "EUR"
    assert res.json()["estimate"]["horizon_years"] == 3


# --- support model lists -------------------------------------------------------------------------------------
def _landscape(client, headers):
    client.post(
        f"{API}/transitions/{T}/support-model/inputs",
        files=[("files", ("walk.txt", io.BytesIO(b"SFTP and SSO"), "text/plain"))],
        headers=headers("U01"),
    )
    res = client.post(f"{API}/transitions/{T}/support-model/generate", headers=headers("U01"))
    assert res.status_code == 200, res.text
    model = res.json()["support_model"]
    return model["id"], model["landscape"]


def test_support_relations_follow_the_list(client, headers, db, fresh_seed):
    sid, landscape = _landscape(client, headers)
    first = landscape["components"][0]

    def put(relation):
        bad = {**landscape, "components": [{**first, "relation": relation, "target": None}]}
        return client.put(
            f"{API}/support-models/{sid}", json={"landscape": bad}, headers=headers("U01")
        )

    assert put("peer").status_code == 422
    _add_option(db, "support_relations", "peer", color="brand")
    assert put("peer").status_code == 200


def test_support_file_kinds_follow_the_list(client, headers, db, fresh_seed):
    def upload(name):
        return client.post(
            f"{API}/transitions/{T}/support-model/inputs",
            files=[("files", (name, io.BytesIO(b"notes"), "text/plain"))],
            headers=headers("U01"),
        )

    assert upload("notes.md").status_code == 422
    row = _edit_option(db, "support_file_kinds", "transcript")
    row.meta = {"extensions": [*row.meta["extensions"], ".md"]}
    db.commit()
    cfg.invalidate()
    res = upload("notes.md")
    assert res.status_code == 200, res.text
    assert any(
        f["filename"] == "notes.md" and f["kind"] == "transcript"
        for f in res.json()["inputs"]["files"]
    )


# --- reminder rule R6 --------------------------------------------------------------------------------------------
def _fact(**changes) -> rm.TransitionFact:
    base = dict(
        transition_id="TR-1",
        name="Agent",
        current_gate="SG2",
        next_decision_gate="SG4_ATD",
        next_decision_date=date(2026, 12, 1),
        or_focal_user_id="U01",
        architect_user_id="U11",
        autonomous_mode=False,
        first_approver_role="OLM",
        open_approval_chain=False,
        support_model_exists=False,
        fw006_evidence_accepted=False,
    )
    return rm.TransitionFact(**{**base, **changes})


def _item(item_id: str, category: str = "") -> rm.ItemFact:
    return rm.ItemFact(
        transition_id="TR-1",
        item_id=item_id,
        title=f"Title {item_id}",
        owner_user_id=None,
        status="Not started",
        first_due_gate="SG2",
        gate_index=1,
        done_or_covered=False,
        category=category,
    )


def test_r6_uses_its_item_ids_and_category() -> None:
    items = [_item("FW-048"), _item("FW-049"), _item("X-1", "Observability"), _item("X-2")]
    default = rm.evaluate_r6(rm.RuleConfig("R6"), [_fact()], items)
    assert default[0].related_ids == ["FW-048", "FW-049"]  # the default FW-048..FW-054
    custom = rm.RuleConfig("R6", {"item_ids": ["X-2"], "category": "Observability"})
    (candidate,) = rm.evaluate_r6(custom, [_fact()], items)
    assert candidate.related_ids == ["X-1", "X-2"]
    assert [i["id"] for i in candidate.payload["items"]] == ["X-1", "X-2"]
    assert candidate.autonomous_eligible is False  # the ceiling: R6 is never autonomous


# --- pure rules take the lists as parameters ---------------------------------------------------------------------
def test_status_rules_use_the_severity_and_design_lists_they_are_given() -> None:
    from app.rules import status

    own = ("Blocker", "Minor")
    assert status.input_errors(lens="Business", gap_severity="Blocker", severities=own) == []
    (reason,) = status.input_errors(lens="Business", gap_severity="Critical", severities=own)
    assert reason == "Gap severity must be one of Blocker, Minor"
    reasons = status.rule_violations(
        lens="Business",
        status="Gap",
        gap_severity=None,
        note="x",
        design_effectiveness=None,
        na_reason=None,
        has_condition=True,
        severities=own,
    )
    assert reasons == ["'Gap' needs a gap severity (Blocker or Minor)"]
    # the defaults are the standard lists
    assert status.input_errors(lens="Business", gap_severity="Critical") == []


def test_gate_rules_use_the_critical_severity_they_are_given() -> None:
    from app.rules.gates import GateContext, GateItemFact, validate_decision

    gap = GateItemFact(
        item_id="K", lens="Technical", due_gate="SG4_ATD", status="Gap", gap_severity="Blocker"
    )
    ctx = GateContext(gate="SG4_ATD", gate_type="decision", items=[gap], critical_value="Blocker")
    text = "\n".join(validate_decision(ctx, "Approve", []).reasons)
    assert "Blocker gap K is open - only an approved exception can cover it" in text
    # with the standard critical value the same gap is an ordinary open item
    plain = GateContext(gate="SG4_ATD", gate_type="decision", items=[gap])
    assert "gap K is open - only an approved exception" not in "\n".join(
        validate_decision(plain, "Approve", []).reasons
    )


def test_orion_picks_the_evidence_type_by_what_it_needs(client, headers, db, fresh_seed):
    assert cfg.evidence_type_for(db, "url") == "Link"
    assert cfg.evidence_type_for(db, "text") == "Email sign-off"
    _edit_option(db, "evidence_types", "Link", active=False)
    _add_option(db, "evidence_types", "Web page", needs="url", system=False)
    assert cfg.evidence_type_for(db, "url") == "Web page"
    res = client.post(
        f"{API}/orion/chat",
        json={
            "message": "add evidence link https://x.example/a to S3-019",
            "context": {"transition_id": T},
        },
        headers=headers("U10"),
    )
    assert res.status_code == 200, res.text
    proposals = [m["proposal"] for m in res.json()["messages"] if m["type"] == "proposal"]
    assert proposals and proposals[0]["payload"]["type"] == "Web page"
