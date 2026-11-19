"""CR-01: tiering wording and tier definitions come from configuration; the BR-011 rules do not.

The Admin edits the question wording, the hints and the tier cards (name, definition, examples, builder
persona). Which answers lead to which tier stays in ``app.rules.tiering`` (BR-011).
"""

from __future__ import annotations

import pytest

from app.domain import cfg
from app.models import AppSetting, TierQuestion
from app.rules.tiering import propose_tier, unknown_question_ids
from tests.config_helpers import API, new_transition

TIER_KEYS = ("tier", "name", "definition", "examples", "builder_persona")


def _edit_wording(client, headers, db, *, question=None, tier_name=None):
    """Change the wording of TQ1 and/or the name of Tier 2 the way the Admin screen does."""
    current = client.get(f"{API}/admin/tiering", headers=headers("U16")).json()
    tiers = [{k: t[k] for k in TIER_KEYS} for t in current["tiers"]]
    questions = [{k: q[k] for k in ("id", "text", "hint")} for q in current["questions"]]
    if question:
        questions[0]["text"] = question
    if tier_name:
        next(t for t in tiers if t["tier"] == 2)["name"] = tier_name
    res = client.put(
        f"{API}/admin/tiering",
        json={"tiers": tiers, "questions": questions},
        headers=headers("U16"),
    )
    if res.status_code == 501:  # write endpoint not built yet: store the same documents directly
        if question:
            db.get(TierQuestion, "TQ1").text = question
        if tier_name:
            db.merge(AppSetting(key="cfg.tiers", value=tiers))
        db.commit()
        cfg.invalidate()
    else:
        assert res.status_code == 200, res.text


def test_question_wording_comes_from_configuration(client, headers, db, fresh_seed):
    before = client.get(f"{API}/reference", headers=headers("U01")).json()["tier_questions"]
    assert [q["id"] for q in before] == ["TQ1", "TQ2", "TQ3", "TQ4", "TQ5"]
    assert before[0]["text"].startswith("Does the agent communicate directly with external parties")

    _edit_wording(client, headers, db, question="Does the agent talk to customers directly?")
    after = client.get(f"{API}/reference", headers=headers("U01")).json()["tier_questions"]
    assert after[0] == {**before[0], "text": "Does the agent talk to customers directly?"}
    assert after[1:] == before[1:]


def test_tier_definitions_come_from_configuration(client, headers, db, fresh_seed):
    _edit_wording(client, headers, db, tier_name="Medium risk (renamed)")
    body = {
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
        "answers": {"TQ4": True},
    }
    res = client.post(f"{API}/tiering/propose", json=body, headers=headers("U01"))
    assert res.status_code == 200, res.text
    assert res.json()["proposed_tier"] == 2
    assert res.json()["tier"]["name"] == "Medium risk (renamed)"


def test_the_proposal_follows_the_tier_card_of_the_transition(client, headers, db, fresh_seed):
    _edit_wording(client, headers, db, tier_name="Medium risk (renamed)")
    tid = new_transition(
        client,
        headers,
        project_type="Agentic AI",
        audience="Internal department",
        write_actions="No",
        sensitive_data="No",
    ).json()["id"]
    res = client.put(
        f"{API}/transitions/{tid}/tier", json={"answers": {"TQ4": True}}, headers=headers("U01")
    )
    assert res.status_code == 200, res.text
    assert res.json()["proposed_tier"] == 2
    assert res.json()["tier"]["name"] == "Medium risk (renamed)"


def test_br011_rules_are_unchanged_by_the_wording(client, headers, db, fresh_seed):
    _edit_wording(client, headers, db, question="Reworded", tier_name="Reworded tier")
    vectors = [
        (("Internal department", "No", "No", {"TQ4": True}), 2),
        (("Internal department", "No", "No", {"TQ5": True}), 1),
        (("Internal department", "No", "No", {"TQ2": True}), 4),
        (("Internal department", "No", "SOX / MC", {}), 4),
        (("External", "No", "No", {"TQ4": True}), 3),
        (("Internal department", "No", "No", {}), 3),
    ]
    for (audience, writes, sensitive, answers), tier in vectors:
        body = {
            "audience": audience,
            "write_actions": writes,
            "sensitive_data": sensitive,
            "answers": answers,
        }
        res = client.post(f"{API}/tiering/propose", json=body, headers=headers("U01"))
        assert res.json()["proposed_tier"] == tier, body
        assert propose_tier(audience, writes, sensitive, answers).tier == tier


def test_unknown_question_ids_are_checked_against_configuration(client, headers, fresh_seed):
    assert unknown_question_ids({"TQ1": True, "TQ9": True}) == ["TQ9"]  # default ids TQ1..TQ5
    assert unknown_question_ids({"TQ9": True}, known_ids=["TQ9"]) == []
    body = {
        "audience": None,
        "write_actions": None,
        "sensitive_data": None,
        "answers": {"TQ9": True},
    }
    res = client.post(f"{API}/tiering/propose", json=body, headers=headers("U01"))
    assert res.status_code == 422
    assert "Unknown tier question 'TQ9'" in res.json()["reasons"][0]


def test_confirm_refuses_a_tier_that_is_not_defined(client, headers, fresh_seed):
    tid = new_transition(
        client,
        headers,
        project_type="Agentic AI",
        audience="Internal department",
        write_actions="No",
        sensitive_data="No",
    ).json()["id"]
    client.put(
        f"{API}/transitions/{tid}/tier", json={"answers": {"TQ4": True}}, headers=headers("U01")
    )
    res = client.post(
        f"{API}/transitions/{tid}/tier/confirm",
        json={"tier": 7, "reason": "no such tier"},
        headers=headers("U14"),
    )
    assert res.status_code == 422
    assert "Tier 7 is not defined" in res.json()["reasons"][0]
    ok = client.post(
        f"{API}/transitions/{tid}/tier/confirm", json={"tier": 2}, headers=headers("U14")
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.parametrize("field", ["audience", "write_actions", "sensitive_data"])
def test_intake_values_for_tiering_must_be_active_options(client, headers, field):
    body = {"audience": None, "write_actions": None, "sensitive_data": None, "answers": {}}
    body[field] = "Nonsense"
    res = client.post(f"{API}/tiering/propose", json=body, headers=headers("U01"))
    assert res.status_code == 422
    assert f"{field} 'Nonsense' is not one of" in res.json()["reasons"][0]
