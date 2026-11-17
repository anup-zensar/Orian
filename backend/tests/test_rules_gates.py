"""Gate rules matrix (BR-040, spec 7.5 / 7.6, AC-08). Pure rule tests, no database."""

from __future__ import annotations

from app.rules.gates import (
    ConditionFact,
    ConditionInput,
    FailedEval,
    GateContext,
    GateItemFact,
    carried_items,
    evaluate_verdict,
    validate_decision,
    validate_stage_review,
)


def item(item_id: str, lens: str = "Business", status: str = "In progress", due: str = "SG3", **kw):
    return GateItemFact(item_id=item_id, lens=lens, due_gate=due, status=status, **kw)


def ctx(gate: str, items=(), **kw) -> GateContext:
    gate_type = {
        "SG4_ATD": "decision",
        "SG6_ATO": "decision",
        "CLOSURE": "closure",
    }.get(gate, "stage_review")
    return GateContext(gate=gate, gate_type=gate_type, items=list(items), **kw)


def cond(item_id: str, due: str = "SG4_ATD", owner: str | None = "U01", text: str = "do it"):
    return ConditionInput(item_id, owner, due, text)


# --- stage reviews -----------------------------------------------------------------------------


def test_hold_is_always_allowed():
    c = ctx("SG3", [item("A"), item("C1", "Compliance")], ai_flavour=True, tier_confirmed=False)
    assert validate_stage_review(c, "Hold", []).allowed


def test_proceed_needs_no_uncovered_open_items():
    c = ctx("SG3", [item("A"), item("B", status="Complete")])
    res = validate_stage_review(c, "Proceed", [])
    assert not res.allowed and "1 open item(s) due by SG3 are not covered (A)" in res.reasons[0]
    assert validate_stage_review(ctx("SG3", [item("B", status="Complete")]), "Proceed", []).allowed


def test_proceed_ignores_items_covered_by_condition_or_approved_exception():
    c = ctx(
        "SG2",
        [
            item("A", due="SG2", covered_by_condition=True),
            item("B", "Compliance", "Non-compliant", due="SG2", under_approved_exception=True),
        ],
    )
    assert validate_stage_review(c, "Proceed", []).allowed


def test_pending_exception_still_blocks():
    c = ctx(
        "SG2",
        [item("X", "Compliance", "Non-compliant", due="SG2", under_pending_exception=True)],
    )
    assert not validate_stage_review(c, "Proceed", []).allowed


def test_proceed_with_conditions_requires_condition_per_business_technical_item():
    c = ctx("SG3", [item("A"), item("T", "Technical", "Gap")])
    ok = validate_stage_review(c, "Proceed with conditions", [cond("A"), cond("T")])
    assert ok.allowed, ok.reasons
    missing = validate_stage_review(c, "Proceed with conditions", [cond("A")])
    assert not missing.allowed and any("without a condition: T" in r for r in missing.reasons)


def test_condition_rules_owner_text_due_gate_and_duplicates():
    c = ctx("SG3", [item("A")])
    assert any(
        "needs an owner" in r
        for r in validate_stage_review(
            c, "Proceed with conditions", [cond("A", owner=None)]
        ).reasons
    )
    assert any(
        "due gate must be after SG3" in r
        for r in validate_stage_review(c, "Proceed with conditions", [cond("A", due="SG3")]).reasons
    )
    assert any(
        "unknown due gate" in r
        for r in validate_stage_review(c, "Proceed with conditions", [cond("A", due="XX")]).reasons
    )
    assert any(
        "needs a text" in r
        for r in validate_stage_review(c, "Proceed with conditions", [cond("A", text=" ")]).reasons
    )
    dup = validate_stage_review(c, "Proceed with conditions", [cond("A"), cond("A")])
    assert any("More than one condition for A" in r for r in dup.reasons)


def test_conditions_rejected_for_unknown_done_or_covered_items():
    c = ctx(
        "SG3",
        [item("A"), item("D", status="Complete"), item("V", covered_by_condition=True)],
    )
    res = validate_stage_review(
        c, "Proceed with conditions", [cond("A"), cond("D"), cond("V"), cond("ZZ")]
    )
    assert not res.allowed
    text = " ".join(res.reasons)
    assert "D rejected" in text and "V rejected" in text and "ZZ rejected" in text


def test_proceed_with_conditions_compliance_needs_approved_exception_at_sg2():
    c = ctx("SG2", [item("A", due="SG2"), item("C", "Compliance", "Non-compliant", due="SG2")])
    res = validate_stage_review(c, "Proceed with conditions", [cond("A", due="SG3")])
    assert not res.allowed
    assert "Compliance item C is open - only an approved exception can cover it" in res.reasons
    # conditioning a compliance item is rejected as well
    res2 = validate_stage_review(
        c, "Proceed with conditions", [cond("A", due="SG3"), cond("C", due="SG3")]
    )
    assert any("Compliance items cannot be conditioned" in r for r in res2.reasons)


def test_proceed_with_conditions_nothing_to_condition():
    res = validate_stage_review(ctx("SG3", []), "Proceed with conditions", [])
    assert not res.allowed


def test_sg3_compliance_items_never_block_a_sg3_rule():
    c = ctx("SG3", [item("C", "Compliance", "Non-compliant", due="SG3"), item("A")])
    # Compliance does not block and needs no condition
    assert validate_stage_review(c, "Proceed with conditions", [cond("A")]).allowed
    only_c = ctx("SG3", [item("C", "Compliance", "Non-compliant", due="SG3")])
    assert validate_stage_review(only_c, "Proceed", []).allowed
    assert evaluate_verdict(only_c).verdict == "Ready"


def test_compliance_blocks_at_sg2():
    only_c = ctx("SG2", [item("C", "Compliance", "In review", due="SG2")])
    assert not validate_stage_review(only_c, "Proceed", []).allowed
    assert evaluate_verdict(only_c).verdict == "Not ready"


def test_sg0_needs_confirmed_tier_for_ai_flavours():
    c = ctx("SG0", [], ai_flavour=True, tier_confirmed=False)
    for outcome in ("Proceed", "Proceed with conditions"):
        res = validate_stage_review(c, outcome, [])
        assert not res.allowed
        assert "Tier must be confirmed by IRM before SG0 can proceed" in res.reasons
    assert validate_stage_review(ctx("SG0", [], ai_flavour=True), "Proceed", []).allowed
    assert validate_stage_review(
        ctx("SG0", [], ai_flavour=False, tier_confirmed=False), "Proceed", []
    ).allowed
    assert evaluate_verdict(c).verdict == "Not ready"


def test_critical_gap_is_not_a_hard_stop_at_stage_review():
    c = ctx("SG3", [item("A", "Technical", "Gap", gap_severity="Critical")])
    res = validate_stage_review(c, "Proceed with conditions", [cond("A")])
    assert res.allowed, res.reasons
    assert evaluate_verdict(c).verdict == "Ready with conditions"


def test_unknown_outcome_and_wrong_gate_type():
    assert not validate_stage_review(ctx("SG3"), "Approve", []).allowed
    assert not validate_stage_review(ctx("SG4_ATD"), "Proceed", []).allowed


# --- decision gates ----------------------------------------------------------------------------


def atd(items=(), **kw) -> GateContext:
    kw.setdefault("chain_status", "Approved")
    return ctx("SG4_ATD", items, **kw)


def test_return_always_allowed():
    c = atd([item("A", due="SG4_ATD")], chain_status=None)
    assert validate_decision(c, "Return", []).allowed
    assert validate_decision(ctx("CLOSURE", [item("A", due="CLOSURE")]), "Return", []).allowed


def test_approve_requires_chain_approved():
    clean = [item("A", status="Complete", due="SG4_ATD")]
    none = validate_decision(atd(clean, chain_status=None), "Approve", [])
    assert not none.allowed and "Approval has not been requested yet" in none.reasons
    pending = validate_decision(
        atd(clean, chain_status="Pending", chain_pending_step="OLM approval"), "Approve", []
    )
    assert "Approval chain is not approved yet (OLM approval step pending)" in pending.reasons
    rejected = validate_decision(atd(clean, chain_status="Rejected"), "Approve", [])
    assert not rejected.allowed
    assert validate_decision(atd(clean), "Approve", []).allowed
    assert not validate_decision(
        atd(clean, chain_status="Pending"),
        "Approve with conditions",
        [cond("A", due="SG5_HYPERCARE")],
    ).allowed


def test_approve_blocks_on_open_items_critical_compliance_and_failed_evals():
    items = [
        item("B1", due="SG4_ATD"),
        item("K", "Technical", "Gap", due="SG4_ATD", gap_severity="Critical"),
        item("C", "Compliance", "Non-compliant", due="SG4_ATD"),
    ]
    fe = [FailedEval("EV-03", "Hallucination rate", "3.1%", "≤ 2%")]
    res = validate_decision(atd(items, failed_evals=fe, ai_flavour=True), "Approve", [])
    text = "\n".join(res.reasons)
    assert not res.allowed
    assert "Critical gap K is open" in text
    assert "Compliance item C is open" in text
    assert "Eval metric below target: Hallucination rate 3.1% vs ≤ 2%" in text
    assert "open item(s) due by AtD are not covered (B1, K)" in text


def test_approve_with_conditions_allows_business_technical_only():
    items = [item("B1", due="SG4_ATD"), item("T1", "Technical", "Gap", due="SG4_ATD")]
    c = atd(items)
    ok = validate_decision(
        c, "Approve with conditions", [cond("B1", "SG5_HYPERCARE"), cond("T1", "SG6_ATO")]
    )
    assert ok.allowed, ok.reasons
    assert not validate_decision(
        c, "Approve with conditions", [cond("B1", "SG5_HYPERCARE")]
    ).allowed
    bad_due = validate_decision(
        c, "Approve with conditions", [cond("B1", "SG4_ATD"), cond("T1", "SG6_ATO")]
    )
    assert any("due gate must be after AtD" in r for r in bad_due.reasons)


def test_approve_with_conditions_still_blocked_by_critical_compliance_eval():
    fe = [FailedEval("EV-12", "Prompt-injection resistance", "84%", "≥ 90%")]
    crit = item("K", "Technical", "Gap", due="SG4_ATD", gap_severity="Critical")
    c = atd(
        [crit, item("C", "Compliance", "Non-compliant", due="SG4_ATD")],
        failed_evals=fe,
        ai_flavour=True,
    )
    res = validate_decision(c, "Approve with conditions", [cond("K", "SG6_ATO")])
    text = "\n".join(res.reasons)
    assert not res.allowed
    assert (
        "Critical gap K" in text
        and "Compliance item C" in text
        and "Eval metric below target" in text
    )
    assert "Critical gap cannot be covered by a condition" in text.replace(
        "a Critical", "a Critical"
    )


def test_critical_gap_covered_only_by_approved_exception():
    crit = item(
        "K",
        "Compliance",
        "Non-compliant",
        due="SG4_ATD",
        gap_severity="Critical",
        under_approved_exception=True,
    )
    assert validate_decision(atd([crit]), "Approve", []).allowed
    cov = item(
        "K2", "Technical", "Gap", due="SG4_ATD", gap_severity="Critical", covered_by_condition=True
    )
    res = validate_decision(atd([cov]), "Approve", [])
    assert not res.allowed and any("Critical gap K2" in r for r in res.reasons)


def test_evals_only_block_at_atd_and_only_for_ai_flavours():
    fe = [FailedEval("EV-03", "Hallucination rate", "3.1%", "≤ 2%")]
    non_ai = atd([], failed_evals=fe, ai_flavour=False)
    assert validate_decision(non_ai, "Approve", []).allowed
    ato = ctx("SG6_ATO", [], failed_evals=fe, ai_flavour=True, chain_status="Approved")
    assert validate_decision(ato, "Approve", []).allowed
    assert not validate_decision(atd([], failed_evals=fe, ai_flavour=True), "Approve", []).allowed


def test_unevaluated_evals_are_warnings_only():
    c = atd([], ai_flavour=True, unevaluated_evals=3)
    assert validate_decision(c, "Approve", []).allowed
    v = evaluate_verdict(c)
    assert v.verdict == "Ready" and any("3 eval metric(s)" in w for w in v.warnings)


def test_ato_extras_block_both_approve_variants():
    c = ctx(
        "SG6_ATO",
        [],
        chain_status="Approved",
        open_p1_p2=1,
        tracker_in_place=False,
        atd_conditions_open=2,
        ocet_approved=False,
        support_model_agreed=False,
    )
    for d in ("Approve", "Approve with conditions"):
        res = validate_decision(c, d, [])
        text = "\n".join(res.reasons)
        assert not res.allowed
        for needle in ("P1/P2", "tracker", "AtD condition", "OCET", "Support model"):
            assert needle in text
    ok = ctx("SG6_ATO", [], chain_status="Approved")
    assert validate_decision(ok, "Approve", []).allowed
    assert evaluate_verdict(c).verdict == "Not ready"
    assert len(evaluate_verdict(c).hard_reasons) == 5


def test_closure_rules():
    done = ctx("CLOSURE", [item("A", status="Complete", due="CLOSURE")])
    assert validate_decision(done, "Close", []).allowed
    assert validate_decision(done, "Return", []).allowed
    assert not validate_decision(done, "Approve", []).allowed
    assert not validate_decision(done, "Close", [cond("A", "CLOSURE")]).allowed
    busy = ctx(
        "CLOSURE",
        [item("A", due="CLOSURE", covered_by_condition=True)],
        open_conditions_due=["CON-9"],
        open_actions=2,
        open_defects=1,
    )
    res = validate_decision(busy, "Close", [])
    text = "\n".join(res.reasons)
    assert not res.allowed
    assert "open condition" in text and "open action" in text and "open defect" in text
    assert "not covered" in text  # a condition does not cover items at closure
    assert evaluate_verdict(busy).verdict == "Not ready"


# --- verdict -----------------------------------------------------------------------------------


def test_verdict_levels_and_blocking_order():
    c = atd(
        [
            item("T2", "Technical", due="SG4_ATD"),
            item("B2", due="SG4_ATD"),
            item("T1", "Technical", "Gap", due="SG4_ATD", gap_severity="Critical"),
            item("B1", due="SG4_ATD"),
        ]
    )
    v = evaluate_verdict(c)
    assert [b.item_id for b in v.blocking] == ["B1", "B2", "T1", "T2"]
    assert v.verdict == "Not ready"  # critical gap
    no_crit = atd([item("B1", due="SG4_ATD")])
    assert evaluate_verdict(no_crit).verdict == "Ready with conditions"
    assert evaluate_verdict(atd([item("A", status="N/A", due="SG4_ATD")])).verdict == "Ready"


def test_items_due_after_gate_are_out_of_scope():
    c = ctx("SG3", [item("L", due="SG4_ATD")])
    assert evaluate_verdict(c).verdict == "Ready"


def test_failed_evals_are_technical_blockers_with_reason_and_pending_exceptions_listed():
    fe = [FailedEval("EV-03", "Hallucination rate", "3.1%", "≤ 2%")]
    c = atd(
        [
            item(
                "C",
                "Compliance",
                "Non-compliant",
                due="SG4_ATD",
                gap_severity="Critical",
                under_pending_exception=True,
                exception_ref="EX-01",
            ),
        ],
        failed_evals=fe,
        ai_flavour=True,
    )
    v = evaluate_verdict(c)
    ev = [b for b in v.blocking if b.item_id == "EV-03"][0]
    assert ev.lens == "Technical"
    assert ev.reason == "Eval metric below target: Hallucination rate 3.1% vs ≤ 2%"
    comp = [b for b in v.blocking if b.item_id == "C"][0]
    assert comp.reason == "Non-compliant (Critical); exception EX-01 pending"
    assert any("EX-01" in w for w in v.warnings)
    assert [b.item_id for b in v.critical_gaps] == ["C"]


# --- carried items -----------------------------------------------------------------------------


def test_carried_items():
    conds = [
        ConditionFact("CON-1", "S3-019", "SG3", "SG4_ATD", "U10", "t", "Open"),
        ConditionFact("CON-2", "S02-012", "SG2", "CLOSURE", "U14", "t", "Open"),
        ConditionFact("CON-3", "X1", "SG2", "SG3", "U01", "t", "Closed"),
        ConditionFact("CON-4", "X2", "SG2", "SG3", "U01", "t", "Closed"),
        ConditionFact("CON-5", None, "SG2", "SG3", "U01", "t", "Open"),
    ]
    done = {"X1": True, "X2": False}
    ids = [(c.item_id, c.condition_id) for c in carried_items(conds, done, "SG4_ATD")]
    assert ids == [("X2", "CON-4"), ("S3-019", "CON-1"), ("S02-012", "CON-2")]
    # same-gate / later conditions are not carried yet
    assert [c.item_id for c in carried_items(conds, done, "SG3")] == ["X2", "S02-012"]
    assert carried_items(conds, done, "SG0") == []
