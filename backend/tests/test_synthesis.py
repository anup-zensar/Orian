"""Deterministic status synthesis (spec 11.3): unit cases and the all-transitions snapshot check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Condition, Transition, TransitionItem
from app.rules.constants import GATE_ORDER
from app.rules.readiness import ReadinessItem, compute_readiness
from app.rules.synthesis import Pin, Snapshot, SynthItem, _split_budget, synthesize


def seed_transitions() -> dict[str, dict]:
    path = Path(get_settings().seed_dir) / "sample_transitions.json"
    with path.open(encoding="utf-8") as fh:
        return {t["id"]: t for t in json.load(fh)["transitions"]}


def readiness_from_db(db, transition: Transition):
    """Readiness of a seeded transition, covered = open condition due after the current gate."""
    conditions = db.scalars(
        select(Condition).where(
            Condition.transition_id == transition.id, Condition.status == "Open"
        )
    ).all()
    covered = {
        c.transition_item_id
        for c in conditions
        if GATE_ORDER[c.due_gate] > GATE_ORDER[transition.current_gate]
    }
    items = db.scalars(
        select(TransitionItem).where(TransitionItem.transition_id == transition.id)
    ).all()
    return compute_readiness(
        [
            ReadinessItem(
                i.playbook_item.lens,
                i.due_gate,
                i.applicability,
                i.status,
                i.gap_severity,
                i.id in covered,
            )
            for i in items
        ],
        transition.current_gate,
    )


@pytest.mark.parametrize("tid", [f"TR-{n:04d}" for n in (1, 3, 5, 8, 11, 14)])
def test_seeded_readiness_matches_snapshot(db, tid):
    transition = db.get(Transition, tid)
    snapshot = seed_transitions()[tid]["snapshot"]
    result = readiness_from_db(db, transition)

    for lens, wanted in snapshot["readiness_pct"].items():
        scope = result.lenses[lens].scope
        # +-3 points where the scope is big enough; a scope of n items can only hit multiples of
        # 100/n, so the achievable accuracy is half a step (spec 11.3 tolerance is best effort).
        tolerance = max(3, 50 / scope + 0.5)
        assert abs(result.lenses[lens].readiness_pct - wanted) <= tolerance, (tid, lens, scope)

    assert result.critical_gaps == snapshot["critical_gaps"]

    if result.open_gaps != snapshot["open_gaps"]:
        # Not exact only when every non-done item already is a gap (snapshot asks for more gaps
        # than the scope can hold) - never because the algorithm left items "in progress".
        assert result.open_gaps < snapshot["open_gaps"]
        assert result.totals["in_progress"] + result.totals["not_started"] == 0, tid
    assert abs(result.open_gaps - snapshot["open_gaps"]) <= 2


def test_most_transitions_hit_open_gaps_exactly(db):
    snapshots = seed_transitions()
    exact = sum(
        readiness_from_db(db, db.get(Transition, tid)).open_gaps == s["snapshot"]["open_gaps"]
        for tid, s in snapshots.items()
    )
    capped = [
        tid
        for tid, s in snapshots.items()
        if readiness_from_db(db, db.get(Transition, tid)).open_gaps != s["snapshot"]["open_gaps"]
    ]
    # Only TR-0005 (tiny scope: 7 of the snapshot's 8 gaps fit) is a known capped case.
    assert exact >= 5 and set(capped) <= {"TR-0005"}, capped


def test_flagship_overrides_applied_exactly(db):
    flagship = seed_transitions()["TR-0001"]
    rows = {
        i.playbook_item_id: i
        for i in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == "TR-0001"))
    }
    for override in flagship["item_overrides"]:
        row = rows[override["item_id"]]
        assert row.status == override["status"], override["item_id"]
        assert row.note == override["note"], override["item_id"]
        if "design_effectiveness" in override:
            assert row.design_effectiveness == override["design_effectiveness"]
        if "linked_module" in override:
            assert row.linked_module == override["linked_module"]
    assert rows["S45-014"].gap_severity == "Critical"  # A-07
    assert rows["S45-014"].design_effectiveness == "No"
    assert rows["FW-035"].gap_severity == "Major"
    # A-36: items of the seeded open conditions
    assert rows["S02-012"].status == "Compliant with conditions"
    assert rows["S02-012"].design_effectiveness == "Yes"
    assert rows["S3-019"].status == "In progress"
    # exactly one critical gap on the flagship
    critical = [r.playbook_item_id for r in rows.values() if r.gap_severity == "Critical"]
    assert critical == ["S45-014"]


def test_blocker_attached_to_first_critical_gap_note(db):
    row_note = {
        i.playbook_item_id: i.note
        for i in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == "TR-0003"))
        if i.gap_severity == "Critical"
    }
    assert row_note, "TR-0003 has 2 critical gaps"
    assert sum("Support model not agreed with SOM" in n for n in row_note.values()) == 1


# --- pure unit cases ------------------------------------------------------------------------------


def items(spec):
    return [SynthItem(i, lens, gate) for i, lens, gate in spec]


def test_split_budget_largest_remainder_and_tie_break():
    assert _split_budget(5, {"Business": 10, "Technical": 10, "Compliance": 10}) == {
        "Business": 2,
        "Technical": 2,
        "Compliance": 1,
    }  # tie on remainders -> lens order Business, Technical, Compliance
    # remainders tie between Business and Compliance -> the extra gap goes to Business
    assert _split_budget(4, {"Business": 1, "Technical": 8, "Compliance": 1}) == {
        "Business": 1,
        "Technical": 3,
        "Compliance": 0,
    }
    assert _split_budget(50, {"Business": 1, "Technical": 2, "Compliance": 3}) == {
        "Business": 1,
        "Technical": 2,
        "Compliance": 3,
    }  # capped by free items
    assert sum(_split_budget(0, {"Business": 3}).values()) == 0


def test_targets_and_gap_placement_without_pins():
    spec = [(f"B-{n:02d}", "Business", "SG2") for n in range(10)]
    spec += [(f"C-{n:02d}", "Compliance", "SG2") for n in range(10)]
    spec += [("B-99", "Business", "SG4_ATD")]  # due after current gate
    snap = Snapshot(
        {"Business": 50, "Technical": 100, "Compliance": 30}, open_gaps=4, critical_gaps=1
    )
    out = synthesize(items(spec), "SG2", snap)
    assert out["B-99"].status == "Not started"
    done_b = [i for i in out if i.startswith("B-") and out[i].status == "Complete"]
    assert done_b == [f"B-{n:02d}" for n in range(5)]  # the FIRST k items
    done_c = [i for i in out if i.startswith("C-") and out[i].status == "Compliant"]
    assert done_c == ["C-00", "C-01", "C-02"]
    assert all(out[i].design_effectiveness == "Yes" for i in done_c)
    gaps = sorted(i for i, r in out.items() if r.status in ("Gap", "Non-compliant"))
    assert gaps == ["B-08", "B-09", "C-08", "C-09"]  # 4 gaps split 2/2; the LAST free items
    assert [i for i in gaps if out[i].gap_severity == "Critical"] == ["B-08"]  # lowest gate, id
    assert [i for i in gaps if out[i].gap_severity == "Major"] == ["B-09", "C-08", "C-09"]
    for i, r in out.items():
        if r.status == "Non-compliant":
            assert r.design_effectiveness == "No"
        if r.status == "In review":
            assert r.design_effectiveness == "–"
        if i.startswith("B-"):
            assert r.design_effectiveness is None


def test_round_half_up_target_and_deterministic():
    # 58 % of 25 = 14.5 -> 15 (float arithmetic would give 14.499999... -> 14)
    spec = [(f"T-{n:02d}", "Technical", "SG2") for n in range(25)]
    snap = Snapshot({"Business": 100, "Technical": 58, "Compliance": 100}, 0, 0)
    first = synthesize(items(spec), "SG2", snap)
    assert sum(r.status == "Complete" for r in first.values()) == 15
    assert synthesize(items(spec), "SG2", snap) == first


def test_pins_count_towards_targets_and_critical_prefers_listed_ids():
    spec = [(f"T-{n:02d}", "Technical", "SG2") for n in range(10)]
    snap = Snapshot(
        {"Business": 100, "Technical": 50, "Compliance": 100}, open_gaps=3, critical_gaps=1
    )
    pins = {"T-03": Pin("Complete"), "T-00": Pin("Gap")}
    out = synthesize(items(spec), "SG2", snap, pinned=pins, preferred_critical_ids=["T-09"])
    assert out["T-03"].status == "Complete" and out["T-00"].status == "Gap"
    assert sum(r.status == "Complete" for r in out.values()) == 5  # 50 % of 10 incl. the pin
    assert sum(r.status == "Gap" for r in out.values()) == 3  # incl. the pinned gap
    assert out["T-09"].gap_severity == "Critical"
    assert out["T-00"].gap_severity == "Major"
    assert sum(r.gap_severity == "Critical" for r in out.values()) == 1


def test_covered_items_count_as_done():
    spec = [(f"B-{n}", "Business", "SG2") for n in range(4)]
    snap = Snapshot({"Business": 50, "Technical": 100, "Compliance": 100}, 0, 0)
    out = synthesize(items(spec), "SG2", snap, covered_item_ids={"B-3"})
    assert sum(r.status == "Complete" for r in out.values()) == 2
    assert out["B-3"].status == "Complete"
    assert out["B-0"].status == "Complete" and out["B-1"].status == "In progress"
