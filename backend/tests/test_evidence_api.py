"""Evidence API (FR-033, spec 8.7 d, 10.5): upload / link / e-mail sign-off, review, download."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditEvent

API = "/api/v1"
T = "TR-0001"
TECH_ITEM = "S3-019"  # Technical lens (OR focal reviews)
COMP_ITEM = "S45-014"  # Compliance lens (IRM reviews)


def _upload(client, headers, user="U10", **form):
    data = {"title": "Pen test report", "type": "Document", "item_id": TECH_ITEM, **form}
    files = {"file": ("pen test (final).pdf", b"%PDF-1.4 test content", "application/pdf")}
    return client.post(
        f"{API}/transitions/{T}/evidence", data=data, files=files, headers=headers(user)
    )


def _review(client, headers, evidence_id, body, user="U01"):
    return client.post(f"{API}/evidence/{evidence_id}/review", json=body, headers=headers(user))


def _audit(db, evidence_id):
    db.expire_all()
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity == "Evidence", AuditEvent.entity_id == evidence_id)
            .order_by(AuditEvent.id)
        ).all()
    )


def test_list_seeded_evidence_newest_first(client, headers):
    res = client.get(f"{API}/transitions/{T}/evidence", headers=headers())
    assert res.status_code == 200
    rows = res.json()
    assert rows
    stamps = [(r["created_at"], r["id"]) for r in rows]
    assert stamps == sorted(stamps, reverse=True)
    assert client.get(f"{API}/transitions/TR-9999/evidence", headers=headers()).status_code == 404


def test_requires_header(client):
    assert client.get(f"{API}/transitions/{T}/evidence").status_code == 401


def test_upload_download_round_trip(client, headers, db, fresh_seed):
    res = _upload(client, headers)
    assert res.status_code == 201, res.text
    ev = res.json()
    assert ev["id"].startswith("EVD-") and ev["status"] == "Submitted"
    assert ev["has_file"] is True and ev["type"] == "Document"
    assert ev["url"].startswith("https://sharepoint.example/") and f"/{T}/" in ev["url"]
    assert ev["item_id"] == TECH_ITEM and ev["item_title"]
    assert ev["submitted_by"]["id"] == "U10"
    dl = client.get(f"{API}/evidence/{ev['id']}/download", headers=headers())
    assert dl.status_code == 200
    assert dl.content == b"%PDF-1.4 test content"
    assert dl.headers["content-type"].startswith("application/pdf")
    disp = dl.headers["content-disposition"]
    assert (
        disp.startswith("attachment;") and ".pdf" in disp and "/" not in disp and ".." not in disp
    )
    # audited as Human
    events = _audit(db, ev["id"])
    assert [e.action for e in events] == ["created"]
    assert events[0].actor_type == "Human" and events[0].actor_user_id == "U10"
    assert events[0].transition_id == T


def test_filters(client, headers, fresh_seed):
    ev = _upload(client, headers).json()
    link = client.post(
        f"{API}/transitions/{T}/evidence",
        data={"title": "Runbook", "type": "Link", "url": "https://example.com/runbook"},
        headers=headers("U11"),
    )
    assert link.status_code == 201
    base = f"{API}/transitions/{T}/evidence"
    by_item = client.get(base, params={"item": TECH_ITEM}, headers=headers()).json()
    assert ev["id"] in [r["id"] for r in by_item]
    assert all(r["item_id"] == TECH_ITEM for r in by_item)
    by_type = client.get(base, params={"type": "Link"}, headers=headers()).json()
    assert [r["id"] for r in by_type] == [link.json()["id"]]
    by_status = client.get(base, params={"status": "Submitted"}, headers=headers()).json()
    assert ev["id"] in [r["id"] for r in by_status]
    assert all(r["status"] == "Submitted" for r in by_status)


def test_link_and_email_signoff(client, headers, fresh_seed):
    link = client.post(
        f"{API}/transitions/{T}/evidence",
        data={"title": "Runbook", "type": "Link", "url": "https://example.com/runbook"},
        headers=headers("U01"),
    )
    assert link.status_code == 201
    body = link.json()
    assert body["url"] == "https://example.com/runbook" and body["has_file"] is False
    assert body["item_id"] is None
    assert client.get(f"{API}/evidence/{body['id']}/download", headers=headers()).status_code == 404

    mail = client.post(
        f"{API}/transitions/{T}/evidence",
        data={
            "title": "OLM sign-off",
            "type": "Email sign-off",
            "text": "Approved by Sam on 12 Nov.",
            "item_id": TECH_ITEM,
        },
        headers=headers("U12"),
    )
    assert mail.status_code == 201
    assert mail.json()["text"] == "Approved by Sam on 12 Nov." and mail.json()["has_file"] is False


def test_validation(client, headers, fresh_seed):
    base = f"{API}/transitions/{T}/evidence"
    h = headers("U10")
    assert client.post(base, data={"title": "x", "type": "Link"}, headers=h).status_code == 422
    bad_url = {"title": "x", "type": "Link", "url": "javascript:alert(1)"}
    assert client.post(base, data=bad_url, headers=h).status_code == 422
    assert (
        client.post(base, data={"title": "x", "type": "Email sign-off"}, headers=h).status_code
        == 422
    )
    assert client.post(base, data={"title": "x", "type": "Document"}, headers=h).status_code == 422
    gen = {"title": "x", "type": "Generated", "url": "https://example.com"}
    assert client.post(base, data=gen, headers=h).status_code == 422
    exe = client.post(
        base,
        data={"title": "x", "type": "Document"},
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        headers=h,
    )
    assert exe.status_code == 422
    unknown_item = {"title": "x", "type": "Link", "url": "https://e.com", "item_id": "NOPE-1"}
    assert client.post(base, data=unknown_item, headers=h).status_code == 404
    assert (
        client.post(
            f"{API}/transitions/TR-9999/evidence",
            data={"title": "x", "type": "Link", "url": "https://e.com"},
            headers=h,
        ).status_code
        == 404
    )


def test_upload_permission(client, headers, fresh_seed):
    res = _upload(client, headers, user="U13")  # Planner cannot upload evidence
    assert res.status_code == 403
    assert res.json()["detail"] == "Your role cannot upload or link evidence"


def test_review_permissions_by_lens(client, headers, db, fresh_seed):
    tech = _upload(client, headers).json()
    comp = _upload(client, headers, item_id=COMP_ITEM, title="Red-team report").json()
    # can_review flags per viewer
    rows = {
        r["id"]: r
        for r in client.get(f"{API}/transitions/{T}/evidence", headers=headers("U01")).json()
    }
    assert (
        rows[tech["id"]]["can_review"] is True and rows[tech["id"]]["review_denied_reason"] is None
    )
    assert rows[comp["id"]]["can_review"] is False
    assert rows[comp["id"]]["review_denied_reason"] == (
        "Only IRM can accept or reject Compliance evidence"
    )
    irm_rows = {
        r["id"]: r
        for r in client.get(f"{API}/transitions/{T}/evidence", headers=headers("U14")).json()
    }
    assert irm_rows[comp["id"]]["can_review"] is True
    assert irm_rows[tech["id"]]["can_review"] is False

    # OR focal: Technical yes, Compliance no
    res = _review(client, headers, comp["id"], {"decision": "Accept"}, user="U01")
    assert res.status_code == 403
    assert res.json()["detail"] == "Only IRM can accept or reject Compliance evidence"
    res = _review(client, headers, tech["id"], {"decision": "Accept"}, user="U10")  # PM
    assert res.status_code == 403
    assert (
        res.json()["detail"] == "Only the OR focal can accept or reject Business/Technical evidence"
    )
    res = _review(client, headers, tech["id"], {"decision": "Accept", "note": "ok"}, user="U01")
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "Accepted" and out["reviewed_by"]["id"] == "U01"
    assert out["reviewed_at"] and out["review_note"] == "ok"
    # IRM: Compliance yes, Technical no
    assert (
        _review(
            client, headers, tech["id"], {"decision": "Reject", "note": "x"}, user="U14"
        ).status_code
        == 403
    )
    res = _review(client, headers, comp["id"], {"decision": "Accept"}, user="U14")
    assert res.status_code == 200 and res.json()["status"] == "Accepted"
    # re-review is allowed
    res = _review(client, headers, tech["id"], {"decision": "Reject", "note": "Wrong version"})
    assert res.status_code == 200 and res.json()["status"] == "Rejected"

    events = _audit(db, tech["id"])
    assert [e.action for e in events] == ["created", "accepted", "rejected"]
    assert events[1].before["status"] == "Submitted" and events[1].after["status"] == "Accepted"
    assert events[2].before["status"] == "Accepted" and events[2].after["status"] == "Rejected"
    assert all(e.actor_type == "Human" for e in events)


def test_reject_needs_note(client, headers, fresh_seed):
    ev = _upload(client, headers).json()
    res = _review(client, headers, ev["id"], {"decision": "Reject", "note": "  "})
    assert res.status_code == 422
    assert "note" in res.json()["detail"].lower()
    assert _review(client, headers, "EVD-999", {"decision": "Accept"}).status_code == 404


def test_evidence_without_item_is_business_technical(client, headers, fresh_seed):
    link = client.post(
        f"{API}/transitions/{T}/evidence",
        data={"title": "General", "type": "Link", "url": "https://example.com/g"},
        headers=headers("U10"),
    ).json()
    assert (
        _review(client, headers, link["id"], {"decision": "Accept"}, user="U14").status_code == 403
    )
    assert (
        _review(client, headers, link["id"], {"decision": "Accept"}, user="U01").status_code == 200
    )


def test_download_unknown_404(client, headers):
    assert client.get(f"{API}/evidence/EVD-999/download", headers=headers()).status_code == 404


def test_upload_too_large_rejected(client, headers, fresh_seed, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    big = b"x" * (1024 * 1024 + 10)
    res = client.post(
        f"{API}/transitions/{T}/evidence",
        data={"title": "Big", "type": "Document"},
        files={"file": ("big.txt", big, "text/plain")},
        headers=headers("U10"),
    )
    assert res.status_code in (413, 422)
