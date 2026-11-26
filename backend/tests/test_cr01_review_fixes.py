"""Regression tests for the CR-01 review findings (guardrails an Admin could get around)."""

from __future__ import annotations

from app.domain.audit_text import describe_event
from app.domain.config_admin import _parse_target, check_reserved_words
from app.models import AuditEvent, Transition

API = "/api/v1"
ITEM_KEYS = ("value", "label", "description", "meta", "active")


def _admin(headers):
    return headers("U16")


def _severity_body(client, headers):
    url = f"{API}/admin/option-lists/severities/items"
    items = client.get(url, headers=_admin(headers)).json()["items"]
    return url, [{k: i[k] for k in ITEM_KEYS} for i in items]


def test_critical_severity_cannot_be_recoded_while_gaps_hold_it(client, headers, fresh_seed):
    url, body = _severity_body(client, headers)
    critical = next(row for row in body if row["meta"].get("counts_as_critical"))
    critical["value"] = "Critical2"
    res = client.put(url, json={"items": body}, headers=_admin(headers))
    assert res.status_code == 422, res.text
    assert "critical severity" in " ".join(res.json()["reasons"])


def test_option_values_differing_only_by_case_are_refused(client, headers, fresh_seed):
    url, body = _severity_body(client, headers)
    body.append({"value": body[0]["value"].lower(), "label": "x", "meta": {}})
    res = client.put(url, json={"items": body}, headers=_admin(headers))
    assert res.status_code == 422


def test_slash_is_not_allowed_in_type_code_or_portfolio_name(client, headers, fresh_seed):
    res = client.post(f"{API}/admin/project-types", json={"code": "Q/R"}, headers=_admin(headers))
    assert res.status_code == 422
    res = client.post(
        f"{API}/admin/portfolios", json={"name": "Fuels/EU", "code": "FEU"}, headers=_admin(headers)
    )
    assert res.status_code == 422


def test_approval_chain_cannot_use_admin_or_leadership_or_be_too_long(client, headers, fresh_seed):
    url = f"{API}/admin/approval-chains"
    for role in ("ADMIN", "LEADERSHIP"):
        chain = {"type": "AtD", "steps": [{"step": 1, "label": "L", "role": role}]}
        res = client.put(url, json={"chains": [chain]}, headers=_admin(headers))
        assert res.status_code == 422, role
    steps = [{"step": n, "label": f"S{n}", "role": "IRM"} for n in range(1, 10)]
    res = client.put(
        url, json={"chains": [{"type": "AtD", "steps": steps}]}, headers=_admin(headers)
    )
    assert res.status_code == 422
    assert "at most" in " ".join(res.json()["reasons"])


def test_role_change_and_deactivation_need_a_replacement(client, headers, fresh_seed):
    res = client.patch(f"{API}/admin/users/U01", json={"role": "PM"}, headers=_admin(headers))
    assert res.status_code == 422
    assert "open transitions" in " ".join(res.json()["reasons"])
    res = client.post(f"{API}/admin/users/U01/deactivate", json={}, headers=_admin(headers))
    assert res.status_code == 422
    res = client.post(
        f"{API}/admin/users/U01/deactivate", json={"reassign_to": "U02"}, headers=_admin(headers)
    )
    assert res.status_code == 200, res.text


def test_custom_text_is_limited_and_must_be_text(client, headers, fresh_seed):
    made = client.post(
        f"{API}/admin/intake-fields",
        json={"label": "Note", "type": "text"},
        headers=_admin(headers),
    )
    assert made.status_code == 201, made.text
    patch = f"{API}/transitions/TR-0001"
    for bad in ("y" * 5000, {"a": [1]}, ["a"]):
        res = client.patch(patch, json={"custom_fields": {"cf_note": bad}}, headers=headers("U01"))
        assert res.status_code == 422, bad
    res = client.patch(patch, json={"custom_fields": {"cf_note": "fine"}}, headers=headers("U01"))
    assert res.status_code == 200, res.text


def test_reserved_word_look_alikes_are_caught():
    for name in ("0rion", "Ōrion", "O-r-i-o-n", "Orion bot"):
        assert check_reserved_words("Name", name), name
    assert not check_reserved_words("Name", "Daniel Gaines")
    assert not check_reserved_words("Name", "Asha Menon")


def test_focal_label_and_title_cannot_be_called_orion(client, headers, fresh_seed):
    for field in ("focal_label", "title"):
        res = client.patch(
            f"{API}/admin/users/U10", json={field: "Orion agent"}, headers=_admin(headers)
        )
        assert res.status_code == 422, field


def test_template_markup_and_duplicate_keys(client, headers, fresh_seed):
    listed = client.get(f"{API}/admin/message-templates", headers=_admin(headers)).json()
    first = listed[0] if isinstance(listed, list) else listed["templates"][0]
    one = {k: first[k] for k in ("key", "subject", "body", "enabled")}
    url = f"{API}/admin/message-templates"
    res = client.put(url, json={"templates": [one, one]}, headers=_admin(headers))
    assert res.status_code == 422
    svg = {**one, "body": "<svg/onload=alert(1)>x"}
    res = client.put(url, json={"templates": [svg]}, headers=_admin(headers))
    assert res.status_code == 422


def test_required_field_cannot_be_hidden_and_retiring_drops_the_requirement(
    client, headers, fresh_seed
):
    res = client.patch(
        f"{API}/admin/intake-fields/audience", json={"visible": False}, headers=_admin(headers)
    )
    assert res.status_code == 422, res.text
    assert "AI Transition" in " ".join(res.json()["reasons"])
    checklist = client.get(f"{API}/admin/checklists", headers=_admin(headers)).json()[0]["code"]
    made = client.post(
        f"{API}/admin/project-types",
        json={"code": "Privacy Review", "checklists": [checklist]},
        headers=_admin(headers),
    )
    assert made.status_code == 201, made.text
    made = client.post(
        f"{API}/admin/intake-fields",
        json={
            "label": "Data region",
            "type": "text",
            "required_mode": "by_project_type",
            "required_for_project_types": ["Privacy Review"],
        },
        headers=_admin(headers),
    )
    assert made.status_code == 201, made.text
    res = client.patch(
        f"{API}/admin/intake-fields/cf_data_region",
        json={"active": False},
        headers=_admin(headers),
    )
    assert res.status_code == 200, res.text
    types = client.get(f"{API}/admin/project-types", headers=_admin(headers)).json()
    privacy = next(t for t in types if t["code"] == "Privacy Review")
    assert "cf_data_region" not in privacy["required_intake_fields"]


def test_automatic_metric_target_is_read_from_the_tier_texts(client, headers, fresh_seed):
    assert _parse_target("<= 5%") == ("<=", 5.0, "%")
    assert _parse_target("be nice") is None
    texts = {"1": "<= 5%", "2": "<= 3%", "3": "<= 2%", "4": "<= 1%"}
    url = f"{API}/admin/eval-metrics"
    res = client.post(
        url,
        json={"metric": "Toxicity rate", "evaluation": "auto", "targets_by_tier": texts},
        headers=_admin(headers),
    )
    assert res.status_code == 201, res.text
    bad = client.post(
        url,
        json={"metric": "Bad", "evaluation": "auto", "targets_by_tier": {**texts, "1": "low"}},
        headers=_admin(headers),
    )
    assert bad.status_code == 422


def test_reminder_edits_are_audited_as_config(client, headers, db, fresh_seed):
    rules = client.get(f"{API}/admin/reminder-rules", headers=_admin(headers)).json()
    rules[0]["enabled"] = not rules[0]["enabled"]
    res = client.put(f"{API}/admin/reminder-rules", json={"rules": rules}, headers=_admin(headers))
    assert res.status_code == 200, res.text
    entities = {e.entity for e in db.query(AuditEvent).all()}
    assert "config:reminder_rules" in entities
    assert "ReminderRule" not in entities


def test_approval_labels_use_agreement_wording():
    from app.domain import approvals

    labels = " ".join(str(v) for v in vars(approvals).values() if isinstance(v, dict))
    assert "Agreement to Deploy" in labels
    assert "Authority to" not in labels


def test_audit_summary_uses_item_id_and_draft_subject():
    assert (
        describe_event("TransitionItem", "271", "updated", {}, "S45-014 - bulk update")
        == "Updated checklist item S45-014"
    )
    assert (
        describe_event("OrionDraft", "1", "drafted", {"subject": "Evidence chaser"}, "")
        == 'Drafted Orion draft "Evidence chaser"'
    )


def test_dashboard_user_has_the_role_label(client, headers):
    me = client.get(f"{API}/dashboard", headers=headers("U01")).json()["user"]
    assert me["role_label"]


def test_locked_status_lists_show_real_usage(client, headers):
    res = client.get(
        f"{API}/admin/option-lists/evidence_statuses/items", headers=_admin(headers)
    ).json()
    assert sum(i["used_by"] for i in res["items"]) > 0


def test_flagship_transition_is_still_seeded(db):
    assert db.get(Transition, "TR-0001") is not None
