"""CR-01 acceptance B: a new portfolio ("Fuels EU") with its golden set, added through configuration only.

Whether a portfolio asks for site rows is the portfolio's "Requires sites" switch, not its name.
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain import cfg
from app.models import PlaybookItem, Portfolio, Transition, TransitionItem
from tests.config_helpers import API, add_golden_set, add_portfolio, new_transition

PORTFOLIO = "Fuels EU"
GOLDEN = [
    {"title": "Fuel price feed validated", "gate": "SG2", "lens": "Technical", "mandatory": True},
    {"title": "Station signage plan", "gate": "SG3", "lens": "Business", "mandatory": False},
]


def _configure(client, headers, db, **extra) -> None:
    add_portfolio(
        client, headers, db, PORTFOLIO, "FEU", focus_areas=["Pricing", "Compliance"], **extra
    )
    add_golden_set(client, headers, db, PORTFOLIO, GOLDEN)


def test_acceptance_b_new_portfolio_with_golden_set(client, headers, db, fresh_seed):
    _configure(client, headers, db)

    ref = client.get(f"{API}/reference", headers=headers("U01")).json()
    assert PORTFOLIO in ref["portfolios"]
    detail = next(p for p in ref["portfolio_details"] if p["name"] == PORTFOLIO)
    assert detail["golden_set_count"] == 2 and detail["golden_set_mandatory_count"] == 1
    assert detail["requires_sites"] is False

    res = new_transition(client, headers, portfolio=PORTFOLIO)
    assert res.status_code == 201, res.text
    tid = res.json()["id"]

    scope = client.get(f"{API}/transitions/{tid}/scope", headers=headers("U01")).json()
    assert scope["focus_areas"] == ["Pricing", "Compliance"]
    assert {r["requirement"]: r["applies"] for r in scope["golden_set"]} == {
        "Fuel price feed validated": "Yes",  # mandatory rows are locked to Yes
        "Station signage plan": "To confirm",
    }

    assert (
        client.post(
            f"{API}/transitions/{tid}/launch-assessment", headers=headers("U01")
        ).status_code
        == 200
    )
    db.expire_all()
    golden = {
        p.title: i.applicability
        for i, p in (
            (i, i.playbook_item)
            for i in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid))
        )
        if p.source == "PORTFOLIO"
    }
    assert golden == {"Fuel price feed validated": "Applies", "Station signage plan": "To confirm"}


def test_other_portfolios_golden_sets_are_not_picked(client, headers, db, fresh_seed):
    _configure(client, headers, db)
    tid = new_transition(client, headers, portfolio="GCC").json()["id"]
    client.post(f"{API}/transitions/{tid}/launch-assessment", headers=headers("U01"))
    db.expire_all()
    portfolios = {
        i.playbook_item.portfolio
        for i in db.scalars(select(TransitionItem).where(TransitionItem.transition_id == tid))
        if i.playbook_item.source == "PORTFOLIO"
    }
    assert portfolios == {"GCC"}


def test_requires_sites_switch_drives_site_rows(client, headers, db, fresh_seed):
    _configure(client, headers, db, requires_sites=True, sites_label="Fuel stations")

    none = new_transition(client, headers, portfolio=PORTFOLIO)
    assert none.status_code == 422
    assert any("Add at least one site" in r and PORTFOLIO in r for r in none.json()["reasons"])

    ok = new_transition(
        client, headers, portfolio=PORTFOLIO, sites=[{"site_id": "S-1", "site_key": "K-1"}]
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["sites"] == [{"site_id": "S-1", "site_key": "K-1"}]


def test_sites_are_dropped_for_a_portfolio_that_does_not_need_them(client, headers, fresh_seed):
    res = new_transition(
        client, headers, portfolio="GCC", sites=[{"site_id": "S-1", "site_key": "K-1"}]
    )
    assert res.status_code == 201, res.text
    assert res.json()["sites"] == []


def test_retail_keeps_asking_for_sites_from_its_switch(client, headers, db, fresh_seed):
    assert cfg.portfolio_requires_sites(db, "Retail Site Systems") is True
    assert new_transition(client, headers, portfolio="Retail Site Systems").status_code == 422

    # Switch it off: the same portfolio no longer asks for sites (no code involved).
    row = db.get(Portfolio, "Retail Site Systems")
    row.requires_sites = False
    db.commit()
    cfg.invalidate()
    assert new_transition(client, headers, portfolio="Retail Site Systems").status_code == 201


def test_relabelling_a_portfolio_changes_no_code_or_data(client, headers, db, fresh_seed):
    _configure(client, headers, db)
    tid = new_transition(client, headers, portfolio=PORTFOLIO).json()["id"]
    res = client.patch(
        f"{API}/admin/portfolios/{PORTFOLIO}",
        json={"label": "Fuels Europe"},
        headers=headers("U16"),
    )
    if res.status_code == 501:  # write endpoint not built yet: relabel the row directly
        db.get(Portfolio, PORTFOLIO).label = "Fuels Europe"
        db.commit()
    else:
        assert res.status_code == 200, res.text
    cfg.invalidate()

    detail = client.get(f"{API}/transitions/{tid}", headers=headers("U01")).json()
    assert detail["portfolio"] == PORTFOLIO  # the stored code stays
    assert (
        detail["flavour_label"] == "Normal · Fuels Europe · Global"
    )  # the label is what people see
    db.expire_all()
    assert db.get(Transition, tid).portfolio == PORTFOLIO
    assert db.scalars(select(PlaybookItem).where(PlaybookItem.portfolio == PORTFOLIO)).first()


def test_deactivated_portfolio_is_not_offered_to_new_transitions(client, headers, db, fresh_seed):
    _configure(client, headers, db)
    tid = new_transition(client, headers, portfolio=PORTFOLIO).json()["id"]
    db.get(Portfolio, PORTFOLIO).active = False
    db.commit()
    cfg.invalidate()

    assert new_transition(client, headers, portfolio=PORTFOLIO).status_code == 422
    assert (
        PORTFOLIO not in client.get(f"{API}/reference", headers=headers("U01")).json()["portfolios"]
    )
    # the existing transition still opens and can be edited
    res = client.patch(
        f"{API}/transitions/{tid}", json={"description": "edited"}, headers=headers("U01")
    )
    assert res.status_code == 200, res.text
