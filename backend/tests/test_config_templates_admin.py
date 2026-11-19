"""CR-01 admin "Messages": save and preview the wording of Orion's drafts. Only a template's own
placeholders are allowed, values are HTML-escaped, and recipients / send policy can never change
here ("Orion drafts, you decide")."""

from __future__ import annotations

import pytest

from app.domain import cfg, cfg_defaults
from app.models import AuditEvent

API = "/api/v1"
ADMIN = "U16"


def _templates(client, headers) -> dict[str, dict]:
    r = client.get(f"{API}/admin/message-templates", headers=headers(ADMIN))
    assert r.status_code == 200, r.text
    return {t["key"]: t for t in r.json()}


def _put(client, headers, *templates: dict, user: str = ADMIN):
    return client.put(
        f"{API}/admin/message-templates", json={"templates": list(templates)}, headers=headers(user)
    )


def test_every_draft_kind_is_listed_with_its_placeholders(client, headers) -> None:
    listed = _templates(client, headers)
    assert set(listed) == set(cfg_defaults.DEFAULT_TEMPLATES)
    chaser = listed["chaser"]
    assert (
        chaser["subject"] == chaser["default_subject"] and chaser["body"] == chaser["default_body"]
    )
    assert chaser["code_source"] and "Orion drafts, you decide" in chaser["notice"]
    names = {p["name"] for p in chaser["placeholders"]}
    assert {"recipient_name", "transition_name", "item_list", "deep_link", "greeting"} <= names
    assert {p["name"] for p in chaser["placeholders"] if p["html"]} >= {"item_list", "greeting"}
    assert "recipients" not in chaser and "send_policy" not in chaser  # not part of a template


def test_save_a_template_changes_what_cfg_returns(client, headers, fresh_seed, db) -> None:
    saved = _put(
        client,
        headers,
        {
            "key": "chaser",
            "subject": "Quick nudge: {{transition_name}} ({{gate_short}})",
            "body": "<p>{{greeting}}</p><p>Please look at {{item_list}}</p>{{sign_off}}",
            "enabled": True,
        },
    )
    assert saved.status_code == 200, saved.text
    chaser = next(t for t in saved.json() if t["key"] == "chaser")
    assert chaser["subject"].startswith("Quick nudge") and chaser["default_subject"].startswith(
        "Action needed"
    )
    assert chaser["is_default"] is False
    template = cfg.template(db, "chaser")
    assert template is not None and template.subject.startswith("Quick nudge")
    out = cfg.render_template(
        template,
        {
            "transition_name": "TR <1>",
            "gate_short": "AtD",
            "greeting": "Hi,",
            "item_list": "<ul></ul>",
            "sign_off": "",
        },
    )
    assert out["subject"] == "Quick nudge: TR <1> (AtD)"  # the subject is plain text
    other = _templates(client, headers)["reminder"]
    assert other["is_default"] is False or other["subject"] == other["default_subject"]  # untouched
    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity == "config:message_templates")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert event.actor_type == "Human" and event.entity_id == "chaser"
    assert event.before["subject"].startswith("Action needed") and event.after[
        "subject"
    ].startswith("Quick nudge")


def test_disable_flag_is_stored(client, headers, fresh_seed) -> None:
    current = _templates(client, headers)["reminder"]
    r = _put(
        client,
        headers,
        {
            "key": "reminder",
            "subject": current["subject"],
            "body": current["body"],
            "enabled": False,
        },
    )
    assert next(t for t in r.json() if t["key"] == "reminder")["enabled"] is False


@pytest.mark.parametrize(
    ("subject", "body", "needle"),
    [
        ("Hello {{secret_field}}", "<p>{{greeting}}</p>", "{{secret_field}}"),
        ("Fine", "<p>{{ recipient_password }}</p>", "{{recipient_password}}"),
        ("Fine", "<script>alert(1)</script>", "scripts"),
        ("Fine", '<a href="javascript:steal()">x</a>', "scripts"),
        ("Fine", '<p onclick="x()">x</p>', "scripts"),
        ("Fine", "{{leadership_only}}", "{{leadership_only}}"),
    ],
)
def test_unknown_placeholders_and_scripts_refuse_the_save(
    client, headers, fresh_seed, subject, body, needle
) -> None:
    before = _templates(client, headers)["chaser"]
    r = _put(client, headers, {"key": "chaser", "subject": subject, "body": body})
    assert r.status_code == 422, r.text
    assert needle in " ".join(r.json()["reasons"])
    assert _templates(client, headers)["chaser"]["body"] == before["body"]  # nothing saved


def test_placeholders_belong_to_their_template(client, headers, fresh_seed) -> None:
    """``approver_name`` exists for the escalation template only."""
    r = _put(client, headers, {"key": "chaser", "subject": "{{approver_name}}", "body": "x"})
    assert r.status_code == 422 and "{{approver_name}}" in r.json()["reasons"][0]
    ok = _put(
        client,
        headers,
        {
            "key": "escalation",
            "subject": "{{approver_name}} is late",
            "body": "<p>{{approver_name}}</p>",
        },
    )
    assert ok.status_code == 200


def test_unknown_key_and_all_or_nothing(client, headers, fresh_seed) -> None:
    r = _put(
        client,
        headers,
        {"key": "chaser", "subject": "New subject", "body": "<p>{{greeting}}</p>"},
        {"key": "no_such_message", "subject": "x", "body": "y"},
    )
    assert r.status_code == 422 and "Unknown message 'no_such_message'" in r.json()["reasons"][0]
    assert _templates(client, headers)["chaser"]["subject"].startswith(
        "Action needed"
    )  # the valid one was not saved either


def test_preview_escapes_values_and_lists_unknown_placeholders(client, headers) -> None:
    r = client.post(
        f"{API}/admin/message-templates/chaser/preview",
        json={
            "subject": "{{transition_name}} {{ nope }}",
            "body": "<p>{{greeting}} {{transition_name}}</p>{{item_list}}",
            "context": {"transition_name": "<b>X</b> & Y"},
        },
        headers=headers(ADMIN),
    )
    out = r.json()
    assert out["unknown_placeholders"] == ["nope"]
    assert "&lt;b&gt;X&lt;/b&gt; &amp; Y" in out["body_html"]  # a value is escaped
    assert "<ul>" in out["body_html"]  # an html placeholder (item_list) is inserted as given
    # saved preview of the stored default
    saved = client.post(
        f"{API}/admin/message-templates/chaser/preview", json={}, headers=headers(ADMIN)
    ).json()
    assert "Mobility Knowledge Agent" in saved["subject"] and saved["unknown_placeholders"] == []


def test_preview_writes_nothing(client, headers, db) -> None:
    before = db.query(AuditEvent).count()
    client.post(
        f"{API}/admin/message-templates/chaser/preview",
        json={"body": "{{greeting}}"},
        headers=headers(ADMIN),
    )
    db.expire_all()
    assert db.query(AuditEvent).count() == before


def test_only_the_admin_edits_templates(client, headers, fresh_seed) -> None:
    body = {"key": "chaser", "subject": "x", "body": "y"}
    for user in ("U01", "U14", "U15"):
        assert _put(client, headers, body, user=user).status_code == 403
        assert (
            client.post(
                f"{API}/admin/message-templates/chaser/preview", json={}, headers=headers(user)
            ).status_code
            == 403
        )
    assert (
        client.put(f"{API}/admin/message-templates", json={"templates": [body]}).status_code == 401
    )
