"""GET /dashboard (FR-010, spec 8.1)."""

from __future__ import annotations

API = "/api/v1"
OWNED = {"TR-0001", "TR-0003", "TR-0005", "TR-0008", "TR-0011", "TR-0014"}


def _dash(client, headers, user):
    res = client.get(f"{API}/dashboard", headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _kpis(d):
    return {k["key"]: k for k in d["kpis"]}


def test_requires_header(client):
    assert client.get(f"{API}/dashboard").status_code == 401


def test_or_focal_dashboard(client, headers):
    d = _dash(client, headers, "U01")
    kpis = _kpis(d)
    assert list(kpis) == [
        "my_open_items",
        "my_pending_approvals",
        "transitions_i_own",
        "decisions_14d",
        "critical_gaps",
    ]
    assert kpis["transitions_i_own"]["value"] == 6  # U01 owns every seeded transition (A-102)
    assert kpis["transitions_i_own"]["link"] == "/transitions?mine=true"
    assert kpis["my_pending_approvals"]["link"] == "/approvals"
    assert kpis["my_open_items"]["link"] is None
    # critical gaps over the six owned transitions: 1 + 2 + 0 + 3 + 0 + 1
    assert kpis["critical_gaps"]["value"] == 7
    assert kpis["critical_gaps"]["tone"] == "danger"
    assert kpis["critical_gaps"]["link"] == "/transitions?mine=true&has_critical=true"
    assert d["portfolio_tiles"] == []
    assert d["my_work_total"] >= len(d["my_work"]) > 0
    assert len(d["my_work"]) == min(d["my_work_total"], 200)  # my_work_limit (was 25)
    assert all(w["transition_id"] in OWNED for w in d["my_work"])


def test_non_or_focal_has_no_owner_tile(client, headers):
    assert "transitions_i_own" not in _kpis(_dash(client, headers, "U10"))


def test_irm_pending_approval_first_in_my_work(client, headers):
    d = _dash(client, headers, "U14")
    assert _kpis(d)["my_pending_approvals"]["value"] == 1
    first = d["my_work"][0]
    assert first["kind"] == "approval"
    assert first["link"] == f"/approvals?request={first['id']}"
    assert first["due_label"].startswith("Waiting ")
    assert all(w["kind"] != "approval" for w in d["my_work"][1:])


def test_my_work_order_and_cap(client, headers):
    d = _dash(client, headers, "U14")  # IRM owns the compliance items of every transition
    assert d["my_work_total"] > 25 and len(d["my_work"]) == d["my_work_total"] <= 200
    assert d["my_work"][0]["kind"] == "approval"
    items = [w for w in d["my_work"] if w["kind"] == "item"]
    crit = [w for w in items if w["gap_severity"] == "Critical"]
    assert items[: len(crit)] == crit  # critical gaps before everything else


def test_leadership_dashboard(client, headers):
    d = _dash(client, headers, "U15")
    assert d["my_work"] == [] and d["my_work_total"] == 0
    tiles = d["portfolio_tiles"]
    assert [t["portfolio"] for t in tiles] == [
        "GCC",
        "eMobility",
        "Global Marketing",
        "Fleets",
        "Telecoms",
        "Retail Site Systems",
    ]
    assert [t["transitions"] for t in tiles] == [
        1
    ] * 6  # one sample transition per portfolio (A-109)
    retail = tiles[-1]  # TR-0008 (Red)
    assert retail["red"] == 1 and retail["transitions"] == 1
    assert retail["red"] + retail["amber"] + retail["green"] + retail["grey"] == 1
    kpis = _kpis(d)
    assert list(kpis) == ["active", "red", "decisions_14d", "critical"]
    assert kpis["red"]["link"] == "/control-tower?rag=Red"
    assert kpis["decisions_14d"]["link"] == "/control-tower?decision_within_days=14"


def test_recent_activity(client, headers, db):
    from sqlalchemy import select

    from app.models import AuditEvent

    for user in ("U01", "U14", "U15"):
        events = _dash(client, headers, user)["recent_activity"]
        assert len(events) <= 10
        ats = [e["at"] for e in events]
        assert ats == sorted(ats, reverse=True)
        for e in events:
            if e["transition_id"]:
                assert e["transition_name"]
    d = _dash(client, headers, "U01")
    mine = OWNED
    assert d["recent_activity"] and all(e["transition_id"] in mine for e in d["recent_activity"])
    expected = db.scalars(
        select(AuditEvent.id)
        .where(AuditEvent.transition_id.in_(mine))
        .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
        .limit(10)
    ).all()
    assert [e["id"] for e in d["recent_activity"]] == list(expected)


def test_pending_approvals_match_inbox_rule(client, headers):
    users = ("U01", "U10", "U11", "U12", "U13", "U14", "U15", "U16")
    for user in users:
        inbox = client.get(f"{API}/approvals", params={"scope": "mine"}, headers=headers(user))
        can_act = [a for a in inbox.json() if a["can_act"]]
        d = _dash(client, headers, user)
        assert _kpis(d).get("my_pending_approvals", {"value": 0})["value"] == len(can_act), user
        assert len([w for w in d["my_work"] if w["kind"] == "approval"]) == len(can_act), user


def test_pending_approval_requires_the_named_approver(client, headers, db, fresh_seed):
    from sqlalchemy import select

    from app.models import ApprovalStep

    step = db.scalars(select(ApprovalStep).where(ApprovalStep.status == "Pending")).first()
    assert step is not None
    owner = step.approver_user_id
    assert (
        owner is None or _kpis(_dash(client, headers, owner))["my_pending_approvals"]["value"] >= 1
    )
    step.approver_user_id = (
        "U13"  # somebody else is named: others of the same role no longer see it
    )
    db.commit()
    assert _kpis(_dash(client, headers, "U13"))["my_pending_approvals"]["value"] >= 1
    if owner and owner != "U13":
        mine = [w for w in _dash(client, headers, owner)["my_work"] if w["kind"] == "approval"]
        assert step.request_id not in {w["id"] for w in mine}


def test_dashboard_excludes_not_launched_from_portfolio_averages(client, headers, db, fresh_seed):
    from sqlalchemy import delete

    from app.models import Transition, TransitionItem

    t = db.get(Transition, "TR-0003")
    t.portfolio = portfolio = "GCC"  # share a portfolio with the launched TR-0001
    db.execute(delete(TransitionItem).where(TransitionItem.transition_id == "TR-0003"))
    t.assessment_launched_at = None
    db.commit()
    tiles = {x["portfolio"]: x for x in _dash(client, headers, "U15")["portfolio_tiles"]}
    rows = client.get(f"{API}/transitions", params={"portfolio": portfolio}, headers=headers())
    scores = [r["overall_readiness"] for r in rows.json() if r["assessment_launched"]]
    assert tiles[portfolio]["grey"] >= 1
    assert tiles[portfolio]["average_readiness"] == int(sum(scores) / len(scores) + 0.5)


def test_subtitle_is_role_label_plus_portfolios(client, headers):
    d = _dash(client, headers, "U01")
    assert d["subtitle"].startswith("OR focal (S&T)")
    assert "OR focal A" not in d["subtitle"]  # the login placeholder is not repeated
    assert " · " in d["subtitle"] and "GCC" in d["subtitle"]
    leadership = _dash(client, headers, "U15")["subtitle"]
    assert leadership.startswith("Leadership")


def test_seed_events_sit_at_the_start_of_the_demo_day(client, headers, db):
    """The demo clock uses the real time of day, so seed events must never sort after later work."""
    from datetime import datetime, time

    from sqlalchemy import select

    from app import clock
    from app.models import AuditEvent

    seeded = db.scalars(select(AuditEvent).where(AuditEvent.action == "seeded")).all()
    assert seeded and all(e.at == datetime.combine(clock.today(), time.min) for e in seeded)
    events = _dash(client, headers, "U01")["recent_activity"]
    ats = [e["at"] for e in events]
    assert ats == sorted(ats, reverse=True)
