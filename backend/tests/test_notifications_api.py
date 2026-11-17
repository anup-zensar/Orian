"""Notification fan-out (spec 10.2/10.3) and the outbox/notification endpoints."""

from __future__ import annotations

from app.domain.notify import deliver

API = "/api/v1"


def test_deliver_fans_out_in_app_email_and_teams(client, headers, db, fresh_seed):
    card = {"type": "AdaptiveCard", "version": "1.5", "body": [], "actions": []}
    deliver(
        db,
        user_ids=["U14", "U14", "U-UNKNOWN", "U01"],
        text="Hello there",
        link="/approvals",
        email_subject="Subject",
        email_html="<p>Hi</p><script>x()</script>",
        teams_card=card,
        related_ids=["TR-0001"],
    )
    db.commit()
    deliver(db, user_ids=[], text="nothing", link="/")  # no-op
    db.commit()

    assert client.get(f"{API}/notifications", headers=headers("U14")).json()["unread"] == 1
    items = client.get(f"{API}/notifications", headers=headers("U01")).json()["items"]
    assert items[0]["text"] == "Hello there" and items[0]["link"] == "/approvals"

    emails = client.get(
        f"{API}/outbox",
        params={"channel": "Email", "transition_id": "TR-0001"},
        headers=headers("U01"),
    ).json()
    assert len(emails) == 2  # one per unique known user
    assert all("script" not in m["body_html"] for m in emails)
    teams = client.get(
        f"{API}/outbox",
        params={"channel": "Teams", "transition_id": "TR-0001"},
        headers=headers("U01"),
    ).json()
    assert len(teams) == 1 and teams[0]["adaptive_card_json"] == card
    assert len(teams[0]["to"]) == 2
    other = client.get(
        f"{API}/outbox", params={"transition_id": "TR-0002"}, headers=headers("U01")
    ).json()
    assert other == []


def test_notifications_require_sign_in(client):
    assert client.get(f"{API}/notifications").status_code == 401
    assert client.get(f"{API}/outbox").status_code == 401
