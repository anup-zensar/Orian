"""GET /orion/insights (FR-010, FR-011, BR-050)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import (
    Action,
    ApprovalRequest,
    AuditEvent,
    OrionDraft,
    OrionProposal,
    TransitionItem,
)
from app.services.mock.ai import MockAIService

API = "/api/v1"


def _ins(client, headers, user="U01", **params):
    res = client.get(f"{API}/orion/insights", params=params, headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def test_requires_header(client):
    assert client.get(f"{API}/orion/insights", params={"scope": "dashboard"}).status_code == 401


def test_dashboard_insights_deterministic_and_flagship(client, headers):
    first = _ins(client, headers, scope="dashboard")
    assert first == _ins(client, headers, scope="dashboard")
    assert first["generated_by"] == "Orion agent"
    assert first["scope"] == "dashboard"
    assert 1 <= len(first["insights"]) <= 5
    top = first["insights"][0]
    assert top["id"] == "TR-0001:critical-gap"
    assert top["text"] == (
        "Mobility Knowledge Agent: AtD in 21 days, blocked by 1 critical gap "
        "(S45-014 Agent / Use Case has undergone red-teaming exercise). Draft a chaser?"
    )
    assert [a["label"] for a in top["actions"]] == ["Open gaps", "Draft a chaser"]
    assert [a["href"] for a in top["actions"]] == [
        "/transitions/TR-0001/gaps",
        "/transitions/TR-0001/gaps?item=S45-014",
    ]


def test_dashboard_approvals_insight_for_irm(client, headers):
    ids = [i["id"] for i in _ins(client, headers, user="U14", scope="dashboard")["insights"]]
    assert "approvals:waiting" in ids


def test_dashboard_success_template():
    out = MockAIService().insights(
        {
            "scope": "dashboard",
            "user": {"id": "U99"},
            "critical_transitions": [],
            "approvals_waiting": [],
            "overdue_actions": [],
            "low_readiness": [],
        }
    )
    assert [i["text"] for i in out] == ["All your transitions are on track"]
    assert out[0]["severity"] == "success"


def test_control_tower_insights(client, headers):
    body = _ins(client, headers, scope="control-tower")
    assert body == _ins(client, headers, scope="control-tower")
    texts = [i["text"] for i in body["insights"]]
    assert 3 <= len(texts) <= 5
    assert "Forecourt POS refresh" in texts[0]
    assert any(t.startswith("Suggested ask for the leadership meeting") for t in texts)
    assert body["insights"][0]["severity"] == "critical"


def test_transition_insights(client, headers):
    body = _ins(client, headers, scope="transition", id="TR-0008")
    assert body["scope_id"] == "TR-0008"
    texts = " ".join(i["text"] for i in body["insights"])
    assert "AtD in 4 days" in texts
    assert "Lowest lens: Technical at 49%" in texts
    assert "Top gaps:" in texts
    assert 3 <= len(body["insights"]) <= 5


def test_transition_unknown_is_404(client, headers):
    res = client.get(
        f"{API}/orion/insights", params={"scope": "transition", "id": "TR-9999"}, headers=headers()
    )
    assert res.status_code == 404
    assert res.json()["detail"]


def test_invalid_scope_is_422(client, headers):
    res = client.get(f"{API}/orion/insights", params={"scope": "nope"}, headers=headers())
    assert res.status_code == 422


def test_insights_never_write_br050(client, headers, db):
    models = (AuditEvent, Action, ApprovalRequest, OrionDraft, OrionProposal, TransitionItem)

    def counts():
        return [db.scalar(select(func.count()).select_from(m)) for m in models]

    before = counts()
    for scope, extra in (
        ("dashboard", {}),
        ("control-tower", {}),
        ("transition", {"id": "TR-0001"}),
    ):
        for user in ("U01", "U14", "U15"):
            _ins(client, headers, user=user, scope=scope, **extra)
    db.expire_all()
    assert counts() == before


def test_item_labels_are_short_and_cut_at_word_boundaries():
    from app.services.mock.ai import _short

    assert _short("Evidence of data lineage (incl. DPIA attachments and sign-off)") == (
        "Evidence of data lineage"
    )
    long = "Documented and approved operational runbook covering incident response and rollback"
    out = _short(long)
    assert out.endswith("…") and len(out) <= 61 and long.startswith(out[:-1])
    assert long[len(out) - 1] == " "


def test_leadership_cannot_draft(client, headers):
    for user in ("U15",):
        for ins in _ins(client, headers, user=user, scope="dashboard")["insights"]:
            assert all(a["label"] != "Draft a chaser" for a in ins["actions"])
            assert "Draft a chaser" not in ins["text"]


def test_control_tower_insights_follow_filters(client, headers):
    api = f"{API}/transitions"
    ids = {
        r["id"]
        for r in client.get(
            api, params={"portfolio": "Retail Site Systems"}, headers=headers()
        ).json()
    }
    body = _ins(client, headers, scope="control-tower", portfolio="Retail Site Systems")
    assert body != _ins(client, headers, scope="control-tower")
    assert all(i["transition_id"] in ids for i in body["insights"] if i["transition_id"])


def test_not_launched_transition_insight_claims_no_readiness(client, headers, db, fresh_seed):
    from sqlalchemy import delete

    from app.models import Transition, TransitionItem

    t = db.get(Transition, "TR-0002")
    db.execute(delete(TransitionItem).where(TransitionItem.transition_id == "TR-0002"))
    t.assessment_launched_at = None
    db.commit()
    body = _ins(client, headers, scope="transition", id="TR-0002")
    text = " ".join(i["text"] for i in body["insights"])
    assert "has not been launched yet" in text and "%" not in text
    hrefs = [a["href"] for i in body["insights"] for a in i["actions"]]
    assert "/transitions/TR-0002/scope" in hrefs


def test_chaser_insight_carries_a_typed_action(client, headers):
    top = _ins(client, headers, scope="dashboard")["insights"][0]
    link, chaser = top["actions"]
    assert link["kind"] == "link" and link["item_id"] is None
    assert chaser["kind"] == "draft_chaser" and chaser["label"] == "Draft a chaser"
    assert chaser["transition_id"] == "TR-0001" and chaser["item_id"] == "S45-014"
    assert chaser["href"] == "/transitions/TR-0001/gaps?item=S45-014"  # link fallback
    # the button calls the normal user endpoint as the human: it drafts, nothing is sent
    res = client.post(
        f"{API}/orion/drafts/chaser",
        json={"transition_id": chaser["transition_id"], "item_ids": [chaser["item_id"]]},
        headers=headers("U01"),
    )
    assert res.status_code == 201 and res.json()["status"] == "Draft"
