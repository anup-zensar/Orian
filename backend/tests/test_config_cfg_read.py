"""CR-01 design 6: the cfg read API - lookups, defaults when rows are missing, cache and invalidate()."""

from __future__ import annotations

import pytest

from app.domain import cfg, cfg_defaults
from app.errors import BadRequest
from app.models import AppSetting, FlavourRule, MessageTemplate, OptionItem, OptionList, Portfolio


def test_option_lookups(db) -> None:
    assert cfg.option_label(db, "severities", "Critical") == "Critical"
    assert cfg.option_label(db, "severities", "Nope") == "Nope"  # unknown value shows itself
    assert cfg.option_meta(db, "action_priorities", "High") == {"color": "danger"}
    assert cfg.option_meta(db, "action_priorities", "Nope") == {}
    assert cfg.options(db, "no_such_list") == []
    assert cfg.option_list_exists(db, "regions") and not cfg.option_list_exists(db, "nope")


def test_validate_option_active_unknown_and_current(db) -> None:
    cfg.validate_option(db, "evidence_types", "Document")
    with pytest.raises(BadRequest) as exc:
        cfg.validate_option(db, "evidence_types", "Telepathy")
    assert exc.value.status_code == 422 and exc.value.reasons
    with pytest.raises(BadRequest):
        cfg.validate_option(db, "no_such_list", "x")
    with pytest.raises(BadRequest):
        cfg.validate_option(db, "evidence_types", "")
    cfg.validate_option(
        db, "evidence_types", "Telepathy", current="Telepathy"
    )  # unchanged old value


def test_inactive_values_are_not_offered_but_stay_valid_when_unchanged(fresh_seed, db) -> None:
    item = db.query(OptionItem).filter_by(list_key="regions", value="Americas").one()
    item.active = False
    db.commit()
    cfg.invalidate()
    assert "Americas" not in cfg.option_values(db, "regions")
    assert "Americas" in cfg.option_values(db, "regions", active_only=False)
    with pytest.raises(BadRequest):
        cfg.validate_option(db, "regions", "Americas")
    cfg.validate_option(db, "regions", "Americas", current="Americas")


def test_cache_is_kept_until_invalidate(fresh_seed, db) -> None:
    assert cfg.option_label(db, "regions", "Asia Pacific") == "Asia Pacific"
    db.query(OptionItem).filter_by(list_key="regions", value="Asia Pacific").one().label = "APAC"
    db.commit()
    assert cfg.option_label(db, "regions", "Asia Pacific") == "Asia Pacific"  # cached
    cfg.invalidate()
    assert cfg.option_label(db, "regions", "Asia Pacific") == "APAC"


def test_label_and_portfolio_edits_are_picked_up_after_invalidate(fresh_seed, db) -> None:
    db.get(Portfolio, "GCC").label = "Global Commercial Cards"
    db.get(FlavourRule, "Normal").label = "Standard"
    db.commit()
    cfg.invalidate()
    assert cfg.portfolio_label(db, "GCC") == "Global Commercial Cards"
    assert cfg.project_type_label(db, "Normal") == "Standard"
    assert cfg.project_type_label(db, "Unknown type") == "Unknown type"


def test_inactive_types_and_portfolios(fresh_seed, db) -> None:
    db.get(FlavourRule, "Infrastructure").active = False
    db.get(Portfolio, "Telecoms").active = False
    db.commit()
    cfg.invalidate()
    assert "Infrastructure" not in [p.code for p in cfg.project_types(db)]
    assert "Infrastructure" in [p.code for p in cfg.project_types(db, active_only=False)]
    assert cfg.project_type(db, "Infrastructure") is not None  # still resolvable
    assert "Telecoms" not in [p.name for p in cfg.portfolios(db)]


def test_thresholds_merge_over_defaults(fresh_seed, db) -> None:
    db.merge(AppSetting(key="cfg.thresholds", value={"rag": {"red_lens_below": 40}}))
    db.commit()
    cfg.invalidate()
    t = cfg.thresholds(db)
    assert t["rag"]["red_lens_below"] == 40 and t["rag"]["red_critical_gaps"] == 2
    assert cfg.rag_thresholds(db).red_lens_below == 40
    assert "min_lens_readiness < 40" in cfg.rag_rule_text(db)["red"]
    t["rag"]["red_lens_below"] = 1  # a copy: callers cannot corrupt the cache
    assert cfg.thresholds(db)["rag"]["red_lens_below"] == 40


def test_labels_gates_lenses(db) -> None:
    assert cfg.label(db, "rag.Grey") == "Not started"
    assert cfg.label(db, "unknown.key", "fallback") == "fallback"
    assert cfg.label(db, "unknown.key") == "unknown.key"
    assert cfg.gate_label(db, "SG4_ATD").startswith("SG4")
    assert cfg.gate_short(db, "SG2") == "SG0–SG2"
    assert cfg.gate_short(db, "NOPE") == "NOPE"
    assert set(cfg.lenses(db)) == {"Business", "Technical", "Compliance"}
    assert cfg.lenses(db)["Compliance"]["signoff_role"] == "IRM"


def test_roles(db) -> None:
    assert cfg.role_label(db, "OR_FOCAL") == "OR focal (S&T)"
    assert cfg.role_short_label(db, "OR_FOCAL") == "OR focal"
    assert cfg.role(db, "NOPE") is None and cfg.role_label(db, "NOPE") == "NOPE"
    assert all(r.can_approve for r in cfg.roles(db))


def test_intake_field_helpers(db) -> None:
    f = cfg.intake_field(db, "audience")
    assert cfg.field_required(f, "Agentic AI") and not cfg.field_required(f, "Normal")
    assert cfg.field_applies(f, "Normal", "GCC")
    assert [x.key for x in cfg.intake_fields(db, form="ai_profile")] == []


def test_template_returns_row_else_code_default(fresh_seed, db) -> None:
    saved = cfg.template(db, "chaser")
    assert saved is not None and not saved.is_default and saved.enabled
    db.query(MessageTemplate).filter_by(key="chaser").delete()
    db.commit()
    cfg.invalidate()
    fallback = cfg.template(db, "chaser")
    assert fallback is not None and fallback.is_default
    assert (fallback.subject, fallback.body) == (saved.subject, saved.body)  # code default == seed
    assert cfg.template(db, "no_such_template") is None
    assert set(cfg.template_keys()) == set(cfg_defaults.DEFAULT_TEMPLATES)


def test_render_escapes_values_but_not_html_placeholders() -> None:
    tpl = cfg.TemplateCfg(
        key="x",
        name="x",
        subject="Hi {{recipient_name}}",
        body="<p>{{recipient_name}}</p>{{item_list}}{{unknown}}",
        enabled=True,
        placeholders=({"name": "item_list", "description": "", "html": True},),
    )
    out = cfg.render_template(tpl, {"recipient_name": "<b>Asha & co</b>", "item_list": "<ul></ul>"})
    assert out["body_html"] == "<p>&lt;b&gt;Asha &amp; co&lt;/b&gt;</p><ul></ul>"
    assert out["subject"] == "Hi <b>Asha & co</b>"  # the subject is plain text


def test_defaults_work_without_any_config_rows(fresh_seed, db) -> None:
    """An empty configuration (before seeding / a section never saved) still answers with the defaults."""
    for model in (OptionItem, OptionList):
        db.query(model).delete()
    db.query(FlavourRule).delete()
    db.commit()
    cfg.invalidate()
    assert cfg.option_values(db, "severities") == ["Critical", "Major", "Minor"]
    assert [p.code for p in cfg.project_types(db)] == [
        "Normal",
        "Infrastructure",
        "Agentic AI",
        "Combined",
    ]
    assert cfg.critical_severity(db) == "Critical"
    cfg.validate_option(db, "severities", "Major")


# --- legacy message text == default template (design 8) ---------------------------------------------


def _legacy_vs_template(db, kind: str, key: str, ctx: dict, values: dict) -> None:
    from app.services.mock.ai_messages import draft_message

    legacy = draft_message(kind, ctx)
    tpl = cfg.template(db, key)
    rendered = cfg.render_template(tpl, values)
    assert rendered["subject"] == legacy["subject"]
    assert rendered["body_html"] == legacy["body_html"]


SIGN = "<p>Thank you,<br>Orion, on behalf of Asha Menon</p>"
BASE = {
    "recipient_name": "Tom",
    "transition_name": "Mobility Knowledge Agent",
    "or_focal_name": "Asha Menon",
    "greeting": "Hi Tom,",
    "sign_off": SIGN,
    "deep_link": "http://localhost:5173/transitions/TR-0001/gates",
}
CTX = {
    "transition_name": "Mobility Knowledge Agent",
    "transition_id": "TR-0001",
    "recipient_name": "Tom",
    "or_focal_name": "Asha Menon",
}


def test_default_leadership_update_equals_legacy(db) -> None:
    ctx = {**CTX, "scope": "Q4 portfolio", "text": "Line one.\nLine two.\n\nSecond paragraph."}
    values = {
        **BASE,
        "scope": "Q4 portfolio",
        "paragraphs": "<p>Line one.<br>Line two.</p><p>Second paragraph.</p>",
    }
    _legacy_vs_template(db, "leadership update", "leadership_update", ctx, values)


def test_default_input_request_equals_legacy(db) -> None:
    ctx = {**CTX, "items": [{"id": "L1", "title": "Hosting cost"}]}
    item_list = (
        '<ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=L1">L1</a> '
        "Hosting cost</li></ul>"
    )
    values = {**BASE, "input_count_text": "1 input", "item_list": item_list}
    _legacy_vs_template(db, "input request", "input_request", ctx, values)


def test_default_approval_request_equals_legacy(db) -> None:
    ctx = {
        **CTX,
        "gate_short": "AtD",
        "verdict": "Ready",
        "approver_role": "OLM",
        "summary": "All good.",
        "deep_link": "http://x/y",
    }
    values = {
        **BASE,
        "gate_short": "AtD",
        "deep_link": "http://x/y",
        "verdict_suffix": " (readiness: Ready)",
        "summary_html": "<p>All good.</p>",
        "approver_line": "<p>First approver: OLM.</p>",
    }
    _legacy_vs_template(db, "approval request", "approval_request", ctx, values)


def test_default_chaser_and_reminder_equal_legacy(db) -> None:
    items = [{"id": "S3-019", "title": "DPIA", "due_gate_short": "AtD", "owner_name": "Tom"}]
    item_list = (
        '<ul><li><a href="http://localhost:5173/transitions/TR-0001/assessment?item=S3-019">S3-019</a> '
        "DPIA (due at AtD, Tom)</li></ul>"
    )
    ctx = {**CTX, "gate_short": "AtD", "days": 21, "items": items, "deep_link": "http://x/y"}
    chaser = {
        **BASE,
        "deep_link": "http://x/y",
        "item_title": "DPIA",
        "when_suffix": " (AtD in 21 days)",
        "when_or_next_gate": "AtD in 21 days",
        "item_phrase": "this item",
        "item_list": item_list,
    }
    _legacy_vs_template(db, "chaser", "chaser", ctx, chaser)
    reminder = {
        **BASE,
        "open_item_count_text": "1 open item",
        "item_count_text": "1 item",
        "when_suffix": " (AtD in 21 days)",
        "is_are": "is",
        "item_list": item_list,
    }
    _legacy_vs_template(db, "reminder", "reminder", ctx, reminder)
