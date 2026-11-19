"""CR-01: RAG thresholds, the critical severity and the default tier come from configuration.

Thresholds are live: a change recolours every transition on the next read; nothing is stored per
transition. The seed values reproduce today's rule (Red: 2 critical gaps, lens < 50 %, 1 critical gap
and a decision within 7 days; Amber: 1 critical gap or lens < 70 %).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domain import cfg
from app.models import AppSetting, OptionItem
from app.rules.rag import DEFAULT_RAG, RagThresholds, compute_rag
from tests.config_helpers import API

LENSES = {"Business": 80, "Technical": 80, "Compliance": 80}


# --- the pure rule -----------------------------------------------------------------------------


def test_defaults_are_todays_rule():
    assert RagThresholds(2, 50, 7, 1, 70) == DEFAULT_RAG
    assert compute_rag(2, LENSES, None) == "Red"
    assert compute_rag(1, LENSES, 7) == "Red"
    assert compute_rag(1, LENSES, 8) == "Amber"
    assert compute_rag(0, {**LENSES, "Business": 69}, None) == "Amber"


@pytest.mark.parametrize(
    ("limits", "critical", "lenses", "days", "expected"),
    [
        (RagThresholds(red_critical_gaps=3), 2, LENSES, None, "Amber"),
        (RagThresholds(red_critical_gaps=1), 1, LENSES, None, "Red"),
        (RagThresholds(red_lens_below=80), 0, {**LENSES, "Technical": 79}, None, "Red"),
        (RagThresholds(red_near_days=30), 1, LENSES, 20, "Red"),
        (RagThresholds(red_near_days=0), 1, LENSES, 3, "Amber"),
        (RagThresholds(amber_lens_below=90), 0, LENSES, None, "Amber"),
        (RagThresholds(amber_lens_below=10), 0, {**LENSES, "Technical": 60}, None, "Green"),
        (RagThresholds(amber_critical_gaps=2, red_critical_gaps=5), 1, LENSES, None, "Green"),
    ],
)
def test_thresholds_change_compute_rag(limits, critical, lenses, days, expected):
    assert compute_rag(critical, lenses, days, thresholds=limits) == expected


def test_not_started_is_grey_whatever_the_thresholds():
    assert (
        compute_rag(9, LENSES, 0, has_items=False, thresholds=RagThresholds(1, 100, 99, 1, 100))
        == "Grey"
    )


# --- through the API ---------------------------------------------------------------------------


def _put_thresholds(client, headers, db, **rag):
    """Change the RAG numbers the way the Admin screen does (GET the document, edit, PUT it back)."""
    doc = client.get(f"{API}/admin/thresholds", headers=headers("U16")).json()["thresholds"]
    doc["rag"].update(rag)
    res = client.put(f"{API}/admin/thresholds", json={"thresholds": doc}, headers=headers("U16"))
    if res.status_code == 501:  # write endpoint not built yet: store the same document directly
        db.merge(AppSetting(key="cfg.thresholds", value=doc))
        db.commit()
        cfg.invalidate()
    else:
        assert res.status_code == 200, res.text
    return doc


def _rags(client, headers) -> dict[str, str]:
    res = client.get(f"{API}/transitions", headers=headers("U15"))
    assert res.status_code == 200, res.text
    return {row["id"]: row["rag"] for row in res.json()}


def test_changing_the_numbers_recolours_every_transition_live(client, headers, db, fresh_seed):
    before = _rags(client, headers)
    assert {"Red", "Amber", "Green"} <= set(before.values())  # the seed shows all colours

    # Red below 100 % on any lens: every launched transition that is not fully ready turns Red.
    _put_thresholds(client, headers, db, red_lens_below=100, amber_lens_below=100)
    rows = client.get(f"{API}/transitions", headers=headers("U15")).json()
    for row in rows:
        lowest = min(row["lens_readiness"].values())
        if row["rag"] == "Grey":
            assert row["assessment_launched"] is False or before[row["id"]] == "Grey"
        elif lowest < 100:
            assert row["rag"] == "Red", row["id"]
    assert sum(r["rag"] == "Red" for r in rows) > sum(rag == "Red" for rag in before.values())

    # Back to today's numbers: the colours come back (nothing was stored per transition).
    _put_thresholds(client, headers, db, red_lens_below=50, amber_lens_below=70)
    assert _rags(client, headers) == before


def test_detail_and_register_use_the_same_thresholds(client, headers, db, fresh_seed):
    _put_thresholds(client, headers, db, red_lens_below=100, amber_lens_below=100)
    register = _rags(client, headers)
    for tid in ("TR-0001", "TR-0002"):
        detail = client.get(f"{API}/transitions/{tid}", headers=headers("U15")).json()
        assert detail["rag"] == register[tid]


def test_rag_rule_text_is_generated_from_the_numbers(client, headers, db, fresh_seed):
    _put_thresholds(client, headers, db, red_lens_below=40, amber_lens_below=65)
    res = client.get(f"{API}/admin/thresholds", headers=headers("U16")).json()
    assert "min_lens_readiness < 40" in res["rag_rule"]["red"]
    assert "min_lens_readiness < 65" in res["rag_rule"]["amber"]
    assert cfg.rag_rule_text(db)["red"] == res["rag_rule"]["red"]


def test_which_severity_is_critical_comes_from_configuration(client, headers, db, fresh_seed):
    before = {
        row["id"]: row["critical_gaps"]
        for row in client.get(f"{API}/transitions", headers=headers("U15")).json()
    }
    assert sum(before.values()) > 0

    # "Major" counts as critical instead of "Critical": the critical gap numbers follow it.
    items = {
        i.value: i
        for i in db.scalars(select(OptionItem).where(OptionItem.list_key == "severities"))
    }
    items["Critical"].meta = {**items["Critical"].meta, "counts_as_critical": False}
    items["Major"].meta = {**items["Major"].meta, "counts_as_critical": True}
    db.commit()
    cfg.invalidate()
    assert cfg.critical_severity(db) == "Major"

    after = {
        row["id"]: row["critical_gaps"]
        for row in client.get(f"{API}/transitions", headers=headers("U15")).json()
    }
    assert after != before


def test_default_tier_comes_from_configuration(client, headers, db, fresh_seed):
    body = {
        "audience": "Internal department",
        "write_actions": "No",
        "sensitive_data": "No",
        "answers": {},
    }
    res = client.post(f"{API}/tiering/propose", json=body, headers=headers("U01")).json()
    assert res["proposed_tier"] == 3 and "No rule matched -> Tier 3" in res["rationale"][-2]

    doc = client.get(f"{API}/admin/thresholds", headers=headers("U16")).json()["thresholds"]
    doc["default_tier"] = 2
    put = client.put(f"{API}/admin/thresholds", json={"thresholds": doc}, headers=headers("U16"))
    if put.status_code == 501:
        db.merge(AppSetting(key="cfg.thresholds", value=doc))
        db.commit()
        cfg.invalidate()
    res = client.post(f"{API}/tiering/propose", json=body, headers=headers("U01")).json()
    assert res["proposed_tier"] == 2
    assert any("No rule matched -> Tier 2" in line for line in res["rationale"])
