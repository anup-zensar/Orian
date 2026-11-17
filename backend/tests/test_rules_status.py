"""BR-030 status rules (spec 7.5, AC-06): pure functions, no database."""

from __future__ import annotations

import pytest

from app.rules import status as rules


def test_allowed_statuses_per_lens():
    assert rules.allowed_statuses("Business") == (
        "Not started",
        "In progress",
        "Complete",
        "Gap",
        "N/A",
    )
    assert rules.allowed_statuses("Technical") == rules.allowed_statuses("Business")
    assert "Compliant with conditions" in rules.allowed_statuses("Compliance")
    assert rules.allowed_statuses("Nope") == ()


def test_input_errors_status_not_in_lens():
    assert rules.input_errors(lens="Business", status="Complete") == []
    assert rules.input_errors(lens="Business", status="Compliant")
    assert rules.input_errors(lens="Compliance", status="Gap")
    assert rules.input_errors(lens="Compliance", status="Non-compliant") == []


def test_input_errors_severity_and_design_effectiveness():
    assert rules.input_errors(lens="Business", gap_severity="Huge")
    assert rules.input_errors(lens="Compliance", design_effectiveness="Maybe")
    assert (
        rules.input_errors(lens="Compliance", gap_severity="Critical", design_effectiveness="Yes")
        == []
    )


def test_input_errors_unknown_lens():
    assert rules.input_errors(lens="Legal", status="Complete")


def _viol(**kw):
    base = dict(
        lens="Business",
        status="In progress",
        gap_severity=None,
        note="",
        design_effectiveness=None,
        na_reason=None,
        has_condition=False,
    )
    base.update(kw)
    return rules.rule_violations(**base)


@pytest.mark.parametrize("status,lens", [("Gap", "Business"), ("Non-compliant", "Compliance")])
def test_gap_needs_severity_and_note(status, lens):
    reasons = _viol(status=status, lens=lens)
    assert len(reasons) == 2
    assert any("severity" in r for r in reasons) and any("note" in r for r in reasons)
    assert len(_viol(status=status, lens=lens, gap_severity="Major")) == 1
    assert len(_viol(status=status, lens=lens, note="   ", gap_severity="Major")) == 1
    assert _viol(status=status, lens=lens, gap_severity="Major", note="why") == []


@pytest.mark.parametrize("status,lens", [("N/A", "Business"), ("Not applicable", "Compliance")])
def test_na_needs_reason(status, lens):
    assert _viol(status=status, lens=lens)
    assert _viol(status=status, lens=lens, na_reason=" ")
    assert _viol(status=status, lens=lens, na_reason="Out of scope") == []


def test_compliant_needs_design_effectiveness_yes_or_na():
    assert _viol(lens="Compliance", status="Compliant")
    assert _viol(lens="Compliance", status="Compliant", design_effectiveness="–")
    assert _viol(lens="Compliance", status="Compliant", design_effectiveness="No")
    assert _viol(lens="Compliance", status="Compliant", design_effectiveness="Yes") == []
    assert _viol(lens="Compliance", status="Compliant", design_effectiveness="N/A") == []


def test_compliant_with_conditions_needs_condition():
    assert _viol(lens="Compliance", status="Compliant with conditions")
    assert _viol(lens="Compliance", status="Compliant with conditions", has_condition=True) == []


def test_check_switches_skip_rules():
    assert _viol(status="Gap", check_gap=False) == []
    assert _viol(status="N/A", check_na=False) == []
    assert _viol(lens="Compliance", status="Compliant", check_design=False) == []
    assert _viol(lens="Compliance", status="Compliant with conditions", check_condition=False) == []


def test_missing_condition_fields():
    assert rules.missing_condition_fields("U11", "SG4_ATD", "Fix it") == []
    assert len(rules.missing_condition_fields(None, "", " ")) == 3


def test_clears_gap_severity():
    assert rules.clears_gap_severity("Complete")
    assert not rules.clears_gap_severity("Gap")
    assert not rules.clears_gap_severity("Non-compliant")
