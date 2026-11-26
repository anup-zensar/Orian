"""CR-01: intake fields from configuration - labels, required-per-project-type and custom fields.

Custom fields (the form section "Additional details") are stored in ``Transition.custom_fields``,
validated by their type, required per project type, shown in the transition detail and filterable
with ``GET /transitions?cf_<key>=value``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domain import cfg
from app.models import AuditEvent, IntakeField, Transition
from tests.config_helpers import API, add_custom_field, new_transition


def _create(client, headers, custom=None, **overrides):
    body = {"custom_fields": custom} if custom is not None else {}
    return new_transition(client, headers, **body, **overrides)


def test_custom_field_of_every_type_is_stored_and_shown(client, headers, db, fresh_seed):
    add_custom_field(client, headers, db, "cf_note", "Short note", "text", max_length=20)
    add_custom_field(client, headers, db, "cf_story", "Story", "textarea")
    add_custom_field(client, headers, db, "cf_cost", "Cost (EUR)", "number", min=0, max=1000)
    add_custom_field(client, headers, db, "cf_review_on", "Review date", "date")
    add_custom_field(
        client, headers, db, "cf_mode", "Write mode", "select", option_list="write_actions"
    )
    add_custom_field(
        client, headers, db, "cf_users", "Audiences", "multiselect", option_list="audience"
    )
    add_custom_field(client, headers, db, "cf_urgent", "Urgent", "boolean")
    add_custom_field(client, headers, db, "cf_buddy", "Buddy PM", "user", option_list="PM")

    values = {
        "cf_note": "  hello  ",
        "cf_story": "A longer story",
        "cf_cost": 12.5,
        "cf_review_on": "2026-12-01",
        "cf_mode": "Yes",
        "cf_users": ["Enterprise", "External"],
        "cf_urgent": True,
        "cf_buddy": "U10",
    }
    res = _create(client, headers, values)
    assert res.status_code == 201, res.text
    expected = {**values, "cf_note": "hello"}
    assert res.json()["custom_fields"] == expected

    db.expire_all()
    assert db.get(Transition, res.json()["id"]).custom_fields == expected
    got = client.get(f"{API}/transitions/{res.json()['id']}", headers=headers("U01")).json()
    assert got["custom_fields"] == expected


@pytest.mark.parametrize(
    ("key", "value", "fragment"),
    [
        ("cf_note", "x" * 21, "longer than 20"),
        ("cf_cost", -1, "at least 0"),
        ("cf_cost", 5000, "at most 1000"),
        ("cf_cost", "abc", "must be a number"),
        ("cf_review_on", "01/12/2026", "must be a date"),
        ("cf_mode", "Sometimes", "is not one of"),
        ("cf_urgent", "yes", "Yes or No"),
        ("cf_buddy", "U11", "does not have the PM role"),
        ("cf_buddy", "U99", "unknown user"),
        ("cf_missing", "x", "not an additional detail field"),
    ],
)
def test_custom_values_are_validated_by_type(client, headers, db, fresh_seed, key, value, fragment):
    add_custom_field(client, headers, db, "cf_note", "Short note", "text", max_length=20)
    add_custom_field(client, headers, db, "cf_cost", "Cost (EUR)", "number", min=0, max=1000)
    add_custom_field(client, headers, db, "cf_review_on", "Review date", "date")
    add_custom_field(
        client, headers, db, "cf_mode", "Write mode", "select", option_list="write_actions"
    )
    add_custom_field(client, headers, db, "cf_urgent", "Urgent", "boolean")
    add_custom_field(client, headers, db, "cf_buddy", "Buddy PM", "user", option_list="PM")
    res = _create(client, headers, {key: value})
    assert res.status_code == 422
    assert any(fragment in r for r in res.json()["reasons"]), res.json()["reasons"]


def test_custom_field_required_for_one_project_type(client, headers, db, fresh_seed):
    add_custom_field(
        client,
        headers,
        db,
        "cf_cost_centre",
        "Cost centre",
        "text",
        required_mode="by_project_type",
        required_for_project_types=["Normal"],
    )
    missing = _create(client, headers, project_type="Normal")
    assert missing.status_code == 422
    assert missing.json()["reasons"] == ["Cost centre is required for Standard Transition"]
    assert _create(client, headers, {"cf_cost_centre": "CC-42"}).status_code == 201
    # other project types are not asked
    assert _create(client, headers, project_type="Infrastructure").status_code == 201


def test_field_that_does_not_apply_to_the_portfolio_is_never_required(
    client, headers, db, fresh_seed
):
    add_custom_field(
        client,
        headers,
        db,
        "cf_permit",
        "Permit number",
        "text",
        required_mode="always",
        applies_to_portfolios=["Telecoms"],
    )
    assert _create(client, headers, portfolio="GCC").status_code == 201
    assert _create(client, headers, portfolio="Telecoms").status_code == 422


def test_patch_merges_clears_and_audits_custom_fields(client, headers, db, fresh_seed):
    add_custom_field(client, headers, db, "cf_note", "Short note", "text")
    add_custom_field(client, headers, db, "cf_urgent", "Urgent", "boolean")
    tid = _create(client, headers, {"cf_note": "one", "cf_urgent": True}).json()["id"]

    res = client.patch(
        f"{API}/transitions/{tid}",
        json={"custom_fields": {"cf_note": "two"}},
        headers=headers("U01"),
    )
    assert res.status_code == 200, res.text
    assert res.json()["custom_fields"] == {"cf_note": "two", "cf_urgent": True}  # merged

    res = client.patch(
        f"{API}/transitions/{tid}",
        json={"custom_fields": {"cf_urgent": None}},
        headers=headers("U01"),
    )
    assert res.json()["custom_fields"] == {"cf_note": "two"}  # blank clears

    db.expire_all()
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.action == "Transition updated"
        )
    ).all()
    assert len(events) == 2 and all(e.actor_type == "Human" for e in events)
    assert "custom_fields" in events[0].note
    assert events[0].after["custom_fields"] == {"cf_note": "two", "cf_urgent": True}


def test_only_the_owning_or_focal_edits_custom_fields(client, headers, db, fresh_seed):
    add_custom_field(client, headers, db, "cf_note", "Short note", "text")
    tid = _create(client, headers, {"cf_note": "one"}).json()["id"]
    other = client.patch(
        f"{API}/transitions/{tid}", json={"custom_fields": {"cf_note": "x"}}, headers=headers("U02")
    )
    assert other.status_code == 403
    admin = client.patch(
        f"{API}/transitions/{tid}", json={"custom_fields": {"cf_note": "x"}}, headers=headers("U16")
    )
    assert admin.status_code == 403  # R-01: the Admin configures, never edits workflow data


def test_retired_custom_field_refuses_new_values_but_keeps_old_ones(
    client, headers, db, fresh_seed
):
    add_custom_field(client, headers, db, "cf_note", "Short note", "text")
    tid = _create(client, headers, {"cf_note": "kept"}).json()["id"]
    db.get(IntakeField, "cf_note").active = False
    db.commit()
    cfg.invalidate()

    refused = client.patch(
        f"{API}/transitions/{tid}",
        json={"custom_fields": {"cf_note": "new"}},
        headers=headers("U01"),
    )
    assert refused.status_code == 422
    got = client.get(f"{API}/transitions/{tid}", headers=headers("U01")).json()
    assert got["custom_fields"] == {"cf_note": "kept"}  # stored values stay visible


def test_register_filters_on_custom_fields(client, headers, db, fresh_seed):
    add_custom_field(
        client,
        headers,
        db,
        "cf_region_team",
        "Team",
        "select",
        option_list="audience",
        filterable=True,
    )
    add_custom_field(client, headers, db, "cf_urgent", "Urgent", "boolean", filterable=True)
    add_custom_field(
        client, headers, db, "cf_users", "Audiences", "multiselect", option_list="audience"
    )
    a = _create(
        client,
        headers,
        {"cf_region_team": "Enterprise", "cf_urgent": True, "cf_users": ["External", "Enterprise"]},
        name="A",
    ).json()["id"]
    b = _create(
        client, headers, {"cf_region_team": "External", "cf_urgent": False}, name="B"
    ).json()["id"]
    c = _create(client, headers, name="C").json()["id"]

    def ids(**params):
        res = client.get(f"{API}/transitions", params=params, headers=headers("U15"))
        assert res.status_code == 200, res.text
        return {row["id"] for row in res.json()}

    assert ids(cf_region_team="Enterprise") == {a}
    assert ids(cf_region_team="External") == {b}
    assert ids(cf_urgent="true") == {a}
    assert ids(cf_urgent="false") == {b}
    assert ids(cf_users="External") == {a}  # a multiselect matches when it contains the value
    assert ids(cf_region_team="Enterprise", cf_urgent="false") == set()  # AND
    assert {a, b, c} <= ids()  # no filter: everything (plus the seeded transitions)
    assert ids(cf_region_team="Nobody") == set()


def test_built_in_field_labels_come_from_configuration(client, headers, db, fresh_seed):
    db.get(IntakeField, "audience").label = "Who will use it"
    db.commit()
    cfg.invalidate()
    res = _create(
        client, headers, project_type="Agentic AI", write_actions="No", sensitive_data="No"
    )
    assert res.status_code == 422
    assert res.json()["reasons"] == ["Who will use it is required for AI Transition"]


def test_required_fields_default_to_todays_behaviour(client, headers, fresh_seed):
    for project_type in ("Agentic AI",):
        res = _create(client, headers, project_type=project_type)
        assert res.status_code == 422
        assert len(res.json()["reasons"]) == 3
    assert _create(client, headers, project_type="Normal").status_code == 201
