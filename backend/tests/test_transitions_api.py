"""GET /transitions (FR-012, BR-020, BR-021, AC-01, AC-02, NFR-05). Seed date 2026-11-16."""

from __future__ import annotations

import time
from datetime import date

from app import clock
from app.rules.rag import compute_rag

API = "/api/v1"


def _get(client, headers, user="U01", **params):
    res = client.get(f"{API}/transitions", params=params, headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _ids(rows):
    return [r["id"] for r in rows]


def test_requires_header(client):
    assert client.get(f"{API}/transitions").status_code == 401


def test_six_transitions_visible_ac01(client, headers):
    rows = _get(client, headers)
    assert len(rows) == 6
    assert len(set(_ids(rows))) == 6


def test_sorted_by_days_then_name(client, headers):
    rows = _get(client, headers)
    keys = [
        (
            r["days_to_next_decision"] is None,
            r["days_to_next_decision"] or 0,
            r["name"].lower(),
        )
        for r in rows
    ]
    assert keys == sorted(keys)


def test_retail_portfolio_storyline_step_2(client, headers):
    rows = _get(client, headers, portfolio="Retail Site Systems")
    assert sorted(_ids(rows)) == ["TR-0008", "TR-0011"]
    pos = next(r for r in rows if r["id"] == "TR-0008")
    assert pos["name"] == "Forecourt POS refresh"
    assert pos["rag"] == "Red"
    assert pos["critical_gaps"] == 3
    assert pos["days_to_next_decision"] == 4


def test_flagship_row(client, headers):
    row = next(r for r in _get(client, headers) if r["id"] == "TR-0001")
    assert row["current_gate"] == "SG4_ATD"
    assert row["current_gate_short"] == "AtD"
    assert row["critical_gaps"] == 1
    assert row["or_focal"]["id"] == "U01"
    assert row["assessment_launched"] is True
    # BR-021: one critical gap, decision in 21 days, lowest lens 60 -> Amber
    assert row["rag"] == "Amber"


def test_every_row_rag_matches_rule_ac02(client, headers):
    for r in _get(client, headers):
        expected = compute_rag(
            r["critical_gaps"], r["lens_readiness"], r["days_to_next_decision"], has_items=True
        )
        assert r["rag"] == expected, r["id"]


def test_exact_filters(client, headers):
    assert all(r["current_gate"] == "SG4_ATD" for r in _get(client, headers, gate="SG4_ATD"))
    assert all(r["region"] == "Global" for r in _get(client, headers, region="Global"))
    ai = _get(client, headers, type="Agentic AI")
    assert ai and all(r["project_type"] == "Agentic AI" for r in ai)
    assert len(_get(client, headers, status="Active")) == 6
    assert _get(client, headers, status="Closed") == []
    reds = _get(client, headers, rag="Red")
    assert reds and all(r["rag"] == "Red" for r in reds)


def test_filters_are_anded(client, headers):
    rows = _get(client, headers, portfolio="Retail Site Systems", rag="Red")
    assert sorted(_ids(rows)) == ["TR-0008"]


def test_q_matches_name_market_and_focal(client, headers):
    allrows = _get(client, headers)
    assert _ids(_get(client, headers, q="forecourt")) == ["TR-0008"]
    assert "TR-0008" in _ids(_get(client, headers, q="tr-0008"))
    market = next(r for r in allrows if r["market"])["market"]
    by_market = _get(client, headers, q=market.upper())
    assert by_market and all(market.lower() in r["market"].lower() for r in by_market)
    focal = next(r for r in allrows if r["id"] == "TR-0001")["or_focal"]["name"]
    by_focal = _get(client, headers, q=focal.split()[0].lower())
    assert "TR-0001" in _ids(by_focal)
    assert _get(client, headers, q="zzz-no-such-thing") == []


def test_computed_filters(client, headers):
    allrows = _get(client, headers)
    soon = _get(client, headers, decision_within_days=14)
    expected = [
        r
        for r in allrows
        if r["days_to_next_decision"] is not None and r["days_to_next_decision"] <= 14
    ]
    assert _ids(soon) == _ids(expected)
    crit = _get(client, headers, has_critical="true")
    assert _ids(crit) == _ids([r for r in allrows if r["critical_gaps"] > 0])
    none = _get(client, headers, has_critical="false")
    assert len(crit) + len(none) == 6
    low = _get(client, headers, compliance_below=70)
    assert _ids(low) == _ids([r for r in allrows if r["lens_readiness"]["Compliance"] < 70])


def test_overdue_decisions_included_in_decision_within_days(client, headers):
    clock.set_today_override(date(2026, 12, 1))  # TR-0008 decision (2026-11-20) is now overdue
    try:
        rows = _get(client, headers, decision_within_days=7)
        row = next(r for r in rows if r["id"] == "TR-0008")
        assert row["days_to_next_decision"] < 0
    finally:
        clock.set_today_override(None)


def test_mine_by_role(client, headers):
    # U01 is the OR focal of every seeded transition (A-102)
    assert sorted(_ids(_get(client, headers, user="U01", mine="true"))) == [
        "TR-0001",
        "TR-0003",
        "TR-0005",
        "TR-0008",
        "TR-0011",
        "TR-0014",
    ]
    # another OR focal who owns no transition sees none
    assert _get(client, headers, user="U02", mine="true") == []
    # IRM is on every seeded transition (A-05); Planner / Leadership / Admin see everything (A-51)
    for user in ("U14", "U13", "U15", "U16"):
        assert len(_get(client, headers, user=user, mine="true")) == 6
    assert "TR-0001" in _ids(_get(client, headers, user="U10", mine="true"))


def test_performance_p95_nfr05(client, headers):
    samples = []
    for _ in range(20):
        start = time.perf_counter()
        res = client.get(f"{API}/transitions", headers=headers("U01"))
        samples.append(time.perf_counter() - start)
        assert res.status_code == 200
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 0.3, f"p95 {p95 * 1000:.0f} ms"


def test_flagship_numbers_pinned(client, headers):
    row = next(r for r in _get(client, headers) if r["id"] == "TR-0001")
    assert row["lens_readiness"] == {"Business": 81, "Technical": 74, "Compliance": 60}
    assert row["overall_readiness"] == 72
    assert (row["open_gaps"], row["critical_gaps"]) == (9, 1)


def test_approved_exception_covers_the_critical_gap(client, headers, db, fresh_seed):
    from app.models import ExceptionRecord

    before = next(r for r in _get(client, headers) if r["id"] == "TR-0001")
    db.get(ExceptionRecord, "EX-01").status = "Approved"  # covers S45-014 (A-09)
    db.commit()
    after = next(r for r in _get(client, headers) if r["id"] == "TR-0001")
    assert before["critical_gaps"] == 1 and after["critical_gaps"] == 0
    assert after["open_gaps"] == before["open_gaps"] - 1
    assert after["lens_readiness"]["Compliance"] > before["lens_readiness"]["Compliance"]
    assert after["overall_readiness"] >= before["overall_readiness"]


def test_to_confirm_and_not_applicable_items_are_out_of_scope(client, headers, db, fresh_seed):
    from sqlalchemy import select

    from app.models import PlaybookItem, TransitionItem

    def pct(lens="Business"):
        return next(r for r in _get(client, headers) if r["id"] == "TR-0001")["lens_readiness"][
            lens
        ]

    rows = (
        db.execute(
            select(TransitionItem)
            .join(PlaybookItem, PlaybookItem.id == TransitionItem.playbook_item_id)
            .where(
                TransitionItem.transition_id == "TR-0001",
                TransitionItem.applicability == "Applies",
                PlaybookItem.lens == "Business",
                TransitionItem.status.in_(["Gap", "Non-compliant"]),
            )
        )
        .scalars()
        .all()
    )
    gap = next(iter(rows), None)
    assert gap is not None, "seed has a Business gap on TR-0001"
    before = pct()
    gap.applicability = "To confirm"  # outside readiness scope until confirmed (A-22)
    db.commit()
    mid = pct()
    assert mid > before
    gap.applicability = "Applies"
    gap.status = "N/A"  # removed from the denominator (BR-020)
    db.commit()
    assert pct() == mid


def test_custom_field_filters_are_anded_with_the_named_filters(client, headers):
    # no transition holds a custom value in the seed: a cf_ filter matches nothing, the rest is unchanged
    everything = client.get(f"{API}/transitions", headers=headers("U15")).json()
    assert client.get(f"{API}/transitions?cf_unknown=x", headers=headers("U15")).json() == []
    same = client.get(f"{API}/transitions?portfolio=GCC", headers=headers("U15")).json()
    assert same and len(same) < len(everything)
    assert (
        client.get(f"{API}/transitions?portfolio=GCC&cf_unknown=x", headers=headers("U15")).json()
        == []
    )
