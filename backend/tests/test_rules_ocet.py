"""OCET projection maths and variance (BR-070, AC-09)."""

from __future__ import annotations

import pytest

from app.rules.ocet import (
    OcetLineInput,
    format_k,
    format_total_label,
    project_line,
    project_version,
    variance,
    years_for,
)


def _line(key="L1", cat="Hosting / cloud", base=100_000.0, growth=10.0, overrides=None, desc=""):
    return OcetLineInput(key, cat, base, growth, overrides or {}, desc)


def test_years():
    assert years_for(2027, 5) == [2027, 2028, 2029, 2030, 2031]


def test_ac09_worked_example():
    proj = project_line(_line(), 2027, 5)
    assert [round(v, 2) for v in proj.yearly.values()] == [
        100_000,
        110_000,
        121_000,
        133_100,
        146_410,
    ]
    assert list(proj.yearly) == [2027, 2028, 2029, 2030, 2031]
    assert proj.total == pytest.approx(610_510)
    assert not proj.base_missing


def test_override_is_growth_into_year_and_compounds_after():
    line = _line(base=40_000, growth=15, overrides={"2028": 30})
    y = project_line(line, 2027, 5).yearly
    assert y[2028] == pytest.approx(52_000)
    assert y[2029] == pytest.approx(52_000 * 1.15)
    # int keys and out-of-horizon keys
    y2 = project_line(_line(base=40_000, growth=15, overrides={2028: 30, 2040: 99}), 2027, 5).yearly
    assert y2 == y


def test_missing_base_contributes_zero_and_flags_pending():
    proj = project_version([_line(), _line("L6", "Other", None, 0)], 2027, 5)
    assert proj.inputs_pending
    assert proj.lines[1].base_missing and proj.lines[1].total == 0
    assert all(v == 0 for v in proj.lines[1].yearly.values())
    assert proj.total == pytest.approx(610_510)


def test_totals_by_category_and_year():
    proj = project_version(
        [_line(), _line("L2", "Hosting / cloud", 10, 0), _line("L3", "Licences", 5, 0)], 2027, 2
    )
    assert list(proj.category_totals) == ["Hosting / cloud", "Licences"]
    assert proj.category_totals["Hosting / cloud"][2027] == pytest.approx(100_010)
    assert proj.grand_total_by_year[2028] == pytest.approx(110_000 + 10 + 5)
    assert proj.category_grand["Licences"] == 10
    assert proj.total == pytest.approx(sum(proj.grand_total_by_year.values()))


def test_empty_version():
    proj = project_version([], 2027, 5)
    assert proj.total == 0 and not proj.inputs_pending and proj.lines == []


def test_variance_added_removed_changed_same():
    prev = project_version(
        [_line("L1", base=100), _line("L2", "Licences", 50, 0), _line("L3", "Other", 10, 0)],
        2027,
        1,
    )
    cur = project_version(
        [_line("L1", base=150), _line("L2", "Licences", 50, 0), _line("L4", "Other", 20, 0)],
        2027,
        1,
    )
    var = variance(prev, cur)
    rows = {r.key: r for r in var.by_line}
    assert [r.key for r in var.by_line] == ["L1", "L2", "L4", "L3"]
    assert rows["L1"].status == "changed" and rows["L1"].abs_change == 50
    assert rows["L1"].pct_change == pytest.approx(50.0)
    assert rows["L2"].status == "same"
    assert rows["L4"].status == "added" and rows["L4"].pct_change is None
    assert rows["L3"].status == "removed" and rows["L3"].current_total == 0
    cats = {r.key: r for r in var.by_category}
    assert cats["Other"].abs_change == 10 and cats["Other"].status == "changed"
    assert var.total_abs == 60 and var.total_pct == pytest.approx(60 / 160 * 100)


def test_variance_without_previous():
    cur = project_version([_line()], 2027, 5)
    var = variance(None, cur)
    assert var.total_abs == cur.total and var.total_pct is None
    assert all(r.status == "added" and r.previous_total == 0 for r in var.by_line)


def test_formatting():
    assert format_k(146_410) == "146.4k"
    assert format_k(100_000) == "100.0k"
    assert format_k(0) == "0.0k"
    assert format_k(999) == "1.0k"
    assert format_k(-12_500) == "-12.5k"
    assert format_total_label(1_920_000) == "1.92M"
    assert format_total_label(610_510) == "610.5k"
