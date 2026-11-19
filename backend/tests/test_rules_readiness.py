"""BR-020 readiness (spec 7.3) with A-09/A-22/A-32/A-33."""

from __future__ import annotations

import pytest

from app.rules.readiness import ReadinessItem, compute_readiness, percent, round_half_up


def item(
    lens="Business", gate="SG2", status="Complete", applicability="Applies", sev=None, covered=False
):
    return ReadinessItem(lens, gate, applicability, status, sev, covered)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.5, 1), (1.5, 2), (2.5, 3), (12.5, 13), (12.49, 12), (0, 0), (100, 100), (66.666, 67)],
)
def test_round_half_up_not_bankers(value, expected):
    assert round_half_up(value) == expected  # round(2.5) would be 2


def test_percent_is_exact_for_ratios():
    assert percent(1, 8) == 13  # 12.5 -> 13
    assert percent(3, 8) == 38  # 37.5 -> 38
    assert percent(0, 0) == 100
    assert percent(29, 50) == 58
    assert percent(7, 12) == 58  # 58.33


def test_empty_scope_is_100_and_overall_100():
    result = compute_readiness([], "SG4_ATD")
    assert result.overall == 100
    for lens in ("Business", "Technical", "Compliance"):
        assert result.lenses[lens].scope == 0
        assert result.lenses[lens].readiness_pct == 100


def test_scope_uses_gate_order():
    items = [
        item(gate="SG0", status="Complete"),
        item(gate="SG3", status="Complete"),
        item(gate="SG4_ATD", status="Not started"),  # due after the current gate -> out of scope
    ]
    business = compute_readiness(items, "SG3").lenses["Business"]
    assert (business.scope, business.done, business.readiness_pct) == (2, 2, 100)
    business = compute_readiness(items, "SG4_ATD").lenses["Business"]
    assert (business.scope, business.done, business.readiness_pct) == (3, 2, 67)


def test_na_removed_from_denominator_and_not_counted_done():
    items = [
        item(status="Complete"),
        item(status="N/A"),
        item(status="Not started"),
        item("Compliance", status="Not applicable"),
        item("Compliance", status="Compliant"),
    ]
    result = compute_readiness(items, "SG2")
    assert result.lenses["Business"].scope == 2
    assert result.lenses["Business"].readiness_pct == 50
    assert result.lenses["Compliance"].scope == 1
    assert result.lenses["Compliance"].readiness_pct == 100


def test_to_confirm_and_not_applicable_are_out_of_scope():
    items = [
        item(status="Complete"),
        item(status="Not started", applicability="To confirm"),
        item(status="N/A", applicability="Not applicable"),
    ]
    business = compute_readiness(items, "SG2").lenses["Business"]
    assert (business.scope, business.readiness_pct) == (1, 100)


def test_covered_counts_as_done_and_is_not_an_open_gap():
    items = [
        item(status="In progress", covered=True),  # open condition due later
        item(status="Gap", sev="Critical", covered=True),  # approved exception
        item(status="Gap", sev="Major"),
        item(status="Not started"),
    ]
    business = compute_readiness(items, "SG2").lenses["Business"]
    assert business.scope == 4
    assert business.done == 2
    assert business.open_gaps == 1
    assert business.critical_gaps == 0
    assert business.not_started == 1
    assert business.in_progress == 0
    assert business.readiness_pct == 50


def test_gap_progress_and_critical_counts_and_partition():
    items = [
        item("Technical", status="Gap", sev="Critical"),
        item("Technical", status="Gap", sev="Major"),
        item("Technical", status="Gap", sev=None),
        item("Technical", status="In progress"),
        item("Technical", status="Not started"),
        item("Technical", status="Complete"),
        item("Compliance", status="Non-compliant", sev="Critical"),
        item("Compliance", status="In review"),
        item("Compliance", status="Compliant with conditions"),
    ]
    result = compute_readiness(items, "SG4_ATD")
    tech = result.lenses["Technical"]
    assert (tech.open_gaps, tech.critical_gaps, tech.in_progress, tech.not_started) == (3, 1, 1, 1)
    comp = result.lenses["Compliance"]
    assert (comp.open_gaps, comp.critical_gaps, comp.in_progress, comp.done) == (1, 1, 1, 1)
    for lens in result.lenses.values():
        assert lens.done + lens.in_progress + lens.not_started + lens.open_gaps == lens.scope
    assert result.totals["open_gaps"] == 4
    assert result.totals["critical_gaps"] == 2
    assert result.open_gaps == 4 and result.critical_gaps == 2


@pytest.mark.parametrize(
    ("pcts", "overall"),
    [
        ((100, 100, 100), 100),
        ((82, 74, 60), 72),
        ((50, 50, 51), 50),
        ((50, 51, 51), 51),
        ((0, 0, 1), 0),
    ],
)
def test_overall_is_round_half_up_mean(pcts, overall):
    # build scopes of 100 items so each lens hits the wanted percentage exactly
    items = []
    for lens, pct in zip(("Business", "Technical", "Compliance"), pcts, strict=True):
        items += [item(lens, status="Complete") for _ in range(pct)]
        items += [item(lens, status="Not started") for _ in range(100 - pct)]
    result = compute_readiness(items, "SG2")
    assert [result.lenses[lens].readiness_pct for lens in result.lenses] == list(pcts)
    assert result.overall == overall


def test_unknown_gate_rejected():
    with pytest.raises(ValueError):
        compute_readiness([], "SG9")


def test_to_dict_shape():
    data = compute_readiness([item()], "SG2").to_dict()
    assert set(data) == {"lenses", "overall", "totals"}
    assert set(data["lenses"]["Business"]) == {
        "scope",
        "done",
        "in_progress",
        "not_started",
        "open_gaps",
        "critical_gaps",
        "readiness_pct",
    }


def test_critical_severity_is_a_parameter():
    items = [
        item(status="Gap", sev="Critical"),
        item(status="Gap", sev="Major"),
        item(status="Gap", sev="Major"),
    ]
    assert compute_readiness(items, "SG2").critical_gaps == 1  # default: "Critical"
    assert compute_readiness(items, "SG2", critical_value="Major").critical_gaps == 2
    assert compute_readiness(items, "SG2", "Showstopper").critical_gaps == 0
    assert compute_readiness(items, "SG2", "Major").open_gaps == 3  # open gaps do not change
