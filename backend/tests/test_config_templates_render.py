"""Message templates (CR-01, Admin > Messages): the default templates give EXACTLY the text the
code produced before templates existed, for every draft kind and reminder variant; a saved template
changes the wording; a switched-off or missing template falls back to the default; values stay
HTML-escaped. Orion only drafts - nothing here sends a message (BR-050)."""

from __future__ import annotations

from app.domain import cfg, cfg_defaults
from app.domain.notify import message_templates
from app.models import MessageTemplate
from app.services.mock.ai_messages import draft_message

API = "/api/v1"

CASES: dict[str, tuple[str, dict]] = {
    "chaser_one": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "gate_short": "AtD",
            "days": 21,
            "items": [
                {
                    "id": "S3-019",
                    "title": "DPIA <done>",
                    "due_gate_short": "AtD",
                    "owner_name": "Tom",
                }
            ],
        },
    ),
    "chaser_two": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "gate_short": "AtD",
            "days": -2,
            "items": [
                {
                    "id": "S3-019",
                    "title": "DPIA <done>",
                    "due_gate_short": "AtD",
                    "owner_name": "Tom",
                },
                {
                    "id": "FW-006",
                    "title": "Support model evidence",
                    "deep_link": "http://x/y?item=1",
                },
            ],
            "deep_link": "http://x/y",
        },
    ),
    "chaser_today": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "gate_short": "AtO",
            "days": 0,
            "items": [
                {
                    "id": "S3-019",
                    "title": "DPIA <done>",
                    "due_gate_short": "AtD",
                    "owner_name": "Tom",
                }
            ],
        },
    ),
    "chaser_noitems": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
        },
    ),
    "chaser_noname": (
        "chaser",
        {
            "transition_name": "T",
            "items": [
                {
                    "id": "FW-006",
                    "title": "Support model evidence",
                    "deep_link": "http://x/y?item=1",
                }
            ],
        },
    ),
    "overdue": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "days_overdue": 3,
            "action_title": "Fix <it>",
            "due_date": "2026-11-13",
            "deep_link": "http://x/a",
        },
    ),
    "overdue_one": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "days_overdue": 1,
            "due_date": "2026-11-15",
        },
    ),
    "escalation": (
        "chaser",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "escalation": True,
            "approver_name": "Olu",
            "gate_short": "AtD",
            "days_pending": 6,
            "deep_link": "http://x/g",
        },
    ),
    "escalation_min": (
        "chaser",
        {"transition_name": "T", "escalation": True, "days_pending": 1},
    ),
    "reminder": (
        "reminder",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "gate_short": "AtD",
            "days": 5,
            "items": [
                {
                    "id": "S3-019",
                    "title": "DPIA <done>",
                    "due_gate_short": "AtD",
                    "owner_name": "Tom",
                },
                {
                    "id": "FW-006",
                    "title": "Support model evidence",
                    "deep_link": "http://x/y?item=1",
                },
            ],
        },
    ),
    "reminder_one": (
        "reminder",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "items": [
                {
                    "id": "S3-019",
                    "title": "DPIA <done>",
                    "due_gate_short": "AtD",
                    "owner_name": "Tom",
                }
            ],
        },
    ),
    "pending_step": (
        "reminder",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "pending_step": True,
            "gate_short": "AtD",
            "days_pending": 3,
            "deep_link": "http://x/p",
        },
    ),
    "monitoring": (
        "reminder",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "monitoring": True,
            "items": [
                {
                    "id": "S3-019",
                    "title": "DPIA <done>",
                    "due_gate_short": "AtD",
                    "owner_name": "Tom",
                },
                {
                    "id": "FW-006",
                    "title": "Support model evidence",
                    "deep_link": "http://x/y?item=1",
                },
            ],
            "deep_link": "http://x/m",
        },
    ),
    "support_model": (
        "reminder",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "support_model": True,
            "subject": "Create support model now?",
            "deep_link": "http://x/s",
        },
    ),
    "support_model_nosubj": (
        "reminder",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "support_model": True,
        },
    ),
    "input_request": (
        "input request",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "items": [{"id": "L1", "title": "Hosting cost"}, {"id": "L2", "title": "Licences"}],
        },
    ),
    "approval": (
        "approval request",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "gate_short": "AtD",
            "verdict": "Ready with conditions",
            "approver_role": "OLM",
            "summary": "All <good>.",
            "deep_link": "http://x/y",
        },
    ),
    "approval_r4": (
        "approval request",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "gate": "SG4_ATD",
            "gate_short": "AtD",
            "verdict": "Ready",
            "approver_role": "",
            "summary": "Fine.",
        },
    ),
    "approval_min": (
        "approval request",
        {"transition_name": "T"},
    ),
    "leadership": (
        "leadership update",
        {
            "transition_id": "TR-0001",
            "transition_name": "Mobility Knowledge Agent <b>",
            "recipient_name": "Tom & Co",
            "or_focal_name": "Asha Menon",
            "scope": "Q4 <portfolio>",
            "text": "Line one.\nLine two.\n\nSecond & paragraph.",
        },
    ),
    "leadership_min": (
        "leadership update",
        {"transition_name": "T", "text": ""},
    ),
}


# What the code produced before message templates existed (captured from the old builders).
LEGACY: dict[str, dict[str, str]] = {
    "chaser_one": {
        "subject": "Action needed: DPIA <done> for Mobility Knowledge Agent <b> (AtD in 21 days)",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is heading to AtD in 21 days. Could you please update this item or let us know what is blocking you?</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> DPIA &lt;done&gt; (due at AtD, Tom)</li></ul><p><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "chaser_two": {
        "subject": "Action needed: DPIA <done> and 1 other item for Mobility Knowledge Agent <b> (AtD overdue by 2 days)",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is heading to AtD overdue by 2 days. Could you please update these items or let us know what is blocking you?</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> DPIA &lt;done&gt; (due at AtD, Tom)</li><li><a href="http://x/y?item=1">FW-006</a> Support model evidence (due at AtD)</li></ul><p><a href="http://x/y">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "chaser_today": {
        "subject": "Action needed: DPIA <done> for Mobility Knowledge Agent <b> (AtO today)",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is heading to AtO today. Could you please update this item or let us know what is blocking you?</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> DPIA &lt;done&gt; (due at AtD, Tom)</li></ul><p><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "chaser_noitems": {
        "subject": "Action needed: open items for Mobility Knowledge Agent <b>",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is heading to its next gate. Could you please update these items or let us know what is blocking you?</p><p><a href="http://localhost:5173/transitions/TR-0001/assessment?item=">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "chaser_noname": {
        "subject": "Action needed: Support model evidence for T",
        "body_html": '<p>Hello,</p><p>T is heading to its next gate. Could you please update this item or let us know what is blocking you?</p><ul><li><a href="http://x/y?item=1">FW-006</a> Support model evidence</li></ul><p><a href="http://x/y?item=1">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of the OR focal</p>',
    },
    "overdue": {
        "subject": "Overdue action: Fix <it> for Mobility Knowledge Agent <b> (3 days overdue)",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>The action <strong>Fix &lt;it&gt;</strong> for Mobility Knowledge Agent &lt;b&gt; was due 2026-11-13 and is now overdue by 3 days. Could you please update it or let us know what is blocking you?</p><p><a href="http://x/a">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "overdue_one": {
        "subject": "Overdue action: an action for Mobility Knowledge Agent <b> (1 day overdue)",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>The action <strong>an action</strong> for Mobility Knowledge Agent &lt;b&gt; was due 2026-11-15 and is now overdue by 1 day. Could you please update it or let us know what is blocking you?</p><p><a href="http://localhost:5173">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "escalation": {
        "subject": "Escalation: AtD approval for Mobility Knowledge Agent <b> pending 6 days",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Olu has not yet decided the AtD approval for Mobility Knowledge Agent &lt;b&gt;; it has been pending for 6 days. You may want to follow up with them directly.</p><p><a href="http://x/g">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "escalation_min": {
        "subject": "Escalation: the gate approval for T pending 1 day",
        "body_html": '<p>Hello,</p><p>The approver has not yet decided the the gate approval for T; it has been pending for 1 day. You may want to follow up with them directly.</p><p><a href="http://localhost:5173">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of the OR focal</p>',
    },
    "reminder": {
        "subject": "Reminder: 2 open items for Mobility Knowledge Agent <b> (AtD in 5 days)",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>A friendly reminder that 2 items for Mobility Knowledge Agent &lt;b&gt; are still open.</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> DPIA &lt;done&gt; (due at AtD, Tom)</li><li><a href="http://x/y?item=1">FW-006</a> Support model evidence (due at AtD)</li></ul><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "reminder_one": {
        "subject": "Reminder: 1 open item for Mobility Knowledge Agent <b>",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>A friendly reminder that 1 item for Mobility Knowledge Agent &lt;b&gt; is still open.</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> DPIA &lt;done&gt; (due at AtD, Tom)</li></ul><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "pending_step": {
        "subject": "Reminder: AtD approval for Mobility Knowledge Agent <b> is waiting for you",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Your approval of AtD for Mobility Knowledge Agent &lt;b&gt; has been pending for 3 days. Please review and decide in Orion.</p><p><a href="http://x/p">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "monitoring": {
        "subject": "Monitoring requirements for Mobility Knowledge Agent <b>",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is in the design stage. Please capture the monitoring requirements below with the team.</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> DPIA &lt;done&gt; (due at AtD, Tom)</li><li><a href="http://x/y?item=1">FW-006</a> Support model evidence</li></ul><p><a href="http://x/m">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "support_model": {
        "subject": "Create support model now?",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>The support-model evidence for Mobility Knowledge Agent &lt;b&gt; has been accepted. Orion can now prepare the support model.</p><p><a href="http://x/s">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "support_model_nosubj": {
        "subject": "Create support model now?",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>The support-model evidence for Mobility Knowledge Agent &lt;b&gt; has been accepted. Orion can now prepare the support model.</p><p><a href="http://localhost:5173">Open in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "input_request": {
        "subject": "Input needed: 2 inputs for Mobility Knowledge Agent <b>",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>To complete the estimate for Mobility Knowledge Agent &lt;b&gt; we still need your input on:</p><ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=L1">L1</a> Hosting cost</li><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=L2">L2</a> Licences</li></ul><p>Please reply with the figures or add them directly in Orion.</p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "approval": {
        "subject": "Approval request: AtD for Mobility Knowledge Agent <b>",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is ready for your approval at AtD (readiness: Ready with conditions).</p><p>All &lt;good&gt;.</p><p>First approver: OLM.</p><p><a href="http://x/y">Review and approve in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "approval_r4": {
        "subject": "Approval request: AtD for Mobility Knowledge Agent <b>",
        "body_html": '<p>Hi Tom &amp; Co,</p><p>Mobility Knowledge Agent &lt;b&gt; is ready for your approval at AtD (readiness: Ready).</p><p>Fine.</p><p><a href="http://localhost:5173/transitions/TR-0001/gates">Review and approve in Orion</a></p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>',
    },
    "approval_min": {
        "subject": "Approval request: gate for T",
        "body_html": '<p>Hello,</p><p>T is ready for your approval at gate.</p><p><a href="http://localhost:5173/transitions//gates">Review and approve in Orion</a></p><p>Thank you,<br>Orion, on behalf of the OR focal</p>',
    },
    "leadership": {
        "subject": "Leadership update: Q4 <portfolio>",
        "body_html": "<p>Hi Tom &amp; Co,</p><p>Line one.<br>Line two.</p><p>Second &amp; paragraph.</p><p>Thank you,<br>Orion, on behalf of Asha Menon</p>",
    },
    "leadership_min": {
        "subject": "Leadership update: T",
        "body_html": "<p>Hello,</p><p>Thank you,<br>Orion, on behalf of the OR focal</p>",
    },
}


def test_every_default_template_key_has_a_code_default() -> None:
    assert set(cfg.template_keys()) == set(cfg_defaults.DEFAULT_TEMPLATES)
    assert len(cfg.template_keys()) == 10


def test_default_output_equals_the_legacy_text_for_every_draft_kind() -> None:
    """No templates passed = the code defaults."""
    assert set(CASES) == set(LEGACY)
    for name, (kind, ctx) in CASES.items():
        assert draft_message(kind, ctx) == LEGACY[name], name


def test_seeded_templates_give_the_same_text_as_the_defaults(db, fresh_seed) -> None:
    """The templates stored by the seed (what the Messages page shows) equal the legacy text."""
    templates = message_templates(db)
    assert all(not t.is_default for t in templates.values())  # real rows
    for name, (kind, ctx) in CASES.items():
        assert draft_message(kind, {**ctx, "templates": templates}) == LEGACY[name], name


def _save(db, key: str, **changes) -> None:
    row = db.get(MessageTemplate, key)
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    cfg.invalidate()


def test_a_saved_template_changes_the_wording(db, fresh_seed) -> None:
    _save(
        db,
        "chaser",
        subject="Please help: {{item_title}} ({{transition_name}})",
        body="<p>{{greeting}}</p><p>Quick nudge about {{transition_name}}.</p>{{item_list}}",
    )
    kind, ctx = CASES["chaser_one"]
    out = draft_message(kind, {**ctx, "templates": message_templates(db)})
    assert out["subject"] == "Please help: DPIA <done> (Mobility Knowledge Agent <b>)"
    assert out["body_html"].startswith("<p>Hi Tom &amp; Co,</p><p>Quick nudge about ")
    assert "Orion, on behalf of" not in out["body_html"]  # the sign-off is only there if used
    # the other templates are untouched
    kind, ctx = CASES["reminder"]
    assert draft_message(kind, {**ctx, "templates": message_templates(db)}) == LEGACY["reminder"]


def test_values_are_escaped_but_the_subject_is_plain_text(db, fresh_seed) -> None:
    _save(db, "leadership_update", subject="{{scope}}", body="<p>{{scope}}</p>{{paragraphs}}")
    kind, ctx = CASES["leadership"]
    out = draft_message(kind, {**ctx, "templates": message_templates(db)})
    assert out["subject"] == "Q4 <portfolio>"
    assert out["body_html"].startswith("<p>Q4 &lt;portfolio&gt;</p><p>Line one.<br>Line two.</p>")
    assert "<script>" not in out["body_html"]


def test_unknown_placeholder_renders_empty_and_switched_off_template_uses_default(
    db, fresh_seed
) -> None:
    _save(db, "input_request", subject="S {{nope}}x", body="<p>{{nope}}{{transition_name}}</p>")
    kind, ctx = CASES["input_request"]
    out = draft_message(kind, {**ctx, "templates": message_templates(db)})
    assert out["subject"] == "S x"
    assert out["body_html"] == "<p>Mobility Knowledge Agent &lt;b&gt;</p>"
    _save(db, "input_request", enabled=False)
    assert (
        draft_message(kind, {**ctx, "templates": message_templates(db)}) == LEGACY["input_request"]
    )


def test_a_missing_row_falls_back_to_the_code_default(db, fresh_seed) -> None:
    db.delete(db.get(MessageTemplate, "approval_request"))
    db.commit()
    cfg.invalidate()
    templates = message_templates(db)
    assert templates["approval_request"].is_default
    kind, ctx = CASES["approval"]
    assert draft_message(kind, {**ctx, "templates": templates}) == LEGACY["approval"]


def test_chaser_draft_from_the_api_uses_the_saved_template(client, headers, db, fresh_seed) -> None:
    _save(db, "chaser", subject="Nudge: {{item_title}}")
    res = client.post(
        f"{API}/orion/drafts/chaser",
        json={"transition_id": "TR-0001", "item_ids": ["S45-014"]},
        headers=headers("U01"),
    )
    assert res.status_code == 201, res.text
    assert res.json()["subject"].startswith("Nudge: ")
    assert res.json()["created_source"] == "Orion agent"


def test_approval_request_draft_uses_the_saved_template(client, headers, db, fresh_seed) -> None:
    from app.domain.drafts import approval_request_message
    from app.models import Transition, User

    _save(db, "approval_request", subject="Please approve {{gate_short}} - {{transition_name}}")
    transition = db.get(Transition, "TR-0001")
    to, cc, text = approval_request_message(db, transition, "SG4_ATD", db.get(User, "U01"))
    assert text["subject"] == f"Please approve SG4 (AtD) - {transition.name}"
    assert to and cc  # To = first approver, Cc = OR focal (unchanged by templates)
