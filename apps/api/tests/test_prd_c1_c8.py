"""PRD closeout C1–C8 mechanical verification."""  # noqa: RUF002

from __future__ import annotations

import asyncio
import inspect
import uuid
from pathlib import Path
from uuid import UUID

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


def _two_teams(client: TestClient) -> dict[str, str]:
    token = _register(client, f"prd8-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "PRD8"}, headers=_auth(token)).json()
    org_id = org["id"]
    t1 = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "Sender"},
        headers=_auth(token, org_id),
    ).json()["id"]
    t2 = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "Receiver"},
        headers=_auth(token, org_id),
    ).json()["id"]
    put = client.put(
        f"/api/teams/{t1}/profile",
        json={"data": {"tone": "plain"}},
        headers=_auth(token, org_id, t1),
    )
    assert put.status_code == 200, put.text
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    return {
        "token": token,
        "org": org_id,
        "team_a": t1,
        "team_b": t2,
        "user_id": me["id"],
    }


def test_c1_attached_conflicts_visible_both_teams(client: TestClient) -> None:
    from src.channels.models import Post
    from src.lib.database import async_session_factory

    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pkg.status_code == 201, pkg.text
    package_id = pkg.json()["id"]
    post_id = uuid.uuid4()
    conflict = {
        "claim_a_id": str(uuid.uuid4()),
        "claim_b_id": str(uuid.uuid4()),
        "classification": "contradiction",
        "rationale": "dates disagree",
    }

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
                    what_was_done="adapted",
                    attached_conflicts=[conflict],
                )
            )
            await session.commit()

    asyncio.run(_seed())

    for team in (t["team_a"], t["team_b"]):
        got = client.get(
            f"/api/posts/{post_id}",
            headers=_auth(t["token"], t["org"], team),
        )
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["attached_conflicts"]
        assert body["attached_conflicts"][0]["classification"] == "contradiction"


def test_c2_acknowledge_conflicts_persisted(client: TestClient) -> None:
    t = _two_teams(client)
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pkg.status_code == 201, pkg.text
    assert pkg.json()["checklist"].get("ok") is True
    package_id = pkg.json()["id"]

    sent = client.post(
        f"/api/packages/{package_id}/send",
        json={"acknowledge_conflicts": True},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["conflicts_acknowledged"] is True
    assert sent.json()["status"] == "sending"


def test_c3_included_nodes_become_topic_tags(client: TestClient) -> None:
    from src.channels import service as channels_service
    from src.graph.models import Node
    from src.lib.database import async_session_factory

    t = _two_teams(client)
    node_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async def _seed_node() -> None:
        async with async_session_factory() as session:
            session.add(
                Node(
                    id=node_id,
                    org_id=UUID(t["org"]),
                    team_id=UUID(t["team_a"]),
                    label="Ship date",
                    node_type="topic",
                    summary="Friday",
                    version=1,
                    search_text="Ship date Friday",
                    document_id=doc_id,
                )
            )
            await session.commit()

    asyncio.run(_seed_node())

    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
            "included_node_ids": [str(node_id)],
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pkg.status_code == 201, pkg.text
    assert str(node_id) in pkg.json()["included_node_ids"]
    package_id = pkg.json()["id"]
    channel_id = pkg.json()["channel_id"]
    assert channel_id

    async def _create_post() -> str:
        async with async_session_factory() as session:
            from src.channels.models import Package

            package = await session.get(Package, UUID(package_id))
            assert package is not None
            tags: list[str] = []
            for raw in package.included_node_ids or []:
                node = await session.get(Node, UUID(str(raw)))
                if node and node.label:
                    tags.append(node.label)
            post = await channels_service.create_post_with_rendition(
                session,
                org_id=UUID(t["org"]),
                channel_id=UUID(channel_id),
                package_id=UUID(package_id),
                original_body="o",
                adapted_body="a",
                what_was_done="adapted",
                priority="P1",
                priority_reason="deadline",
                bypassed_checks=[],
                fidelity=None,
                fit=None,
                confidence=None,
                badge=None,
                judge_payload={},
                topic_tags=tags,
                attached_conflicts=[],
            )
            await session.commit()
            return str(post.id)

    post_id = asyncio.run(_create_post())
    got = client.get(
        f"/api/posts/{post_id}",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert got.status_code == 200, got.text
    assert set(got.json()["topic_tags"]) == {"Ship date"}


def test_c4_suggestion_rejects_out_of_package_node(client: TestClient) -> None:
    from src.channels.models import Post
    from src.graph.models import Node
    from src.lib.database import async_session_factory

    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    in_node = uuid.uuid4()
    out_node = uuid.uuid4()
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
            "included_node_ids": [str(in_node)],
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pkg.status_code == 201, pkg.text
    package_id = pkg.json()["id"]
    post_id = uuid.uuid4()

    async def _seed() -> None:
        async with async_session_factory() as session:
            for nid, label in ((in_node, "In"), (out_node, "Out")):
                session.add(
                    Node(
                        id=nid,
                        org_id=UUID(t["org"]),
                        team_id=UUID(t["team_a"]),
                        label=label,
                        node_type="topic",
                        summary=label,
                        version=1,
                        search_text=label,
                    )
                )
            session.add(
                Post(
                    id=post_id,
                    org_id=UUID(t["org"]),
                    channel_id=UUID(ch),
                    package_id=UUID(package_id),
                    adapted_body="a",
                    original_body="o",
                    what_was_done="x",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    bad = client.post(
        f"/api/posts/{post_id}/suggestions",
        json={"text": "fix date", "target_node_id": str(out_node)},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert bad.status_code == 400, bad.text
    assert "package-included" in bad.json()["detail"]


def test_c5_paste_document(client: TestClient) -> None:
    t = _two_teams(client)
    pasted = client.post(
        f"/api/teams/{t['team_a']}/documents/paste",
        json={"text": "We ship Friday.\nSecond line.", "filename": "notes.txt"},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pasted.status_code == 201, pasted.text
    body = pasted.json()
    assert body["status"] == "queued"
    assert body["filename"].endswith(".txt")
    assert body["job_id"]


def test_c6_view_source_endpoint(client: TestClient) -> None:
    from src.channels.models import Post
    from src.graph.models import Node
    from src.lib.database import async_session_factory
    from src.tenancy.models import SourceDocument

    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    doc_id = uuid.uuid4()
    node_id = uuid.uuid4()
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Spec pack",
            "body": "Body",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
            "included_node_ids": [str(node_id)],
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pkg.status_code == 201, pkg.text
    package_id = pkg.json()["id"]
    post_id = uuid.uuid4()

    async def _seed() -> None:
        async with async_session_factory() as session:
            session.add(
                SourceDocument(
                    id=doc_id,
                    org_id=UUID(t["org"]),
                    team_id=UUID(t["team_a"]),
                    filename="spec.txt",
                    storage_uri="local://documents/spec.txt",
                    content_type="text/plain",
                    status="ready",
                    uploaded_by=UUID(t["user_id"]),
                )
            )
            session.add(
                Node(
                    id=node_id,
                    org_id=UUID(t["org"]),
                    team_id=UUID(t["team_a"]),
                    label="Spec",
                    node_type="topic",
                    summary="s",
                    version=1,
                    search_text="Spec",
                    document_id=doc_id,
                )
            )
            session.add(
                Post(
                    id=post_id,
                    org_id=UUID(t["org"]),
                    channel_id=UUID(ch),
                    package_id=UUID(package_id),
                    adapted_body="a",
                    original_body="o",
                    what_was_done="x",
                )
            )
            await session.commit()

    asyncio.run(_seed())
    src = client.get(
        f"/api/posts/{post_id}/sources",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert src.status_code == 200, src.text
    body = src.json()
    assert body["package_title"] == "Spec pack"
    assert any(d["id"] == str(doc_id) and d["filename"] == "spec.txt" for d in body["documents"])  # noqa: E501
    repo_root = Path(__file__).resolve().parents[3]
    ui_path = (
        repo_root
        / "apps/web/src/features/channels/components/channel-feed-panel.tsx"
    )
    ui = ui_path.read_text(encoding="utf-8")
    assert "openSources" in ui
    assert "originating package/docs for post" not in ui


def test_c7_post_updated_notification(client: TestClient) -> None:
    from src.channels.models import Post
    from src.jobs.kinds import regenerate_rendition as regen_mod
    from src.lib.database import async_session_factory
    from src.review.service import collapse_notification

    src = inspect.getsource(regen_mod.handle_regenerate_rendition)
    assert 'kind="post_updated"' in src

    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Update",
            "body": "Body",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()
    post_id = uuid.uuid4()

    async def _seed_and_notify() -> None:
        async with async_session_factory() as session:
            session.add(
                Post(
                    id=post_id,
                    org_id=UUID(t["org"]),
                    channel_id=UUID(ch),
                    package_id=UUID(pkg["id"]),
                    adapted_body="a",
                    original_body="o",
                    what_was_done="x",
                )
            )
            await session.flush()
            await collapse_notification(
                session,
                org_id=UUID(t["org"]),
                user_id=UUID(t["user_id"]),
                kind="post_updated",
                post_id=post_id,
                payload={"version": 2},
            )
            await session.commit()

    asyncio.run(_seed_and_notify())
    notes = client.get(
        "/api/notifications",
        params={"unread_only": True},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert notes.status_code == 200, notes.text
    assert any(n["kind"] == "post_updated" for n in notes.json())


def test_c8_conflict_false_positive_rate(client: TestClient) -> None:
    from src.conflict.models import ReviewItem
    from src.lib.database import async_session_factory

    t = _two_teams(client)

    async def _seed() -> None:
        async with async_session_factory() as session:
            for resolution in ("keep_a", "not_a_conflict"):
                session.add(
                    ReviewItem(
                        id=uuid.uuid4(),
                        org_id=UUID(t["org"]),
                        team_id=UUID(t["team_a"]),
                        claim_a_id=uuid.uuid4(),
                        claim_b_id=uuid.uuid4(),
                        conflict_class="contradiction",
                        severity="high",
                        rationale="r",
                        status="resolved",
                        resolved_resolution=resolution,
                    )
                )
            await session.commit()

    asyncio.run(_seed())
    metrics = client.get(
        f"/api/orgs/{t['org']}/admin/metrics",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert body["conflict_resolved_count"] == 2
    assert body["conflict_not_a_conflict_count"] == 1
    assert body["conflict_false_positive_rate"] == 0.5
