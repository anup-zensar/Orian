"""Seed loader (spec 11.2, AC-01, NFR-06) and the flagship records (spec 11.3 step 6)."""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from app import clock
from app import db as database
from app.config import get_settings
from app.models import (
    Action,
    AIProfile,
    ApprovalRequest,
    AppSetting,
    AuditEvent,
    Condition,
    EvalResult,
    EvalTarget,
    Evidence,
    ExceptionRecord,
    FlavourRule,
    GateReview,
    OcetEstimate,
    PlaybookItem,
    Portfolio,
    ReminderRule,
    Risk,
    TierAssessment,
    Transition,
    TransitionItem,
    User,
)
from app.seed.loader import reset_and_seed, seed_if_empty


def count(db, model, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def seed_json(name: str):
    with (Path(get_settings().seed_dir) / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def test_row_counts(db):
    portfolios = seed_json("portfolios.json")
    golden = sum(len(p["golden_set"]) for p in portfolios["portfolios"])
    assert count(db, User) == 9  # 8 seed users + the test-only U02
    assert count(db, Transition) == 6
    assert count(db, PlaybookItem, PlaybookItem.source == "FRAMEWORK") == 72
    assert count(db, PlaybookItem, PlaybookItem.source == "AI_PLAYBOOK") == 216
    assert count(db, PlaybookItem, PlaybookItem.source == "PORTFOLIO") == golden == 39
    assert count(db, PlaybookItem, PlaybookItem.source == "COMMON") == 2
    assert count(db, EvalTarget) == 152  # 38 metrics x tiers 1-4
    assert count(db, Portfolio) == 6
    assert count(db, FlavourRule) == 3
    assert count(db, ReminderRule) == 7
    ai_transitions = count(db, Transition, Transition.project_type.in_(["Agentic AI"]))
    assert count(db, TierAssessment) == ai_transitions == 2
    assert count(db, AIProfile) == ai_transitions


def test_library_mapping_and_linked_modules(db):
    fw = db.get(PlaybookItem, "FW-001")
    assert fw.title.startswith("IP (Investment Proposal)")
    assert fw.kind == "Deliverable" and fw.mandatory_rule == "always"
    assert fw.source_sheet == "Operate Readiness Framework"
    assert fw.owner_role_hint == "Project Team"
    assert fw.note == "SOM sign-off: NA"
    ai = db.get(PlaybookItem, "S45-014")
    assert ai.category.startswith("ATD") and ai.applicable_tiers == [2, 3, 4]
    portfolio_item = db.get(PlaybookItem, "GCC-01")
    assert portfolio_item.portfolio == "GCC" and portfolio_item.mandatory_rule is None
    assert portfolio_item.category == "Portfolio golden set"
    assert db.get(PlaybookItem, "ALL-02").mandatory_rule == "if_applicable"
    ocet = {
        i for i in db.scalars(select(PlaybookItem.id).where(PlaybookItem.linked_module == "OCET"))
    }
    assert ocet == {"FW-008", "S45-006"}
    support = set(
        db.scalars(select(PlaybookItem.id).where(PlaybookItem.linked_module == "SUPPORT_MODEL"))
    )
    assert {f"FW-{n:03d}" for n in range(27, 36)} <= support
    sm_compliance = db.scalars(
        select(PlaybookItem).where(
            PlaybookItem.source_sheet == "Support Model", PlaybookItem.lens == "Compliance"
        )
    ).all()
    assert all(i.linked_module is None for i in sm_compliance)


def test_transitions_dates_and_roles(db):
    today = clock.today()
    flagship = db.get(Transition, "TR-0001")
    assert today.isoformat() == "2026-11-16"
    assert flagship.next_decision_date == today + timedelta(days=21)
    assert flagship.irm_user_id == "U14"
    assert flagship.is_flagship and flagship.assessment_launched_at is not None
    assert flagship.audience == "Internal department" and flagship.write_actions == "No"
    assert flagship.sensitive_data == "No" and flagship.target_gate == "AtD"
    assert flagship.investment_type == "Change" and flagship.delivery_method == "AI / Agentic"
    assert flagship.description.startswith("Internal RAG agent")
    assert flagship.blocker_note == "IRM: data-classification control open"
    assert db.get(Transition, "TR-0005").blocker_note is None
    assert all(t.irm_user_id == "U14" for t in db.scalars(select(Transition)))
    assert count(db, Transition, Transition.is_flagship.is_(True)) == 1


def test_tier_assessments(db):
    flagship = db.scalars(
        select(TierAssessment).where(TierAssessment.transition_id == "TR-0001")
    ).one()
    assert flagship.proposed_tier == 2 and flagship.confirmed_tier == 2
    assert flagship.confirmed_by_or_focal == "U01" and flagship.confirmed_by_irm == "U14"
    assert flagship.answers["TQ4"] is True
    other = db.scalars(
        select(TierAssessment).where(TierAssessment.transition_id == "TR-0003")
    ).one()
    assert other.proposed_tier == other.confirmed_tier == 2  # A-06
    assert other.confirmed_by_irm == "U14" and other.answers == {}


def test_item_counts_per_flavour(db):
    def n(tid, *conditions):
        return count(db, TransitionItem, TransitionItem.transition_id == tid, *conditions)

    # Tier 2 Agentic AI flagship: 72 + 216 + 5 (GCC) + 2
    assert n("TR-0001") == 72 + 216 + 5 + 2
    assert n("TR-0001", TransitionItem.excluded_by == "tier") == 8
    # Normal (Fleets): framework + golden set + common only
    assert n("TR-0005") == 72 + 5 + 2
    assert n("TR-0005", TransitionItem.excluded_by.is_not(None)) == 0
    # A-29: nothing is left "To confirm" on seeded transitions
    assert count(db, TransitionItem, TransitionItem.applicability == "To confirm") == 0
    assert count(db, TransitionItem, TransitionItem.last_updated_source != "System") == 0


def test_seed_if_empty_is_idempotent(db):
    before = count(db, TransitionItem)
    assert seed_if_empty(db) is False
    assert count(db, TransitionItem) == before
    assert count(db, User) == 9


def test_reset_and_seed_fast_and_seed_if_empty_on_empty_db(fresh_seed):
    start = time.perf_counter()
    reset_and_seed()
    assert time.perf_counter() - start < 10  # NFR-06

    database.drop_all()
    database.create_all()
    with database.SessionLocal() as session:
        assert seed_if_empty(session) is True
        assert seed_if_empty(session) is False
        assert count(session, Transition) == 6
    clock.set_today_override(None)


def test_reset_clears_today_override(fresh_seed):
    clock.set_today_override(clock.today() + timedelta(days=40))
    reset_and_seed()
    assert clock.get_today_override() is None
    with database.SessionLocal() as session:
        assert session.get(Transition, "TR-0001").next_decision_date == clock.today() + timedelta(
            days=21
        )


def test_flagship_conditions_and_exception(db):
    conditions = {c.id: c for c in db.scalars(select(Condition))}
    assert set(conditions) == {"CON-001", "CON-002"}
    item_of = {
        c.id: db.get(TransitionItem, c.transition_item_id).playbook_item_id
        for c in conditions.values()
    }
    assert item_of == {"CON-001": "S3-019", "CON-002": "S02-012"}
    assert conditions["CON-001"].due_gate == "SG4_ATD" and conditions["CON-001"].status == "Open"
    assert conditions["CON-002"].owner_user_id == "U14"

    exception = db.get(ExceptionRecord, "EX-01")
    assert exception.status == "Pending CISO/BISO"
    assert db.get(TransitionItem, exception.transition_item_id).playbook_item_id == "S45-014"
    approval = db.get(ApprovalRequest, "APR-0001")
    assert exception.approval_request_id == approval.id
    assert approval.type == "EXCEPTION" and approval.status == "Pending"
    first, second = approval.steps
    assert (first.step, first.role, first.approver_user_id, first.status) == (
        1,
        "IRM",
        "U14",
        "Pending",
    )
    assert first.activated_at is not None
    assert clock.now() - first.activated_at >= timedelta(hours=23)
    assert (second.step, second.role, second.approver_user_id, second.status) == (
        2,
        "CISO_BISO",
        None,
        "Waiting",
    )


def test_flagship_risks(db):
    seed_ids = [
        r.id
        for r in db.scalars(select(Risk).where(Risk.transition_id == "TR-0001").order_by(Risk.id))
    ]
    assert seed_ids[:4] == ["CR-01", "CR-02", "CR-03", "CR-04"]
    assert len(seed_ids) == 5  # + the blocker risk
    blocker_risk = db.get(Risk, "CR-05")
    assert blocker_risk.title == "IRM: data-classification control open"
    assert blocker_risk.rating == "High" and blocker_risk.decision == "Escalated"
    assert blocker_risk.item_ids == ["S45-014"]
    # every transition with a blocker has exactly one blocker risk; ids are unique and continue
    blockers = [
        t["snapshot"]["blocker"]
        for t in seed_json("sample_transitions.json")["transitions"]
        if t["snapshot"]["blocker"]
    ]
    assert count(db, Risk) == 4 + len(blockers)
    ids = sorted(r.id for r in db.scalars(select(Risk)))
    assert ids == [f"CR-{n:02d}" for n in range(1, 4 + len(blockers) + 1)]
    for risk in db.scalars(select(Risk).where(Risk.decision == "Escalated")):
        assert risk.rating == "High" and len(risk.item_ids) == 1


def test_flagship_gate_history_actions_evidence(db):
    today = clock.today()
    reviews = {r.gate: r for r in db.scalars(select(GateReview).order_by(GateReview.id))}
    assert list(reviews) == ["SG0", "SG2", "SG3"]
    assert [reviews[g].gate_type for g in reviews] == ["stage_review"] * 3
    assert [(reviews[g].decided_at.date() - today).days for g in reviews] == [-120, -75, -30]
    assert reviews["SG0"].decided_by == "U14" and reviews["SG3"].decided_by == "U01"
    assert reviews["SG0"].conditions_created == []
    assert reviews["SG2"].conditions_created == ["CON-002"]
    assert reviews["SG3"].conditions_created == ["CON-001"]

    actions = {a.id: a for a in db.scalars(select(Action))}
    assert set(actions) == {"ACT-001", "ACT-002", "ACT-003"}
    assert [(actions[i].due_date - today).days for i in sorted(actions)] == [5, 7, 3]
    assert [actions[i].priority for i in sorted(actions)] == ["High", "Medium", "High"]
    assert all(a.origin == "Human" and a.created_by == "U01" for a in actions.values())
    assert actions["ACT-002"].status == "In progress"

    evidence = {e.id: e for e in db.scalars(select(Evidence))}
    assert set(evidence) == {"EVD-001", "EVD-002", "EVD-003"}
    items = {k: db.get(TransitionItem, e.transition_item_id) for k, e in evidence.items()}
    assert [items[k].playbook_item_id for k in sorted(items)] == ["FW-006", "FW-012", "S45-015"]
    for key, ev in evidence.items():
        assert ev.submitted_by == items[key].owner_user_id
        lens = items[key].playbook_item.lens
        if ev.status == "Accepted":
            assert ev.reviewed_by == ("U14" if lens == "Compliance" else "U01")
        else:
            assert ev.reviewed_by is None
    assert evidence["EVD-003"].status == "Submitted"


def test_seeded_evidence_files_download(client, headers):
    """The sample files in seed/files are copied to storage, so each seeded document opens."""
    for eid, name, magic in [
        ("EVD-001", "walkthrough.wav", b"RIFF"),
        ("EVD-002", "IAQ.pdf", b"%PDF"),
        ("EVD-003", "pi-controls.docx", b"PK"),
    ]:
        res = client.get(f"/api/v1/evidence/{eid}/download", headers=headers())
        assert res.status_code == 200, (eid, res.text)
        assert res.content.startswith(magic)
        assert res.content == (Path(get_settings().seed_dir) / "files" / name).read_bytes()
        assert name in res.headers["content-disposition"]


def test_flagship_eval_results_exactly_two_fail(db):
    results = {r.metric_id: r for r in db.scalars(select(EvalResult))}
    assert len(results) == 13
    failing = sorted(m for m, r in results.items() if r.passed is False)
    assert failing == ["EV-03", "EV-12"]
    assert all(r.passed is True for m, r in results.items() if m not in failing)
    assert all(r.source == "Imported (mock)" for r in results.values())
    assert results["EV-03"].value_number == 3.1


def test_flagship_ocet(db):
    estimate = db.scalars(select(OcetEstimate)).one()
    assert estimate.transition_id == "TR-0001" and estimate.current_version == 2
    assert (estimate.currency, estimate.start_year, estimate.horizon_years) == ("USD", 2027, 5)
    v1, v2 = estimate.versions
    assert (v1.version, v1.status) == (1, "Superseded")
    assert (v2.version, v2.status) == (2, "Inputs pending")
    assert [ln.line_key for ln in v1.lines] == ["L1", "L2", "L3", "L4", "L5"]
    assert [ln.line_key for ln in v2.lines] == ["L1", "L2", "L3", "L4", "L5", "L6"]
    assert next(ln for ln in v1.lines if ln.line_key == "L2").year_overrides == {}
    l2 = next(ln for ln in v2.lines if ln.line_key == "L2")
    assert l2.year_overrides == {"2028": 30} and l2.override_reason
    l6 = next(ln for ln in v2.lines if ln.line_key == "L6")
    assert l6.base_amount is None and l6.input_status == "Requested"
    assert l6.input_owner_user_id == "U11"  # ARCHITECT -> the transition's architect
    assert clock.now() - l6.input_requested_at >= timedelta(hours=47)
    assert next(ln for ln in v2.lines if ln.line_key == "L3").input_owner_user_id == "U10"  # PM


def test_audit_events_seeded(db):
    seeded = db.scalars(select(AuditEvent).where(AuditEvent.action == "seeded")).all()
    assert len(seeded) == 7
    per_transition = [e for e in seeded if e.entity == "Transition"]
    assert len(per_transition) == 6
    assert {e.transition_id for e in per_transition} == {
        f"TR-{n:04d}" for n in (1, 3, 5, 8, 11, 14)
    }
    assert all(e.actor_type == "System" and e.note == "Seeded" for e in per_transition)
    assert Counter(e.entity for e in seeded)["System"] == 1


def test_config_seed_matches_the_simplified_admin(db):
    """CR-01 simplification: no tier-rule table, no custom role slots, no label / gate / lens documents."""
    assert "tier_rules" not in database.Base.metadata.tables
    assert not hasattr(Transition, "role_assignments")
    keys = set(db.scalars(select(AppSetting.key).where(AppSetting.key.like("cfg.%"))))
    assert keys == {
        "cfg.thresholds",
        "cfg.gate_chain",
        "cfg.mock_approver",
        "cfg.tiers",
        "cfg.tier_dimensions",
    }
    assert count(db, User, User.active.is_(True)) == count(db, User) == 9
    conf = seed_json("config.json")
    assert "tier_rules" not in conf and not {"cfg.gates", "cfg.labels", "cfg.lenses"} & set(
        conf["settings"]
    )


def test_sample_custom_fields_and_dates_are_loaded(db):
    """CR-03: sample transitions carry project status / tier and AtD / AtO dates (days from today)."""
    today = clock.today()
    for src in seed_json("sample_transitions.json")["transitions"]:
        stored = db.get(Transition, src["id"]).custom_fields
        for key, value in src["custom_fields"].items():
            assert stored[key] == value
        for key, days in src["custom_dates_days"].items():
            assert stored[key] == (today + timedelta(days=days)).isoformat()
