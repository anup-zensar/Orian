"""BR-021 RAG (spec 7.4) - every branch, boundaries included."""

from __future__ import annotations

import pytest

from app.rules.rag import compute_rag

OK = {"Business": 90, "Technical": 90, "Compliance": 90}


def lens(**overrides):
    return {**OK, **overrides}


@pytest.mark.parametrize(
    ("critical", "lenses", "days", "expected"),
    [
        # Green
        (0, OK, 30, "Green"),
        (0, OK, None, "Green"),
        (0, lens(Compliance=70), 3, "Green"),  # exactly 70 is not < 70; no critical gaps
        # Amber
        (1, OK, 30, "Amber"),
        (1, OK, None, "Amber"),  # no decision date: the 7-day rule cannot fire
        (1, OK, 8, "Amber"),  # 8 days: just outside the 7-day window
        (0, lens(Technical=69), 30, "Amber"),
        (0, lens(Technical=50), 30, "Amber"),  # exactly 50 is not < 50
        # Red
        (2, OK, 30, "Red"),
        (5, OK, None, "Red"),
        (1, OK, 7, "Red"),  # exactly 7 days
        (1, OK, 0, "Red"),
        (1, OK, -2, "Red"),  # decision date already passed
        (0, lens(Business=49), 30, "Red"),
        (0, lens(Compliance=0), None, "Red"),
        (1, lens(Business=49), 30, "Red"),
    ],
)
def test_rag_branches(critical, lenses, days, expected):
    assert compute_rag(critical, lenses, days) == expected


def test_grey_when_no_items_even_with_bad_numbers():
    assert compute_rag(3, lens(Business=0), 1, has_items=False) == "Grey"
    assert compute_rag(0, {}, None, has_items=False) == "Grey"


def test_empty_lens_map_is_green():
    assert compute_rag(0, {}, None) == "Green"


@pytest.mark.parametrize(
    ("tid", "pcts", "critical", "days", "expected"),
    [
        # seeded sample transitions (snapshot values) and the colour the control tower must show
        ("TR-0001", (82, 74, 60), 1, 21, "Amber"),
        ("TR-0003", (70, 58, 45), 2, 30, "Red"),
        ("TR-0004", (88, 80, 72), 1, 6, "Red"),
        ("TR-0011", (95, 92, 94), 0, 10, "Green"),
        ("TR-0017", (98, 97, 100), 0, 3, "Green"),
    ],
)
def test_seeded_snapshots(tid, pcts, critical, days, expected):
    lenses = dict(zip(("Business", "Technical", "Compliance"), pcts, strict=True))
    assert compute_rag(critical, lenses, days) == expected, tid


def test_thresholds_parameter_defaults_to_the_client_rule():
    from app.rules.rag import DEFAULT_RAG, RagThresholds

    assert compute_rag(2, OK, None, thresholds=DEFAULT_RAG) == compute_rag(2, OK, None) == "Red"
    strict = RagThresholds(
        red_critical_gaps=1, red_lens_below=60, red_near_days=14, amber_lens_below=95
    )
    assert compute_rag(1, OK, 30, thresholds=strict) == "Red"
    assert compute_rag(0, lens(Business=59), 30, thresholds=strict) == "Red"
    assert compute_rag(0, lens(Business=94), 30, thresholds=strict) == "Amber"
    assert (
        compute_rag(0, lens(Business=96, Technical=96, Compliance=96), 30, thresholds=strict)
        == "Green"
    )
