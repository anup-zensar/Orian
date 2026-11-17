"""Adaptive Card templates (spec §10.4): valid JSON, required actions, renderer behaviour."""

from __future__ import annotations

import json

from app.services.cards import CARDS_DIR, TEMPLATE_NAMES, render_card


def test_templates_are_valid_adaptive_cards() -> None:
    for name in TEMPLATE_NAMES:
        card = json.loads((CARDS_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.5"
        assert any(a["type"] == "Action.OpenUrl" for a in card["actions"])


def test_approval_request_card_renders_facts_and_execute_actions() -> None:
    card = render_card(
        "approval_request",
        {
            "title": "AtD approval request – Mobility Knowledge Agent",
            "transition_name": "Mobility Knowledge Agent",
            "subject": "Agreement to Deploy",
            "facts": [
                {"title": "Verdict", "value": "Ready for AtD"},
                {"title": "Readiness", "value": "B 100% · T 100% · C 100%"},
                {"title": "Open conditions", "value": "1"},
            ],
            "step": 1,
            "step_count": 2,
            "step_label": "SOM OLM approval",
            "request_id": "APR-0002",
            "deep_link": "http://localhost:5173/approvals?request=APR-0002",
        },
    )
    assert card["body"][0]["text"] == "AtD approval request – Mobility Knowledge Agent"
    facts = card["body"][2]["facts"]
    assert [f["title"] for f in facts] == ["Verdict", "Readiness", "Open conditions"]
    approve, reject, open_url = card["actions"]
    assert approve["type"] == "Action.Execute" and approve["verb"] == "approve"
    assert reject["verb"] == "reject"
    assert approve["data"] == {"request_id": "APR-0002", "step": 1}  # whole-expression keeps type
    assert open_url["url"].endswith("APR-0002")
    assert card["body"][3]["text"] == "Step 1 of 2: SOM OLM approval"


def test_reminder_digest_repeats_items_and_tolerates_missing_values() -> None:
    card = render_card(
        "reminder_digest",
        {
            "count": 2,
            "owner_name": "Mei Lin",
            "transition_name": "Mobility Knowledge Agent",
            "gate_short": "AtD",
            "days": 12,
            "items": [
                {"title": "Red-team report", "due_gate": "AtD"},
                {"title": "Monitoring plan", "due_gate": "AtD"},
            ],
            "deep_link": "http://localhost:5173/transitions/TR-0001/assessment?mine=1",
        },
    )
    lines = [block["text"] for block in card["body"][2]["items"]]
    assert lines == ["• Red-team report (due AtD)", "• Monitoring plan (due AtD)"]
    assert (
        card["body"][3]["text"] == "Sent by Orion on behalf of ."
    )  # missing value -> "", no crash
