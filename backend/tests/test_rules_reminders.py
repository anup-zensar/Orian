"""Pure reminder rules R1-R7 and de-duplication (BR-060, spec 7.8)."""

from __future__ import annotations

from datetime import date, timedelta

from app.rules.constants import GATE_ORDER
from app.rules.reminders import (
    ActionFact,
    ItemFact,
    OcetLineFact,
    RuleConfig,
    StepFact,
    TransitionFact,
    dedupe,
    dedupe_key,
    evaluate_r1,
    evaluate_r2,
    evaluate_r3,
    evaluate_r4,
    evaluate_r5,
    evaluate_r6,
    evaluate_r7,
)

TODAY = date(2026, 11, 17)


def _t(**kw) -> TransitionFact:
    base = dict(
        transition_id="TR-1",
        name="Agent",
        current_gate="SG4_ATD",
        next_decision_gate="SG4_ATD",
        next_decision_date=TODAY + timedelta(days=10),
        or_focal_user_id="U01",
        architect_user_id="U11",
        autonomous_mode=False,
        first_approver_role="OLM",
        open_approval_chain=False,
        support_model_exists=False,
        fw006_evidence_accepted=False,
    )
    base.update(kw)
    return TransitionFact(**base)


def _i(item_id="FW-001", owner="U10", gate="SG4_ATD", done=False, tid="TR-1") -> ItemFact:
    return ItemFact(
        transition_id=tid,
        item_id=item_id,
        title=f"Title {item_id}",
        owner_user_id=owner,
        status="Complete" if done else "Not started",
        first_due_gate=gate,
        gate_index=GATE_ORDER[gate],
        done_or_covered=done,
    )


def _cfg(rid, **params) -> RuleConfig:
    return RuleConfig(rule_id=rid, params=params, today=TODAY)


def test_r1_one_digest_per_owner_with_cc_and_threshold():
    items = [
        _i("A", "U10"),
        _i("B", "U10"),
        _i("C", "U11"),
        _i("D", None),  # no owner -> OR focal
        _i("E", "U10", done=True),  # done: ignored
        _i("F", "U10", gate="SG6_ATO"),  # due after the current gate: ignored
    ]
    out = evaluate_r1(_cfg("R1", days_before_decision=14), [_t()], items)
    assert [c.recipient_user_id for c in out] == ["U01", "U10", "U11"]
    pm = next(c for c in out if c.recipient_user_id == "U10")
    assert pm.related_ids == ["A", "B"] and pm.cc_user_ids == ["U01"]
    assert pm.card == "reminder_digest" and pm.autonomous_eligible and pm.kind == "Reminder"
    assert pm.payload["days_to_decision"] == 10
    focal = next(c for c in out if c.recipient_user_id == "U01")
    assert focal.cc_user_ids == [] and focal.related_ids == ["D"]
    # outside the window, or no open items
    assert evaluate_r1(_cfg("R1", days_before_decision=5), [_t()], items) == []
    assert evaluate_r1(_cfg("R1"), [_t()], [_i(done=True)]) == []
    # an overdue decision date still qualifies
    late = _t(next_decision_date=TODAY - timedelta(days=3))
    assert len(evaluate_r1(_cfg("R1"), [late], items)) == 3


def test_r2_overdue_actions_only():
    def act(aid, due, status="Open", owner="U10"):
        return ActionFact("TR-1", aid, f"Do {aid}", owner, due, status)

    actions = [
        act("ACT-1", TODAY - timedelta(days=2)),
        act("ACT-2", TODAY),  # due today is not overdue
        act("ACT-3", TODAY - timedelta(days=9), status="Done"),
        act("ACT-4", TODAY - timedelta(days=1), status="Cancelled"),
        act("ACT-5", TODAY - timedelta(days=1), owner=None),
        act("ACT-6", None),
    ]
    out = evaluate_r2(_cfg("R2"), [_t()], actions)
    assert [c.subject_key for c in out] == ["ACT-1", "ACT-5"]
    assert out[0].kind == "Chaser" and out[0].payload["days_overdue"] == 2
    assert out[0].cc_user_ids == ["U01"] and out[1].recipient_user_id == "U01"
    assert out[1].cc_user_ids == [] and all(c.autonomous_eligible for c in out)


def test_r3_reminder_then_escalation():
    def step(age):
        return StepFact("TR-1", "APR-1", "7", "SG4_ATD", "U12", TODAY - timedelta(days=age))

    cfg = _cfg("R3", reminder_after_days=2, escalate_after_days=5)
    assert evaluate_r3(cfg, [_t()], [step(2)]) == []
    (remind,) = evaluate_r3(cfg, [_t()], [step(3)])
    assert remind.recipient_user_id == "U12" and remind.cc_user_ids == ["U01"]
    assert remind.subject_key == "7:remind" and remind.autonomous_eligible
    assert remind.payload["escalation"] is False and remind.related_ids == ["APR-1", "7"]
    both = evaluate_r3(cfg, [_t()], [step(6)])
    assert [c.subject_key for c in both] == ["7:remind", "7:escalate"]
    esc = both[1]
    assert esc.recipient_user_id == "U01" and esc.kind == "Chaser"
    assert esc.autonomous_eligible is False and esc.payload["escalation"] is True
    assert esc.payload["approver_user_id"] == "U12"


def test_r4_ready_for_gate():
    cfg = _cfg("R4")
    items = [_i("A", done=True), _i("B", done=True), _i("Z", gate="SG6_ATO")]  # Z is after the gate
    (c,) = evaluate_r4(cfg, [_t()], items)
    assert c.recipient_user_id == "U01" and c.kind == "Approval request"
    assert c.action == {"type": "request_approval", "gate": "SG4_ATD"}
    assert c.payload["subject"] == "Ready for SG4 (AtD) - request OLM approval"
    assert c.autonomous_eligible is False and c.subject_key == "ready:SG4_ATD"
    assert evaluate_r4(cfg, [_t()], [*items, _i("C")]) == []  # an open item blocks
    assert evaluate_r4(cfg, [_t(open_approval_chain=True)], items) == []
    assert evaluate_r4(cfg, [_t(next_decision_gate=None)], items) == []


def test_r5_stale_ocet_inputs_grouped_per_owner():
    def line(lid, owner, days):
        return OcetLineFact("TR-1", lid, f"Line {lid}", owner, TODAY - timedelta(days=days))

    lines = [line("1", "U10", 6), line("2", "U10", 9), line("3", "U10", 5), line("4", None, 7)]
    out = evaluate_r5(_cfg("R5", requested_for_days=5), [_t()], lines)
    assert [c.recipient_user_id for c in out] == ["U01", "U10"]
    pm = out[1]
    assert pm.related_ids == ["1", "2"] and pm.kind == "Input request"
    assert pm.payload["lines"][1]["days_requested"] == 9
    assert pm.subject_key == "ocet-inputs" and pm.autonomous_eligible
    assert out[0].related_ids == ["4"] and out[0].cc_user_ids == []


def test_r6_monitoring_requirements_only_at_sg2_with_architect():
    items = [_i("FW-048"), _i("FW-049"), _i("FW-001")]
    t = _t(current_gate="SG2")
    (c,) = evaluate_r6(_cfg("R6"), [t], items)
    assert c.recipient_user_id == "U11" and c.related_ids == ["FW-048", "FW-049"]
    assert c.autonomous_eligible is False and c.subject_key == "monitoring-reqs"
    assert evaluate_r6(_cfg("R6"), [_t()], items) == []
    assert evaluate_r6(_cfg("R6"), [_t(current_gate="SG2", architect_user_id=None)], items) == []


def test_r7_support_model_after_fw006_evidence():
    ok = _t(fw006_evidence_accepted=True)
    (c,) = evaluate_r7(_cfg("R7"), [ok])
    assert c.recipient_user_id == "U01" and c.payload["subject"] == "Create support model now?"
    assert c.autonomous_eligible is False and c.related_ids == ["FW-006"]
    assert evaluate_r7(_cfg("R7"), [_t()]) == []
    assert (
        evaluate_r7(_cfg("R7"), [_t(fw006_evidence_accepted=True, support_model_exists=True)]) == []
    )


def test_dedupe_key_and_dedupe():
    (a,) = evaluate_r7(_cfg("R7"), [_t(fw006_evidence_accepted=True)])
    key = dedupe_key(a)
    assert key == "R7|TR-1|U01|support-model"
    survivors, skipped = dedupe([a, a], set())
    assert survivors == [a] and skipped == 1
    assert dedupe([a], {key}) == ([], 1)
    long_key = dedupe_key(
        type(a)(**{**a.__dict__, "subject_key": "x" * 300}),  # truncated to the column size
    )
    assert len(long_key) <= 120
