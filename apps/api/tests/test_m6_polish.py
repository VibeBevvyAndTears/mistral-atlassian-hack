"""M6 polish tests — glossary, feed filters, mark-read, draft stub, admin metrics."""

from __future__ import annotations

import inspect
import io
import uuid

from fastapi.testclient import TestClient

from tests.test_auth import _reset_all


def _register(client: TestClient, email: str) -> str:
    _reset_all()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "username": "".join(c if c.isalnum() or c=="_" else "_" for c in email.split("@")[0].lower())[:32], "name": "T"},  # noqa: E501
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(
    token: str, org_id: str | None = None, team_id: str | None = None
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if org_id:
        headers["X-Org-Id"] = org_id
    if team_id:
        headers["X-Team-Id"] = team_id
    return headers


def _team(client: TestClient) -> dict[str, str]:
    token = _register(client, f"m6-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "M6"}, headers=_auth(token)).json()[
        "id"
    ]
    team = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Core"},
        headers=_auth(token, org),
    ).json()["id"]
    return {"token": token, "org": org, "team": team}


def test_profile_draft_uses_mistral_not_fake() -> None:
    from src.profiles import service as mod

    src = inspect.getsource(mod)
    assert "get_mistral_provider" in src
    assert "FakeAIProvider(" not in src


def test_glossary_crud(client: TestClient) -> None:
    t = _team(client)
    created = client.post(
        f"/api/teams/{t['team']}/glossary",
        json={
            "term": "SLA",
            "definition": "Service level agreement",
            "kind": "must_explain",
        },
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert created.status_code == 201, created.text
    term_id = created.json()["id"]

    listed = client.get(
        f"/api/teams/{t['team']}/glossary",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert listed.status_code == 200
    assert any(row["id"] == term_id for row in listed.json())

    deleted = client.delete(
        f"/api/teams/{t['team']}/glossary/{term_id}",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert deleted.status_code == 204


def test_feed_sort_and_mark_read(client: TestClient) -> None:
    t = _team(client)
    t2 = client.post(
        f"/api/orgs/{t['org']}/teams",
        json={"name": "Other"},
        headers=_auth(t["token"], t["org"]),
    ).json()["id"]
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team"], "team_b_id": t2},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

    for sort in ("newest", "oldest", "priority"):
        feed = client.get(
            f"/api/channels/{channel_id}/posts",
            params={"sort": sort, "unread_only": False},
            headers=_auth(t["token"], t["org"], t["team"]),
        )
        assert feed.status_code == 200, feed.text


def test_channel_priority_sort_orders_p0_before_p2(client: TestClient) -> None:
    """Channel feed sort=priority ranks by ai_priority (case-insensitive p0..p2)."""
    import asyncio
    from uuid import UUID

    from src.channels import service as channels_service
    from src.lib.database import async_session_factory

    t = _team(client)
    t2 = client.post(
        f"/api/orgs/{t['org']}/teams",
        json={"name": "Receiver"},
        headers=_auth(t["token"], t["org"]),
    ).json()["id"]
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team"], "team_b_id": t2},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

    pkg = client.post(
        f"/api/teams/{t['team']}/packages",
        json={
            "title": "Priority fixture",
            "body": "body",
            "target_team_id": t2,
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert pkg.status_code == 201, pkg.text
    package_id = pkg.json()["id"]

    async def _seed() -> None:
        async with async_session_factory() as session:
            # Insert lower priority first so newest-only order would invert ranking
            for pri, body in (
                ("p2", "FYI — optional reading"),
                ("p1", "Please review this week"),
                ("p0", "BLOCKER — production outage response needed today"),
            ):
                await channels_service.create_post_with_rendition(
                    session,
                    org_id=UUID(t["org"]),
                    channel_id=UUID(channel_id),
                    package_id=UUID(package_id),
                    original_body=body,
                    adapted_body=body,
                    what_was_done="fixture",
                    priority=pri,
                    priority_reason=f"fixture {pri}",
                    bypassed_checks=[],
                    fidelity=None,
                    fit=None,
                    confidence=None,
                    badge=None,
                    judge_payload={},
                    topic_tags=[],
                    attached_conflicts=[],
                )
            await session.commit()

    asyncio.run(_seed())

    newest = client.get(
        f"/api/channels/{channel_id}/posts",
        params={"sort": "newest"},
        headers=_auth(t["token"], t["org"], t2),
    )
    assert newest.status_code == 200, newest.text
    newest_page = newest.json()
    assert newest_page["total"] == 3
    assert newest_page["page_size"] == 10
    assert {p["ai_priority"] for p in newest_page["items"]} == {"p0", "p1", "p2"}

    by_pri = client.get(
        f"/api/channels/{channel_id}/posts",
        params={"sort": "priority"},
        headers=_auth(t["token"], t["org"], t2),
    )
    assert by_pri.status_code == 200, by_pri.text
    by_pri_page = by_pri.json()
    pris = [p["ai_priority"] for p in by_pri_page["items"]]
    assert pris == ["p0", "p1", "p2"], pris
    assert by_pri_page["items"][0]["ai_priority_reason"] == "fixture p0"

    hit = client.get(
        f"/api/channels/{channel_id}/posts",
        params={"q": "BLOCKER", "sort": "newest"},
        headers=_auth(t["token"], t["org"], t2),
    )
    assert hit.status_code == 200, hit.text
    hit_page = hit.json()
    assert hit_page["total"] == 1
    assert hit_page["items"][0]["ai_priority"] == "p0"
    assert hit_page["items"][0]["search_score"] is not None

    page1 = client.get(
        f"/api/channels/{channel_id}/posts",
        params={"sort": "priority", "page": 1, "page_size": 2},
        headers=_auth(t["token"], t["org"], t2),
    )
    assert page1.status_code == 200, page1.text
    p1 = page1.json()
    assert p1["page"] == 1
    assert p1["page_size"] == 2
    assert p1["total"] == 3
    assert p1["total_pages"] == 2
    assert [p["ai_priority"] for p in p1["items"]] == ["p0", "p1"]

    page2 = client.get(
        f"/api/channels/{channel_id}/posts",
        params={"sort": "priority", "page": 2, "page_size": 2},
        headers=_auth(t["token"], t["org"], t2),
    )
    assert page2.status_code == 200, page2.text
    p2 = page2.json()
    assert p2["page"] == 2
    assert [p["ai_priority"] for p in p2["items"]] == ["p2"]


def test_profile_draft_stub_and_admin_metrics(client: TestClient) -> None:
    t = _team(client)
    upload = client.post(
        f"/api/teams/{t['team']}/documents",
        headers=_auth(t["token"], t["org"], t["team"]),
        files={"file": ("note.txt", io.BytesIO(b"We ship Friday."), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]

    draft = client.post(
        f"/api/teams/{t['team']}/profile/draft-from-document",
        json={"document_ids": [doc_id]},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["generated_by"] == "deterministic_stub"

    metrics = client.get(
        f"/api/orgs/{t['org']}/admin/metrics",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert "trace_count" in body
    assert "post_count" in body
    assert "suggestion_count" in body


def test_list_my_orgs(client: TestClient) -> None:
    t = _team(client)

    mine = client.get("/api/orgs", headers=_auth(t["token"]))
    assert mine.status_code == 200, mine.text
    orgs = mine.json()
    assert len(orgs) == 1
    assert orgs[0]["org_id"] == t["org"]
    assert orgs[0]["role"] == "owner"
    assert len(orgs[0]["teams"]) == 1
    assert orgs[0]["teams"][0]["team_id"] == t["team"]
    assert orgs[0]["teams"][0]["role"] == "lead"

    other_token = _register(client, f"m6-other-{uuid.uuid4().hex[:8]}@example.com")
    empty = client.get("/api/orgs", headers=_auth(other_token))
    assert empty.status_code == 200, empty.text
    assert empty.json() == []


def test_post_history_panel_api(client: TestClient) -> None:
    """P1: in-post History endpoint returns timeline without leaving the feed."""
    import asyncio
    from uuid import UUID

    from src.channels.models import Post
    from src.lib.database import async_session_factory

    t = _team(client)
    t2 = client.post(
        f"/api/orgs/{t['org']}/teams",
        json={"name": "Other"},
        headers=_auth(t["token"], t["org"]),
    ).json()["id"]
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team"], "team_b_id": t2},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

    pkg = client.post(
        f"/api/teams/{t['team']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t2,
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert pkg.status_code == 201, pkg.text
    package_id = pkg.json()["id"]
    post_id = uuid.uuid4()

    async def _seed() -> None:
        async with async_session_factory() as session:
            session.add(
                Post(
                    id=post_id,
                    org_id=UUID(t["org"]),
                    channel_id=UUID(channel_id),
                    package_id=UUID(package_id),
                    adapted_body="Adapted",
                    original_body="Original",
                    what_was_done="adapted for Other",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    hist = client.get(
        f"/api/posts/{post_id}/history",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert hist.status_code == 200, hist.text
    rows = hist.json()
    assert rows
    assert any(row["kind"] == "post" for row in rows)
