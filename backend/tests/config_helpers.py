"""Helpers for the CR-01 configuration tests: set up configuration the way an Admin does.

Each ``add_*`` function calls the Admin API as U16. While a write endpoint still answers 501 (not
built yet) the same rows are written straight into the database, so the tests that read the
configuration keep running; the function returns True when the API was used.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain import cfg
from app.models import Checklist, FlavourRule, IntakeField, PlaybookItem, Portfolio

API = "/api/v1"
ADMIN = "U16"


def _api(client, headers, method: str, path: str, body: dict[str, Any]):
    return client.request(method, f"{API}{path}", json=body, headers=headers(ADMIN))


def _written(res) -> bool:
    """True when the endpoint did the write; False when it is not implemented yet (501)."""
    if res.status_code == 501:
        return False
    assert res.status_code in (200, 201), res.text
    return True


def _commit(db: Session, *rows: Any) -> None:
    for row in rows:
        db.add(row)
    db.commit()
    cfg.invalidate()


def add_checklist(client, headers, db: Session, code: str, label: str, **extra: Any) -> bool:
    """A new library checklist (e.g. SECURITY_PLAYBOOK)."""
    res = _api(
        client, headers, "POST", "/admin/checklists", {"code": code, "label": label, **extra}
    )
    if _written(res):
        return True
    _commit(
        db,
        Checklist(
            code=code,
            label=label,
            kind="library",
            tier_filtered=bool(extra.get("tier_filtered", False)),
            sort_order=50,
        ),
    )
    return False


def add_item(
    client,
    headers,
    db: Session,
    item_id: str,
    source: str,
    title: str,
    *,
    gate: str = "SG2",
    lens: str = "Business",
    **extra: Any,
) -> bool:
    """A new library item in any checklist (a golden-set item also needs ``portfolio``)."""
    body = {"id": item_id, "source": source, "title": title, "gate": gate, "lens": lens, **extra}
    res = _api(client, headers, "POST", "/admin/playbook-items", body)
    if _written(res):
        return True
    _commit(
        db,
        PlaybookItem(
            id=item_id,
            source=source,
            portfolio=extra.get("portfolio"),
            title=title,
            gate=gate,
            lens=lens,
            applicable_tiers=extra.get("applicable_tiers", []),
            mandatory=extra.get("mandatory", True),
            mandatory_rule=extra.get("mandatory_rule", "always"),
            applies_to_project_types=[],
            sort_order=9000,
        ),
    )
    return False


def add_project_type(client, headers, db: Session, code: str, **extra: Any) -> bool:
    """A new project type; ``extra`` holds label, checklists, the three switches, required fields."""
    res = _api(client, headers, "POST", "/admin/project-types", {"code": code, **extra})
    if _written(res):
        return True
    _commit(
        db,
        FlavourRule(
            project_type=code,
            label=extra.get("label", code),
            checklists=extra.get("checklists", ["FRAMEWORK"]),
            requires_tiering=extra.get("requires_tiering", False),
            has_ai_profile=extra.get("has_ai_profile", False),
            has_eval_metrics=extra.get("has_eval_metrics", False),
            required_intake_fields=extra.get("required_intake_fields", []),
            sort_order=50,
        ),
    )
    return False


def add_portfolio(client, headers, db: Session, name: str, code: str, **extra: Any) -> bool:
    """A new portfolio; ``extra`` holds label, focus_areas, requires_sites."""
    res = _api(client, headers, "POST", "/admin/portfolios", {"name": name, "code": code, **extra})
    if _written(res):
        return True
    _commit(
        db,
        Portfolio(
            name=name,
            code=code,
            label=extra.get("label", name),
            focus_areas=extra.get("focus_areas", []),
            requires_sites=extra.get("requires_sites", False),
            sort_order=50,
        ),
    )
    return False


def add_golden_set(client, headers, db: Session, portfolio: str, items: list[dict[str, Any]]):
    """Replace the golden set of ``portfolio`` (the golden-set editor endpoint already exists)."""
    res = client.put(
        f"{API}/admin/portfolios/{portfolio}/golden-set",
        json={"items": items},
        headers=headers(ADMIN),
    )
    assert res.status_code == 200, res.text
    cfg.invalidate()
    return res.json()


def add_custom_field(
    client, headers, db: Session, key: str, label: str, field_type: str = "text", **extra: Any
) -> bool:
    """A custom ("Additional details") field of the intake form."""
    body = {"key": key, "label": label, "type": field_type, **extra}
    res = _api(client, headers, "POST", "/admin/intake-fields", body)
    if _written(res):
        return True
    _commit(
        db,
        IntakeField(
            key=key,
            label=label,
            builtin=False,
            structural=False,
            type=field_type,
            option_list=extra.get("option_list"),
            required_mode=extra.get("required_mode", "never"),
            required_for_project_types=extra.get("required_for_project_types", []),
            applies_to_project_types=extra.get("applies_to_project_types", []),
            applies_to_portfolios=extra.get("applies_to_portfolios", []),
            section="Additional details",
            sort_order=500,
            show_on_overview=extra.get("show_on_overview", False),
            filterable=extra.get("filterable", False),
            min=extra.get("min"),
            max=extra.get("max"),
            max_length=extra.get("max_length"),
        ),
    )
    return False


def new_transition(client, headers, user: str = "U01", **overrides: Any):
    """POST /transitions with a valid default body; returns the response."""
    body = {
        "name": "Config test",
        "project_type": "Normal",
        "portfolio": "GCC",
        "region": "Global",
        "or_focal_user_id": "U01",
        "pm_user_id": "U10",
        "architect_user_id": "U11",
        "olm_user_id": "U12",
        "irm_user_id": "U14",
    }
    body.update(overrides)
    return client.post(f"{API}/transitions", json=body, headers=headers(user))
