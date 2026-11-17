"""GET /control-tower (FR-011, AC-01, AC-02)."""

from __future__ import annotations

from fractions import Fraction

from app.rules.readiness import round_half_up

API = "/api/v1"
RAG_ORDER = ["Red", "Amber", "Green", "Grey"]
TILE_KEYS = ["active", "red", "decisions_14d", "critical", "compliance_below_70"]


def _ct(client, headers, user="U01", **params):
    res = client.get(f"{API}/control-tower", params=params, headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def test_requires_header(client):
    assert client.get(f"{API}/control-tower").status_code == 401


def test_register_matches_transitions_endpoint(client, headers):
    ct = _ct(client, headers)
    listing = client.get(f"{API}/transitions", headers=headers()).json()
    assert ct["transitions"] == listing
    assert ct["today"] == "2026-11-16"
    assert len(ct["transitions"]) == 18


def test_kpi_tiles_shape_and_filter_consistency(client, headers):
    ct = _ct(client, headers)
    assert [k["key"] for k in ct["kpis"]] == TILE_KEYS
    assert [k["label"] for k in ct["kpis"]] == [
        "Active transitions",
        "Red",
        "Decisions ≤ 14 days",
        "With critical gaps",
        "Compliance readiness < 70%",
    ]
    assert [k["tone"] for k in ct["kpis"]] == ["neutral", "danger", "warning", "danger", "warning"]
    assert ct["kpis"][2]["filter"] == {"decision_within_days": "14"}
    assert all(k["hint"] for k in ct["kpis"])
    for tile in ct["kpis"]:
        filtered = _ct(client, headers, **tile["filter"])
        assert len(filtered["transitions"]) == tile["value"], tile["key"]


def test_kpis_follow_the_filters(client, headers):
    ct = _ct(client, headers, portfolio="Retail Site Systems")
    kpis = {k["key"]: k["value"] for k in ct["kpis"]}
    assert kpis["active"] == 5
    assert kpis["red"] == 2
    assert ct["filters"]["portfolio"] == "Retail Site Systems"


def test_heatmap(client, headers):
    ct = _ct(client, headers)
    heat = ct["heatmap"]
    assert len(heat["portfolios"]) == 6 and len(heat["gates"]) == 7
    assert len(heat["cells"]) == 42
    assert sum(c["count"] for c in heat["cells"]) == len(ct["transitions"])
    for cell in heat["cells"]:
        rows = [
            t["rag"]
            for t in ct["transitions"]
            if t["portfolio"] == cell["portfolio"] and t["current_gate"] == cell["gate"]
        ]
        assert cell["count"] == len(rows)
        expected = min(rows, key=RAG_ORDER.index) if rows else None
        assert cell["worst_rag"] == expected
    # the heatmap ignores portfolio and gate (the selected cell keeps its context) ...
    for params in ({"portfolio": "GCC"}, {"gate": "SG4_ATD"}):
        filtered = _ct(client, headers, **params)
        assert filtered["heatmap"] == heat
        assert len(filtered["heatmap"]["cells"]) == 42
    # ... but follows every other filter
    region = _ct(client, headers, region="Global")
    assert sum(c["count"] for c in region["heatmap"]["cells"]) == len(region["transitions"]) < 18


def test_readiness_by_region(client, headers):
    ct = _ct(client, headers)
    regions = ct["readiness_by_region"]
    assert [r["region"] for r in regions] == [
        "Global",
        "Europe & South Africa",
        "Asia Pacific",
        "Americas",
        "Central Apps",
    ]
    assert sum(r["transitions"] for r in regions) == 18
    for r in regions:
        scores = [t["overall_readiness"] for t in ct["transitions"] if t["region"] == r["region"]]
        expected = round_half_up(Fraction(sum(scores), len(scores))) if scores else None
        assert r["average_readiness"] == expected
        assert r["transitions"] == len(scores)


def test_escalations_contain_every_red(client, headers):
    ct = _ct(client, headers)
    reds = {t["id"] for t in ct["transitions"] if t["rag"] == "Red"}
    esc = ct["escalations"]
    assert reds <= {e["transition_id"] for e in esc}
    flags = [e["rag"] != "Red" for e in esc]
    assert flags == sorted(flags)  # Red first
    red_days = [e["days_to_next_decision"] for e in esc if e["rag"] == "Red"]
    assert red_days == sorted(red_days)
    pos = next(e for e in esc if e["transition_id"] == "TR-0008")
    # the lowest lens is named whenever it is below 70, even with critical gaps
    assert pos["reason"] == "3 critical gaps · Technical readiness 49% · AtD decision in 4 days"
    assert pos["owner"]["id"]
    blockers = {t["id"] for t in ct["transitions"] if t["blocker_note"]}
    assert blockers <= {e["transition_id"] for e in esc}


def test_calendar(client, headers):
    ct = _ct(client, headers)
    cal = ct["calendar"]
    assert cal
    assert [c["date"] for c in cal] == sorted(c["date"] for c in cal)
    labels = {"SG4_ATD": "AtD decision", "SG6_ATO": "AtO decision", "CLOSURE": "Closure"}
    for entry in cal:
        assert entry["days"] <= 45
        assert entry["decision"] == labels[entry["gate"]]
    expected = {
        t["id"]
        for t in ct["transitions"]
        if t["current_gate"] in labels
        and t["days_to_next_decision"] is not None
        and t["days_to_next_decision"] <= 45
    }
    assert {c["transition_id"] for c in cal} == expected


def test_operating_rhythm(client, headers):
    rows = _ct(client, headers)["operating_rhythm"]
    assert len(rows) == 4
    assert [r["forum"] for r in rows] == [
        "OR team stand-up",
        "Portfolio / regional SME review",
        "IRM checkpoint",
        "Leadership update",
    ]
    assert rows[1]["input"] == 'Portfolio heatmap, "to confirm" applicability'


def test_kpis_ignore_tile_filters_but_follow_the_rest(client, headers):
    base = {k["key"]: k["value"] for k in _ct(client, headers)["kpis"]}
    for params in (
        {"rag": "Red"},
        {"status": "Active"},
        {"decision_within_days": "14"},
        {"has_critical": "true"},
        {"compliance_below": "70"},
        {"rag": "Red", "has_critical": "true"},
    ):
        ct = _ct(client, headers, **params)
        assert {k["key"]: k["value"] for k in ct["kpis"]} == base, params
        assert len(ct["transitions"]) < 18 or params == {"status": "Active"}
    gcc = _ct(client, headers, portfolio="GCC", rag="Red")
    only_gcc = _ct(client, headers, portfolio="GCC")
    assert gcc["kpis"] == only_gcc["kpis"]
    assert {k["key"]: k["value"] for k in only_gcc["kpis"]}["active"] == 3


def test_not_launched_has_zero_readiness_and_is_not_averaged(client, headers, db, fresh_seed):
    from sqlalchemy import delete

    from app.models import Transition, TransitionItem

    before = {r["region"]: r for r in _ct(client, headers)["readiness_by_region"]}
    t = db.get(Transition, "TR-0002")
    region = t.region
    db.execute(delete(TransitionItem).where(TransitionItem.transition_id == "TR-0002"))
    t.assessment_launched_at = None
    db.commit()

    ct = _ct(client, headers)
    row = next(r for r in ct["transitions"] if r["id"] == "TR-0002")
    assert row["rag"] == "Grey" and row["assessment_launched"] is False
    assert row["lens_readiness"] == {"Business": 0, "Technical": 0, "Compliance": 0}
    assert row["overall_readiness"] == 0
    launched = [
        r["overall_readiness"]
        for r in ct["transitions"]
        if r["region"] == region and r["rag"] != "Grey"
    ]
    reg = next(r for r in ct["readiness_by_region"] if r["region"] == region)
    assert reg["transitions"] == before[region]["transitions"]
    assert reg["average_readiness"] == (
        round_half_up(Fraction(sum(launched), len(launched))) if launched else None
    )
    comp = next(k for k in ct["kpis"] if k["key"] == "compliance_below_70")
    listed = _ct(client, headers, compliance_below=70)["transitions"]
    assert "TR-0002" not in {r["id"] for r in listed} and len(listed) == comp["value"]
    esc = {e["transition_id"]: e for e in ct["escalations"]}
    assert "TR-0002" not in esc or "readiness" not in esc["TR-0002"]["reason"]
