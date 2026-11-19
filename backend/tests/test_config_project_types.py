"""CR-01 acceptance A: a new project type is added by an Admin through configuration only.

"Security Review" gets its own checklist (SECURITY_PLAYBOOK), requires tiering, has no AI profile and no
eval metrics. U01 then creates, tiers and launches a transition of that type through the API; the
checklist and the readiness include FRAMEWORK, SECURITY_PLAYBOOK and COMMON items. No code changes.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from app.models import AuditEvent, PlaybookItem, Transition, TransitionItem
from tests.config_helpers import (
    API,
    add_checklist,
    add_item,
    add_project_type,
    new_transition,
)

TYPE = "Security Review"


def _configure(client, headers, db) -> bool:
    """The Admin's work: a checklist with three items and the project type that uses it."""
    api = add_checklist(client, headers, db, "SECURITY_PLAYBOOK", "Security playbook")
    add_item(client, headers, db, "SEC-001", "SECURITY_PLAYBOOK", "Threat model", gate="SG0")
    add_item(
        client, headers, db, "SEC-002", "SECURITY_PLAYBOOK", "Pen test report",
        gate="SG0", lens="Compliance",
    )  # fmt: skip
    add_item(
        client, headers, db, "SEC-003", "SECURITY_PLAYBOOK", "Security sign-off",
        gate="SG3", lens="Technical",
    )  # fmt: skip
    add_project_type(
        client,
        headers,
        db,
        TYPE,
        label="Security Review",
        checklists=["FRAMEWORK", "SECURITY_PLAYBOOK"],
        requires_tiering=True,
        has_ai_profile=False,
        has_eval_metrics=False,
        required_intake_fields=["audience"],
    )
    return api


def _sources(db, transition_id: str) -> Counter:
    db.expire_all()
    sources = {p.id: p.source for p in db.scalars(select(PlaybookItem))}
    rows = db.scalars(select(TransitionItem).where(TransitionItem.transition_id == transition_id))
    return Counter((sources[r.playbook_item_id], r.applicability) for r in rows)


def _lens_scope(detail: dict) -> dict[str, int]:
    return {card["lens"]: card["scope"] for card in detail["lenses"]}


def test_new_project_type_is_offered_on_intake(client, headers, db, fresh_seed):
    _configure(client, headers, db)
    ref = client.get(f"{API}/reference", headers=headers("U01")).json()
    new = next(p for p in ref["project_types"] if p["code"] == TYPE)
    assert new["checklists"] == ["FRAMEWORK", "SECURITY_PLAYBOOK"]
    assert new["requires_tiering"] is True
    assert new["has_ai_profile"] is False and new["has_eval_metrics"] is False
    assert "audience" in new["required_intake_fields"]


def test_new_type_enforces_its_required_intake_fields(client, headers, db, fresh_seed):
    _configure(client, headers, db)
    missing = new_transition(client, headers, project_type=TYPE)
    assert missing.status_code == 422
    assert missing.json()["reasons"] == ["Audience is required for Security Review"]
    ok = new_transition(client, headers, project_type=TYPE, audience="Enterprise")
    assert ok.status_code == 201, ok.text


def test_acceptance_a_security_review_end_to_end(client, headers, db, fresh_seed):
    used_api = _configure(client, headers, db)

    # A plain "Normal" transition is the baseline for the readiness comparison.
    normal = new_transition(client, headers, name="Baseline").json()["id"]
    assert client.post(f"{API}/transitions/{normal}/launch-assessment", headers=headers("U01"))
    baseline = client.get(f"{API}/transitions/{normal}", headers=headers("U01")).json()

    # U01 creates the Security Review transition.
    res = new_transition(
        client, headers, name="Pay app review", project_type=TYPE, audience="Enterprise"
    )
    assert res.status_code == 201, res.text
    detail = res.json()
    tid = detail["id"]
    assert detail["project_type"] == TYPE
    assert detail["requires_tiering"] is True
    assert detail["has_ai_profile"] is False and detail["has_eval_metrics"] is False

    # Tiering applies (the switch is on) ...
    tier = client.put(
        f"{API}/transitions/{tid}/tier", json={"answers": {"TQ4": True}}, headers=headers("U01")
    )
    assert tier.status_code == 200, tier.text
    confirm = client.post(
        f"{API}/transitions/{tid}/tier/confirm", json={"tier": 2}, headers=headers("U14")
    )
    assert confirm.status_code == 200, confirm.text
    # ... but the AI profile and the eval table do not.
    assert (
        client.get(f"{API}/transitions/{tid}/ai-profile", headers=headers("U01")).status_code == 409
    )
    assert (
        client.get(f"{API}/transitions/{tid}/eval-metrics", headers=headers("U01")).status_code
        == 409
    )

    launch = client.post(f"{API}/transitions/{tid}/launch-assessment", headers=headers("U01"))
    assert launch.status_code == 200, launch.text

    # The checklist: FRAMEWORK + SECURITY_PLAYBOOK + COMMON, no AI playbook, no golden set rows picked.
    counts = _sources(db, tid)
    sources = {source for source, _ in counts}
    assert {"FRAMEWORK", "SECURITY_PLAYBOOK", "COMMON"} <= sources
    assert "AI_PLAYBOOK" not in sources
    assert counts[("FRAMEWORK", "Applies")] == 72
    assert counts[("SECURITY_PLAYBOOK", "Applies")] == 3  # not tier filtered: every item applies
    assert launch.json()["counts"]["other"] == 3  # shown on the scope page as "other checklists"

    # Readiness: items of the new checklist count (due at the current gate SG0: Business and
    # Compliance one each; the SG3 Technical item is not in scope yet).
    after = client.get(f"{API}/transitions/{tid}", headers=headers("U01")).json()
    base_scope, new_scope = _lens_scope(baseline), _lens_scope(after)
    assert new_scope["Business"] == base_scope["Business"] + 1
    assert new_scope["Compliance"] == base_scope["Compliance"] + 1
    assert new_scope["Technical"] == base_scope["Technical"]
    assert after["item_counts"]["other"] == 3

    # Audit: the transition is audited as always; the configuration writes are audited when the
    # Admin API did them (actor Human, entity config:<section>).
    db.expire_all()
    created = db.scalars(
        select(AuditEvent).where(
            AuditEvent.transition_id == tid, AuditEvent.action == "Transition created"
        )
    ).all()
    assert len(created) == 1 and created[0].actor_type == "Human"
    if used_api:
        config_rows = db.scalars(select(AuditEvent).where(AuditEvent.entity.like("config:%"))).all()
        assert {e.entity for e in config_rows} >= {"config:project_types", "config:checklists"}
        assert all(e.actor_type == "Human" and e.actor_user_id == "U16" for e in config_rows)


def test_type_without_tiering_skips_the_tiering_step(client, headers, db, fresh_seed):
    add_project_type(
        client, headers, db, "Quick Check", label="Quick check", checklists=["FRAMEWORK"]
    )
    res = new_transition(client, headers, project_type="Quick Check")
    assert res.status_code == 201, res.text
    assert res.json()["requires_tiering"] is False
    tier = client.put(
        f"{API}/transitions/{res.json()['id']}/tier", json={"answers": {}}, headers=headers("U01")
    )
    assert tier.status_code == 409


def test_ai_profile_and_eval_follow_the_switches_not_the_name(client, headers, db, fresh_seed):
    add_project_type(
        client,
        headers,
        db,
        "Copilot Rollout",
        checklists=["FRAMEWORK", "AI_PLAYBOOK"],
        requires_tiering=True,
        has_ai_profile=True,
        has_eval_metrics=True,
        required_intake_fields=["audience", "write_actions", "sensitive_data"],
    )
    res = new_transition(
        client,
        headers,
        project_type="Copilot Rollout",
        audience="Internal department",
        write_actions="No",
        sensitive_data="No",
    )
    assert res.status_code == 201, res.text
    tid = res.json()["id"]
    assert res.json()["has_ai_profile"] is True and res.json()["has_eval_metrics"] is True
    assert (
        client.get(f"{API}/transitions/{tid}/ai-profile", headers=headers("U01")).status_code == 200
    )
    assert (
        client.get(f"{API}/transitions/{tid}/eval-metrics", headers=headers("U01")).status_code
        == 200
    )


def test_unknown_project_type_is_refused(client, headers, fresh_seed):
    res = new_transition(client, headers, project_type="Does not exist")
    assert res.status_code == 422
    assert any("Project type 'Does not exist'" in r for r in res.json()["reasons"])


def test_deactivated_type_stays_valid_on_old_transitions_only(client, headers, db, fresh_seed):
    from app.domain import cfg
    from app.models import FlavourRule

    add_project_type(client, headers, db, "Pilot", checklists=["FRAMEWORK"])
    tid = new_transition(client, headers, project_type="Pilot").json()["id"]
    db.expire_all()
    db.get(FlavourRule, "Pilot").active = False
    db.commit()
    cfg.invalidate()

    # New transitions can no longer pick it ...
    assert new_transition(client, headers, project_type="Pilot").status_code == 422
    # ... the old one keeps working and can be edited with its (unchanged) type.
    res = client.patch(
        f"{API}/transitions/{tid}",
        json={"project_type": "Pilot", "description": "still fine"},
        headers=headers("U01"),
    )
    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.get(Transition, tid).project_type == "Pilot"
