"""Support model generator API (FR-040, AC-10). Seed date 2026-11-16."""

from __future__ import annotations

import io

from sqlalchemy import select

from app.models import AuditEvent, OrionDraft, TransitionItem

API = "/api/v1"
TXT = [("walk.txt", b"SFTP and SSO", "text/plain")]


def _inputs(client, headers, tid="TR-0001", user="U01", url=None, files=None):
    data = {"confluence_url": url} if url is not None else {}
    multipart = [("files", (n, io.BytesIO(c), t)) for n, c, t in (files or [])]
    return client.post(
        f"{API}/transitions/{tid}/support-model/inputs",
        data=data,
        files=multipart or None,
        headers=headers(user),
    )


def _generate(client, headers, tid="TR-0001", user="U01", url=None):
    res = _inputs(client, headers, tid, user, url=url, files=TXT)
    assert res.status_code == 200, res.text
    res = client.post(f"{API}/transitions/{tid}/support-model/generate", headers=headers(user))
    assert res.status_code == 200, res.text
    return res.json()


def _put(client, headers, sid, landscape, user="U01"):
    return client.put(
        f"{API}/support-models/{sid}", json={"landscape": landscape}, headers=headers(user)
    )


def test_not_started_view(client, headers, fresh_seed):
    body = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U01")).json()
    assert body["id"] is None and body["status"] == "Not started" and body["version"] == 0
    assert body["landscape"] is None and body["can_edit"] is True
    ids = {i["item_id"] for i in body["linked_items"]}
    assert {f"FW-0{n}" for n in range(27, 36)} <= ids
    missing = client.get(f"{API}/transitions/TR-9999/support-model", headers=headers())
    assert missing.status_code == 404


def test_voc_sample_by_transition_name(client, headers, fresh_seed):
    out = _generate(client, headers, "TR-0014")
    landscape = out["support_model"]["landscape"]
    assert landscape["central_app"] == "Medallia VOC"
    assert landscape["vendor"] == "Medallia" and landscape["supplier"] == "KPMG"
    names = {c["name"] for c in landscape["components"]}
    assert {"GCC Integration", "MDH", "SSO", "SPN", "Groups"} <= names
    assert [c["id"] for c in landscape["components"]][:2] == ["c1", "c2"]
    assert "walk.txt" in {s["ref"] for s in landscape["sources"]}
    assert [s["label"] for s in out["steps"]] == [
        "Reading transcript",
        "Reading diagrams and documents",
        "Drafting landscape and support flows",
    ]


def test_voc_sample_by_confluence_url(client, headers, fresh_seed):
    out = _generate(client, headers, "TR-0001", url="https://confluence.example/wiki/VOC-design")
    assert out["support_model"]["landscape"]["central_app"] == "Medallia VOC"
    assert out["support_model"]["inputs"]["confluence"]["title"]


def test_generic_landscape_for_flagship(client, headers, fresh_seed):
    landscape = _generate(client, headers)["support_model"]["landscape"]
    assert landscape["central_app"] == "Mobility Knowledge Agent"
    comps = landscape["components"]
    assert 6 <= len(comps) <= 8
    assert {"Entra ID SSO", "ServiceNow", "Monitoring tool"} <= {c["name"] for c in comps}
    assert landscape["support_tiers"]["L1"].startswith("L1 Service Desk")
    assert len(landscape["open_questions"]) == 3
    assert any(s["ref"] == "walk.txt" for s in landscape["sources"])
    assert [c["id"] for c in comps] == [f"c{i}" for i in range(1, len(comps) + 1)]


def test_generate_without_inputs_conflicts(client, headers, fresh_seed):
    res = client.post(f"{API}/transitions/TR-0001/support-model/generate", headers=headers("U01"))
    assert res.status_code == 409


def test_input_validation(client, headers, fresh_seed):
    bad = _inputs(client, headers, files=[("x.exe", b"abc", "application/octet-stream")])
    assert bad.status_code == 422
    empty = _inputs(client, headers, files=[("x.txt", b"", "text/plain")])
    assert empty.status_code == 422
    assert _inputs(client, headers, url="ftp://nope").status_code == 422


def test_same_filename_replaces_and_blank_url_clears(client, headers, fresh_seed):
    _inputs(
        client,
        headers,
        url="https://confluence.example/wiki/x",
        files=[("a.txt", b"1", "text/plain")],
    )
    body = _inputs(client, headers, url="", files=[("a.txt", b"2", "text/plain")]).json()
    assert [f["filename"] for f in body["inputs"]["files"]] == ["a.txt"]
    assert body["inputs"]["confluence_url"] is None and body["inputs"]["confluence"] is None


def test_confluence_fetch(client, headers):
    url = "https://x.example/voc"
    res = client.post(
        f"{API}/integrations/confluence/fetch", json={"url": url}, headers=headers("U10")
    )
    assert res.status_code == 200 and res.json()["title"]
    blank = client.post(
        f"{API}/integrations/confluence/fetch", json={"url": " "}, headers=headers()
    )
    assert blank.status_code == 422
    other = client.post(
        f"{API}/integrations/confluence/fetch", json={"url": "mailto:a"}, headers=headers()
    )
    assert other.status_code == 422


def test_put_edits_persist_and_validate(client, headers, fresh_seed):
    model = _generate(client, headers)["support_model"]
    sid, landscape = model["id"], model["landscape"]
    landscape["components"][0]["name"] = "Renamed node"
    landscape["open_questions"][0] = "Answered: yes"
    res = _put(client, headers, sid, landscape)
    assert res.status_code == 200, res.text
    again = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U11")).json()
    assert again["landscape"]["components"][0]["name"] == "Renamed node"
    assert again["landscape"]["open_questions"][0] == "Answered: yes"

    first = landscape["components"][0]
    dup = {**landscape, "components": [*landscape["components"], dict(first)]}
    assert _put(client, headers, sid, dup).status_code == 422
    for patch in ({"relation": "child_of:Nope"}, {"relation": "sideways"}, {"target": "Nope"}):
        bad = {**landscape, "components": [{**first, **patch}]}
        assert _put(client, headers, sid, bad).status_code == 422
    assert _put(client, headers, 9999, landscape).status_code == 404


def test_permissions_403(client, headers, fresh_seed):
    for user in ("U10", "U12", "U14", "U15"):
        assert _inputs(client, headers, user=user, files=TXT).status_code == 403
        gen = client.post(
            f"{API}/transitions/TR-0001/support-model/generate", headers=headers(user)
        )
        assert gen.status_code == 403
        assert _put(client, headers, 1, {"central_app": "x"}, user).status_code == 403
        assert (
            client.post(
                f"{API}/support-models/1/send-for-review", headers=headers(user)
            ).status_code
            == 403
        )
        assert client.post(f"{API}/support-models/1/pptx", headers=headers(user)).status_code == 403
        draft = client.post(f"{API}/support-models/1/questions/0/draft", headers=headers(user))
        assert draft.status_code == 403
    view = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers("U10")).json()
    assert view["can_edit"] is False and view["edit_denied_reason"]


def test_review_chain_agrees_and_completes_items(client, headers, db, fresh_seed):
    model = _generate(client, headers)["support_model"]
    sid = model["id"]
    sent = client.post(f"{API}/support-models/{sid}/send-for-review", headers=headers("U01"))
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "In review" and body["can_edit"] is False
    assert [s["role"] for s in body["approval"]["steps"]] == ["ARCHITECT", "OLM"]
    rid = body["approval"]["request_id"]
    assert _put(client, headers, sid, model["landscape"]).status_code == 409
    assert (
        client.post(f"{API}/support-models/{sid}/send-for-review", headers=headers()).status_code
        == 409
    )
    again = client.post(f"{API}/transitions/TR-0001/support-model/generate", headers=headers())
    assert again.status_code == 409

    def approve(step, user):
        url = f"{API}/approvals/{rid}/steps/{step}/approve"
        return client.post(url, json={}, headers=headers(user)).status_code

    assert approve(1, "U12") == 403
    assert approve(1, "U11") == 200
    mid = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers()).json()
    assert mid["status"] == "In review"
    assert approve(2, "U12") == 200

    done = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers()).json()
    assert done["status"] == "Agreed" and done["approval"]["status"] == "Approved"
    fw = {i["item_id"]: i["status"] for i in done["linked_items"]}
    assert all(fw[f"FW-0{n}"] == "Complete" for n in range(27, 36))
    assert all(s in ("Complete", "Compliant", "N/A", "Not applicable") for s in fw.values())

    db.expire_all()
    rows = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "TransitionItem",
            AuditEvent.actor_type == "Workflow rule",
            AuditEvent.note == "Support model agreed",
        )
    ).all()
    assert len(rows) >= 9
    items = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == "TR-0001",
            TransitionItem.linked_module == "SUPPORT_MODEL",
        )
    ).all()
    assert any(i.last_updated_source == "Workflow rule" for i in items)

    assert _put(client, headers, sid, model["landscape"]).status_code == 409
    regen = client.post(f"{API}/transitions/TR-0001/support-model/generate", headers=headers("U01"))
    sm = regen.json()["support_model"]
    assert sm["version"] == 2 and sm["status"] == "Draft" and sm["id"] != sid


def test_rejection_returns_to_draft(client, headers, fresh_seed):
    model = _generate(client, headers)["support_model"]
    sent = client.post(f"{API}/support-models/{model['id']}/send-for-review", headers=headers())
    rid = sent.json()["approval"]["request_id"]
    res = client.post(
        f"{API}/approvals/{rid}/steps/1/reject",
        json={"comment": "Missing L3"},
        headers=headers("U11"),
    )
    assert res.status_code == 200, res.text
    view = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers()).json()
    assert view["status"] == "Draft" and view["can_edit"] is True
    again = client.post(f"{API}/support-models/{model['id']}/send-for-review", headers=headers())
    assert again.status_code == 200 and again.json()["approval"]["request_id"] != rid


def test_send_without_landscape_conflicts(client, headers, fresh_seed):
    sid = _inputs(client, headers, files=[("a.txt", b"x", "text/plain")]).json()["id"]
    assert (
        client.post(f"{API}/support-models/{sid}/send-for-review", headers=headers()).status_code
        == 409
    )
    assert client.post(f"{API}/support-models/{sid}/pptx", headers=headers()).status_code == 409


def test_pptx_creates_evidence_and_versions(client, headers, fresh_seed):
    model = _generate(client, headers)["support_model"]
    first = client.post(f"{API}/support-models/{model['id']}/pptx", headers=headers("U11"))
    assert first.status_code == 200, first.text
    out = first.json()
    assert out["version"] == 1 and out["filename"].endswith("-v1.pptx")
    assert out["download_path"] == f"/evidence/{out['evidence_id']}/download"
    dl = client.get(API + out["download_path"], headers=headers("U01"))
    assert dl.status_code == 200 and dl.content[:2] == b"PK"
    second = client.post(f"{API}/support-models/{model['id']}/pptx", headers=headers("U01")).json()
    assert second["version"] == 2 and second["evidence_id"] != out["evidence_id"]
    assert second["filename"].endswith("-v2.pptx")

    ev = client.get(
        f"{API}/transitions/TR-0001/evidence", params={"item": "FW-035"}, headers=headers()
    ).json()
    generated = [e for e in ev if e["type"] == "Generated"]
    assert len(generated) == 2 and all(e["status"] == "Submitted" for e in generated)
    view = client.get(f"{API}/transitions/TR-0001/support-model", headers=headers()).json()
    assert view["pptx"]["version"] == 2 and view["pptx"]["evidence_id"] == second["evidence_id"]


def test_question_draft(client, headers, db, fresh_seed):
    model = _generate(client, headers)["support_model"]
    url = f"{API}/support-models/{model['id']}/questions/1/draft"
    res = client.post(url, headers=headers("U01"))
    assert res.status_code == 200, res.text
    draft = db.get(OrionDraft, res.json()["draft_id"])
    assert draft.kind == "Input request" and draft.status == "Draft"
    assert draft.created_source == "Orion agent" and len(draft.to) == 1
    assert model["landscape"]["open_questions"][1].split("?")[0][:20] in draft.body_html
    bad_index = client.post(
        f"{API}/support-models/{model['id']}/questions/9/draft", headers=headers()
    )
    assert bad_index.status_code == 404
    assert (
        client.post(f"{API}/support-models/9999/questions/0/draft", headers=headers()).status_code
        == 404
    )


def test_list_models_filter(client, headers, fresh_seed):
    _generate(client, headers, "TR-0014")
    _generate(client, headers, "TR-0001")
    rows = client.get(f"{API}/support-models", headers=headers("U15")).json()
    assert {r["transition_id"] for r in rows} == {"TR-0014", "TR-0001"}
    only = client.get(f"{API}/support-models", params={"q": "medallia"}, headers=headers()).json()
    assert [r["transition_id"] for r in only] == ["TR-0014"]
    assert client.get(f"{API}/support-models", params={"q": "zzz"}, headers=headers()).json() == []


def test_voc_match_is_whole_word():
    from app.services.mock.support_model_generator import _matches

    sample = {"match": {"transition_name_contains": ["VOC"], "confluence_url_contains": ["voc"]}}
    assert _matches(sample, "Medallia VOC rollout", "")
    assert _matches(sample, "x", "https://x/wiki/voc-home")
    assert not _matches(sample, "Advocacy portal", "https://x/wiki/advocacy")
    assert not _matches(sample, "Vocabulary trainer", "")


def test_landscape_limits_duplicates_and_cycles(client, headers, fresh_seed):
    model = _generate(client, headers)["support_model"]
    sid, ls = model["id"], model["landscape"]
    many = [
        {"id": f"c{i}", "name": f"N{i}", "type": "Team", "relation": "bidirectional"}
        for i in range(30)
    ]
    assert _put(client, headers, sid, {**ls, "components": many}).status_code == 422
    big = {**ls, "open_questions": ["x" * 50_000]}
    assert _put(client, headers, sid, big).status_code == 422
    a = {"id": "c1", "name": "A", "type": "Team", "relation": "child_of:B"}
    b = {"id": "c2", "name": "B", "type": "Team", "relation": "child_of:A"}
    assert _put(client, headers, sid, {**ls, "components": [a, b]}).status_code == 422
    same = {"id": "c2", "name": "A", "type": "Team", "relation": "inbound"}
    assert _put(client, headers, sid, {**ls, "components": [a, same]}).status_code == 422


def test_superseded_model_cannot_export_pptx(client, headers, db, fresh_seed):
    from app.models import SupportModel

    first = _generate(client, headers)["support_model"]
    db.get(SupportModel, first["id"]).status = "Agreed"
    db.commit()
    gen = client.post(f"{API}/transitions/TR-0001/support-model/generate", headers=headers("U01"))
    assert gen.status_code == 200, gen.text
    res = client.post(f"{API}/support-models/{first['id']}/pptx", headers=headers("U01"))
    assert res.status_code == 409, res.text
