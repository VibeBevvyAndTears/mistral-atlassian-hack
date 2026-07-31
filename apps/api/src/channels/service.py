"""Channel + package + post services (M4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.channels.models import (
    Channel,
    ChannelPostsPage,
    ChannelResponse,
    CrossTeamAccessLog,
    JudgeSummary,
    Package,
    PackageResponse,
    Post,
    PostHistoryEntry,
    PostResponse,
    PostSourceDocument,
    PostSourcesResponse,
    Rendition,
)
from src.jobs.queue import JobKind, enqueue
from src.review.models import ReadState
from src.tenancy.models import SourceDocument, Team, TeamProfile
from src.users.model import User


def _ordered_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if a.hex < b.hex else (b, a)


async def get_or_create_channel(
    db: AsyncSession, *, org_id: UUID, team_a: UUID, team_b: UUID
) -> Channel:
    if team_a == team_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel requires two distinct teams",
        )
    a, b = _ordered_pair(team_a, team_b)
    existing = await db.execute(
        select(Channel).where(
            Channel.org_id == org_id,
            Channel.team_a_id == a,
            Channel.team_b_id == b,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        return row
    # validate teams in org
    for tid in (a, b):
        team = await db.get(Team, tid)
        if team is None or team.org_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
            )
    channel = Channel(id=uuid.uuid4(), org_id=org_id, team_a_id=a, team_b_id=b)
    db.add(channel)
    await db.flush()
    return channel


def channel_response(
    c: Channel,
    *,
    team_a_name: str | None = None,
    team_b_name: str | None = None,
    peer_team_id: UUID | None = None,
    peer_team_name: str | None = None,
) -> ChannelResponse:
    return ChannelResponse(
        id=str(c.id),
        org_id=str(c.org_id),
        team_a_id=str(c.team_a_id),
        team_b_id=str(c.team_b_id),
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        peer_team_id=str(peer_team_id) if peer_team_id else None,
        peer_team_name=peer_team_name,
        created_at=c.created_at,
    )


async def list_team_channels(
    db: AsyncSession, *, org_id: UUID, team_id: UUID
) -> list[ChannelResponse]:
    rows = (
        await db.execute(
            select(Channel)
            .where(
                Channel.org_id == org_id,
                (Channel.team_a_id == team_id) | (Channel.team_b_id == team_id),
            )
            .order_by(Channel.created_at.desc())
        )
    ).scalars().all()
    team_ids = {c.team_a_id for c in rows} | {c.team_b_id for c in rows}
    names: dict[UUID, str] = {}
    if team_ids:
        teams = (
            await db.execute(select(Team).where(Team.id.in_(team_ids)))
        ).scalars().all()
        names = {t.id: t.name for t in teams}
    out: list[ChannelResponse] = []
    for c in rows:
        peer = c.team_b_id if c.team_a_id == team_id else c.team_a_id
        out.append(
            channel_response(
                c,
                team_a_name=names.get(c.team_a_id),
                team_b_name=names.get(c.team_b_id),
                peer_team_id=peer,
                peer_team_name=names.get(peer),
            )
        )
    return out


async def run_presend_checklist(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    bypass_incomplete: bool,
    target_team_id: UUID | None = None,
    package_body: str = "",
    included_node_ids: list[UUID] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Deterministic FR-9 checklist (no LLM)."""
    from src.conflict.models import Decision, ReviewItem
    from src.glossary.models import GlossaryTerm
    from src.graph.models import Node

    checks: dict[str, Any] = {}
    bypassed: list[str] = []

    profile = await db.execute(
        select(TeamProfile)
        .where(TeamProfile.team_id == team_id)
        .order_by(TeamProfile.version.desc())
        .limit(1)
    )
    checks["team_profile_present"] = profile.scalar_one_or_none() is not None

    incomplete = (
        (
            await db.execute(
                select(SourceDocument).where(
                    SourceDocument.org_id == org_id,
                    SourceDocument.team_id == team_id,
                    SourceDocument.status.in_(("queued", "running")),
                )
            )
        )
        .scalars()
        .all()
    )
    checks["pipeline_complete"] = len(incomplete) == 0
    if incomplete and bypass_incomplete:
        bypassed.append(
            f"pipeline_incomplete_for_source({','.join(str(d.id) for d in incomplete)})"
        )
        checks["pipeline_complete"] = True  # allowed via bypass

    open_reviews = (
        await db.execute(
            select(ReviewItem).where(
                ReviewItem.org_id == org_id,
                ReviewItem.team_id == team_id,
                ReviewItem.status == "open",
            )
        )
    ).scalars().all()
    checks["no_unresolved_review_items"] = len(open_reviews) == 0

    unowned = (
        await db.execute(
            select(Decision).where(
                Decision.org_id == org_id,
                Decision.team_id == team_id,
                Decision.owner_team_id.is_(None),
                Decision.status.notin_(("superseded",)),
            )
        )
    ).scalars().all()
    # FR-9.5 — unowned decision always fails the checklist (receiver/owner mandatory)
    checks["no_unowned_decisions"] = len(unowned) == 0
    checks["unowned_decision_ids"] = [str(d.id) for d in unowned]
    checks["unowned_decision_titles"] = [d.title for d in unowned]

    dangling = False
    if included_node_ids:
        for nid in included_node_ids:
            node = await db.get(Node, nid)
            if node is None or node.org_id != org_id or node.team_id != team_id:
                dangling = True
                break
    checks["no_dangling_excluded_refs"] = not dangling

    unknown_terms: list[str] = []
    if target_team_id is not None and package_body:
        terms = (
            await db.execute(
                select(GlossaryTerm).where(
                    GlossaryTerm.org_id == org_id,
                    GlossaryTerm.team_id == target_team_id,
                    GlossaryTerm.kind == "must_explain",
                )
            )
        ).scalars().all()
        body_lower = package_body.casefold()
        for term in terms:
            token = (term.term or "").strip()
            if token and token.casefold() in body_lower:
                unknown_terms.append(token)
        # Also scan target profile jargon_must_explain if present
        tprof = (
            await db.execute(
                select(TeamProfile)
                .where(TeamProfile.team_id == target_team_id)
                .order_by(TeamProfile.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if tprof and isinstance(tprof.data, dict):
            for token in tprof.data.get("jargon_must_explain") or []:
                if isinstance(token, str) and token.casefold() in body_lower:
                    unknown_terms.append(token)
    checks["no_unknown_receiving_terms"] = len(unknown_terms) == 0
    checks["unknown_terms"] = sorted(set(unknown_terms))

    checks["ok"] = bool(
        checks["team_profile_present"]
        and checks["pipeline_complete"]
        and checks["no_unresolved_review_items"]
        and checks["no_unowned_decisions"]
        and checks["no_dangling_excluded_refs"]
        and checks["no_unknown_receiving_terms"]
    )
    return checks, bypassed


async def create_package(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    title: str,
    body: str,
    target_team_id: UUID,
    bypass_incomplete: bool = False,
    included_node_ids: list[UUID] | None = None,
    topic_tags: list[str] | None = None,
    attached_document_ids: list[UUID] | None = None,
) -> PackageResponse:
    target = await db.get(Team, target_team_id)
    if target is None or target.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    channel = await get_or_create_channel(
        db, org_id=org_id, team_a=team_id, team_b=target_team_id
    )
    from src.conflict import service as conflict_service

    await conflict_service.attach_decisions_to_channel(
        db, org_id=org_id, team_id=team_id, channel_id=channel.id
    )
    node_ids = list(included_node_ids or [])
    checklist, bypassed = await run_presend_checklist(
        db,
        org_id=org_id,
        team_id=team_id,
        bypass_incomplete=bypass_incomplete,
        target_team_id=target_team_id,
        package_body=body,
        included_node_ids=node_ids,
    )
    composer_tags = [t.strip() for t in (topic_tags or []) if t and t.strip()]
    composer_docs = [str(d) for d in (attached_document_ids or [])]
    if composer_tags:
        checklist = {**checklist, "composer_tags": composer_tags}
    if composer_docs:
        checklist = {**checklist, "composer_document_ids": composer_docs}
    pkg = Package(
        id=uuid.uuid4(),
        org_id=org_id,
        team_id=team_id,
        target_team_id=target_team_id,
        channel_id=channel.id,
        title=title,
        body=body,
        status="draft",
        bypassed_checks=bypassed,
        checklist=checklist,
        included_node_ids=[str(n) for n in node_ids],
        created_by=user_id,
    )
    db.add(pkg)
    await db.flush()
    return _package_response(pkg)


def _package_response(pkg: Package) -> PackageResponse:
    return PackageResponse(
        id=str(pkg.id),
        team_id=str(pkg.team_id),
        target_team_id=str(pkg.target_team_id),
        channel_id=str(pkg.channel_id) if pkg.channel_id else None,
        title=pkg.title,
        body=pkg.body,
        status=pkg.status,
        bypassed_checks=[str(x) for x in (pkg.bypassed_checks or [])],
        checklist=dict(pkg.checklist or {}),
        included_node_ids=[str(x) for x in (pkg.included_node_ids or [])],
        conflicts_acknowledged=bool(pkg.conflicts_acknowledged),
        job_id=str(pkg.job_id) if pkg.job_id else None,
        created_at=pkg.created_at,
    )


async def get_package(
    db: AsyncSession, *, org_id: UUID, package_id: UUID, team_id: UUID | None
) -> PackageResponse:
    pkg = await db.get(Package, package_id)
    if pkg is None or pkg.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )
    if team_id is not None and pkg.team_id != team_id and pkg.target_team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )
    return _package_response(pkg)


async def enqueue_send(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    package_id: UUID,
    actor_role: str,
    acknowledge_conflicts: bool = False,
) -> PackageResponse:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Lead role required to send"
        )
    pkg = await db.get(Package, package_id)
    if pkg is None or pkg.org_id != org_id or pkg.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )
    if not (pkg.checklist or {}).get("ok"):
        checklist = pkg.checklist or {}
        detail = "Pre-send checklist failed"
        if checklist.get("no_unowned_decisions") is False:
            titles = checklist.get("unowned_decision_titles") or []
            detail = (
                "Cannot send: every decision needs an owner (receiver). "
                f"Unowned: {', '.join(titles) if titles else 'unknown'}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
    if acknowledge_conflicts:
        pkg.conflicts_acknowledged = True
    job_id = await enqueue(
        db,
        JobKind.send_package,
        {
            "package_id": str(pkg.id),
            "org_id": str(org_id),
            "team_id": str(team_id),
            "target_team_id": str(pkg.target_team_id),
            "acknowledge_conflicts": bool(pkg.conflicts_acknowledged),
        },
        dedupe_key=f"send:{pkg.id}",
    )
    pkg.job_id = job_id
    pkg.status = "sending"
    await db.flush()
    return _package_response(pkg)


async def log_cross_team_access(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_a: UUID,
    team_b: UUID,
    purpose: str,
    package_id: UUID | None = None,
    who_user_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        CrossTeamAccessLog(
            id=uuid.uuid4(),
            org_id=org_id,
            who_user_id=who_user_id,
            team_a_id=team_a,
            team_b_id=team_b,
            purpose=purpose,
            package_id=package_id,
            meta=meta or {},
        )
    )


async def create_post_with_rendition(
    db: AsyncSession,
    *,
    org_id: UUID,
    channel_id: UUID,
    package_id: UUID,
    original_body: str,
    adapted_body: str,
    what_was_done: str,
    priority: str | None,
    priority_reason: str | None,
    bypassed_checks: list[str],
    fidelity: str | None,
    fit: str | None,
    confidence: float | None,
    badge: str | None,
    judge_payload: dict[str, Any],
    topic_tags: list[str] | None = None,
    attached_conflicts: list[dict[str, Any]] | None = None,
) -> Post:
    post = Post(
        id=uuid.uuid4(),
        org_id=org_id,
        channel_id=channel_id,
        package_id=package_id,
        adapted_body=adapted_body,
        original_body=original_body,
        what_was_done=what_was_done,
        ai_priority=priority,
        ai_priority_reason=priority_reason,
        topic_tags=list(topic_tags or []),
        bypassed_checks=bypassed_checks,
        attached_conflicts=list(attached_conflicts or []),
    )
    db.add(post)
    await db.flush()
    db.add(
        Rendition(
            id=uuid.uuid4(),
            post_id=post.id,
            org_id=org_id,
            body=adapted_body,
            fidelity_verdict=fidelity,
            fit_verdict=fit,
            overall_confidence=confidence,
            badge=badge,
            judge_payload=judge_payload,
        )
    )
    await db.flush()
    return post


def _search_tokens(q: str | None) -> list[str]:
    if not q:
        return []
    return [t for t in q.casefold().split() if t]


def _post_search_score(post: PostResponse, tokens: list[str]) -> float:
    """Weighted multi-field lexical score.

    Algorithm (channel-scoped):
      1. Tokenize query on whitespace (case-insensitive).
      2. Every token must match at least one field (AND semantics).
      3. Score = sum over tokens of the best field weight hit:
           package title 5 · topic tags 4 · adapted body 2 ·
           original / what_was_done / sender 1
      4. Tie-break with the active feed sort outside this function.

    Good enough for per-channel feeds; upgrade path is Postgres
    tsvector + optional embeddings when channels grow large.
    """
    if not tokens:
        return 0.0
    title = (post.package_title or "").casefold()
    tags = " ".join(post.topic_tags).casefold()
    adapted = (post.adapted_body or "").casefold()
    original = (post.original_body or "").casefold()
    done = (post.what_was_done or "").casefold()
    sender = f"{post.sender_name or ''} {post.sender_team_name or ''}".casefold()

    score = 0.0
    for token in tokens:
        weights: list[int] = []
        if token in title:
            weights.append(5)
        if token in tags:
            weights.append(4)
        if token in adapted:
            weights.append(2)
        if token in original or token in done or token in sender:
            weights.append(1)
        if not weights:
            return -1.0  # token missing → no match
        score += max(weights)
    return score


def _priority_rank_value(priority: str | None) -> int:
    key = (priority or "").casefold()
    return {"p0": 0, "p1": 1, "p2": 2, "p3": 3}.get(key, 4)


async def list_channel_posts(
    db: AsyncSession,
    *,
    org_id: UUID,
    channel_id: UUID,
    team_id: UUID,
    user_id: UUID,
    sort: Literal["priority", "newest", "oldest"] = "newest",
    unread_only: bool = False,
    topic_tags: list[str] | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> ChannelPostsPage:
    channel = await db.get(Channel, channel_id)
    if (
        channel is None
        or channel.org_id != org_id
        or team_id not in (channel.team_a_id, channel.team_b_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )

    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    tokens = _search_tokens(q)

    stmt = (
        select(Post, ReadState.id)
        .outerjoin(
            ReadState,
            (ReadState.post_id == Post.id) & (ReadState.user_id == user_id),
        )
        .where(Post.channel_id == channel_id, Post.org_id == org_id)
    )
    if unread_only:
        stmt = stmt.where(ReadState.id.is_(None))

    # Cheap SQL prefilter when searching — still AND-score in Python for tags/sender
    if tokens:
        stmt = stmt.outerjoin(Package, Package.id == Post.package_id)
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                Post.adapted_body.ilike(pattern)
                | Post.original_body.ilike(pattern)
                | Post.what_was_done.ilike(pattern)
                | Package.title.ilike(pattern)
            )

    # Stable fetch order; final ranking applied in Python after scoring/filters
    stmt = stmt.order_by(Post.created_at.desc())
    rows = (await db.execute(stmt)).all()
    required_tags = {tag.casefold() for tag in (topic_tags or []) if tag}

    scored: list[PostResponse] = []
    for post, read_id in rows:
        if required_tags and not required_tags.intersection(
            str(tag).casefold() for tag in (post.topic_tags or [])
        ):
            continue
        item = await _post_response(db, post, is_read=read_id is not None)
        if tokens:
            score = _post_search_score(item, tokens)
            if score < 0:
                continue
            item.search_score = score
        scored.append(item)

    if tokens:
        # Relevance first, then active feed sort as tie-break
        if sort == "oldest":
            scored.sort(
                key=lambda p: (
                    -(p.search_score or 0),
                    p.created_at,
                )
            )
        elif sort == "priority":
            scored.sort(
                key=lambda p: (
                    -(p.search_score or 0),
                    0 if not p.is_read else 1,
                    _priority_rank_value(p.ai_priority),
                    -p.created_at.timestamp(),
                )
            )
        else:
            scored.sort(
                key=lambda p: (
                    -(p.search_score or 0),
                    -p.created_at.timestamp(),
                )
            )
    elif sort == "oldest":
        scored.sort(key=lambda p: p.created_at)
    elif sort == "priority":
        scored.sort(
            key=lambda p: (
                0 if not p.is_read else 1,
                _priority_rank_value(p.ai_priority),
                -p.created_at.timestamp(),
            )
        )
    else:
        scored.sort(key=lambda p: p.created_at, reverse=True)

    total = len(scored)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    items = scored[start : start + page_size]
    return ChannelPostsPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        q=q.strip() if q and q.strip() else None,
    )


async def get_post(
    db: AsyncSession,
    *,
    org_id: UUID,
    post_id: UUID,
    team_id: UUID,
    user_id: UUID | None = None,
) -> PostResponse:
    post = await db.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    channel = await db.get(Channel, post.channel_id)
    if channel is None or team_id not in (channel.team_a_id, channel.team_b_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    is_read = False
    if user_id is not None:
        is_read = (
            await db.scalar(
                select(ReadState.id).where(
                    ReadState.user_id == user_id, ReadState.post_id == post.id
                )
            )
            is not None
        )
    return await _post_response(db, post, is_read=is_read)


async def mark_post_read(
    db: AsyncSession,
    *,
    org_id: UUID,
    post_id: UUID,
    team_id: UUID,
    user_id: UUID,
) -> PostResponse:
    await get_post(
        db,
        org_id=org_id,
        post_id=post_id,
        team_id=team_id,
        user_id=user_id,
    )
    read_state = await db.scalar(
        select(ReadState).where(
            ReadState.user_id == user_id, ReadState.post_id == post_id
        )
    )
    if read_state is None:
        db.add(
            ReadState(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user_id,
                post_id=post_id,
            )
        )
    else:
        read_state.read_at = datetime.now(UTC)
    await db.flush()
    post = await db.get(Post, post_id)
    assert post is not None
    return await _post_response(db, post, is_read=True)


async def list_post_history(
    db: AsyncSession, *, org_id: UUID, post_id: UUID, team_id: UUID
) -> list[PostHistoryEntry]:
    """Node/rendition change sidebar data for a post (FR-10.6 / FR-10.7)."""
    from src.graph.models import NodeHistory
    from src.review.models import Suggestion

    post = await db.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    channel = await db.get(Channel, post.channel_id)
    if channel is None or team_id not in (channel.team_a_id, channel.team_b_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501

    entries: list[PostHistoryEntry] = [
        PostHistoryEntry(
            kind="post",
            summary=post.what_was_done or "Post created",
            source="agent" if post.what_was_done else "system",
            created_at=post.created_at,
            meta={
                "version": post.version,
                "updated_since_send": post.updated_since_send,
            },
        )
    ]

    renditions = (
        await db.execute(
            select(Rendition)
            .where(Rendition.post_id == post.id, Rendition.org_id == org_id)
            .order_by(Rendition.created_at.desc())
        )
    ).scalars().all()
    for r in renditions:
        entries.append(
            PostHistoryEntry(
                kind="rendition",
                summary=f"Rendition badge={r.badge or '—'} fidelity={r.fidelity_verdict or '—'}",  # noqa: E501
                source="agent",
                created_at=r.created_at,
                meta={"rendition_id": str(r.id), "badge": r.badge},
            )
        )

    suggestions = (
        await db.execute(
            select(Suggestion)
            .where(Suggestion.post_id == post.id, Suggestion.org_id == org_id)
            .order_by(Suggestion.created_at.desc())
        )
    ).scalars().all()
    for s in suggestions:
        entries.append(
            PostHistoryEntry(
                kind="suggestion",
                summary=f"Suggestion {s.status}: {(s.adapted_preview or s.original_text)[:120]}",  # noqa: E501
                source="human",
                created_at=s.created_at,
                node_id=str(s.target_node_id) if s.target_node_id else None,
                meta={"suggestion_id": str(s.id), "response": s.response},
            )
        )
        if s.target_node_id is not None:
            histories = (
                await db.execute(
                    select(NodeHistory)
                    .where(
                        NodeHistory.node_id == s.target_node_id,
                        NodeHistory.org_id == org_id,
                    )
                    .order_by(NodeHistory.created_at.desc())
                    .limit(5)
                )
            ).scalars().all()
            for h in histories:
                snap = h.snapshot or {}
                entries.append(
                    PostHistoryEntry(
                        kind="node",
                        summary=str(snap.get("summary") or f"Node v{h.version}"),
                        source="human" if h.source == "suggestion" else h.source,
                        created_at=h.created_at,
                        node_id=str(h.node_id),
                        meta={
                            "version": h.version,
                            "source_suggestion_id": snap.get("source_suggestion_id"),
                        },
                    )
                )

    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


async def list_post_sources(
    db: AsyncSession, *, org_id: UUID, post_id: UUID, team_id: UUID
) -> PostSourcesResponse:
    """Originating document(s) for a post (FR-10.6 View source)."""
    post = await db.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    channel = await db.get(Channel, post.channel_id)
    if channel is None or team_id not in (channel.team_a_id, channel.team_b_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    pkg = await db.get(Package, post.package_id)
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")  # noqa: E501

    from src.graph.models import Node
    from src.tenancy.models import SourceDocument

    doc_ids: set[UUID] = set()
    for raw in pkg.included_node_ids or []:
        try:
            nid = UUID(str(raw))
        except ValueError:
            continue
        node = await db.get(Node, nid)
        if node is not None and node.document_id is not None:
            doc_ids.add(node.document_id)

    for raw in (pkg.checklist or {}).get("composer_document_ids") or []:
        try:
            doc_ids.add(UUID(str(raw)))
        except ValueError:
            continue

    documents: list[PostSourceDocument] = []
    for did in sorted(doc_ids, key=str):
        doc = await db.get(SourceDocument, did)
        if doc is None or doc.org_id != org_id:
            continue
        documents.append(
            PostSourceDocument(
                id=str(doc.id),
                filename=doc.filename,
                status=doc.status,
                content_type=doc.content_type,
            )
        )
    return PostSourcesResponse(
        package_id=str(pkg.id),
        package_title=pkg.title,
        documents=documents,
    )


def _parse_storage_uri(storage_uri: str) -> tuple[str, str]:
    """Return (bucket, key) from a local:// or Azure blob URL."""
    from urllib.parse import unquote, urlparse

    if storage_uri.startswith("local://"):
        rest = storage_uri.removeprefix("local://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            raise ValueError("invalid local storage uri")
        return bucket, key

    parsed = urlparse(storage_uri)
    path = unquote(parsed.path.lstrip("/"))
    bucket, _, key = path.partition("/")
    if not bucket or not key:
        raise ValueError("invalid blob storage uri")
    return bucket, key


async def read_post_source_bytes(
    db: AsyncSession,
    *,
    org_id: UUID,
    post_id: UUID,
    team_id: UUID,
    document_id: UUID,
) -> tuple[bytes, str, str | None]:
    """Load source file bytes for a post-linked document (channel peers only)."""
    sources = await list_post_sources(
        db, org_id=org_id, post_id=post_id, team_id=team_id
    )
    match = next((d for d in sources.documents if d.id == str(document_id)), None)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found"
        )

    from src.lib.storage.factory import get_storage_provider
    from src.tenancy.models import SourceDocument

    doc = await db.get(SourceDocument, document_id)
    if doc is None or doc.org_id != org_id or not doc.storage_uri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found"
        )

    try:
        bucket, key = _parse_storage_uri(doc.storage_uri)
        data = await get_storage_provider().download(bucket, key)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source file unavailable",
        ) from exc

    return data, doc.filename, doc.content_type


async def _post_response(
    db: AsyncSession, post: Post, *, is_read: bool = False
) -> PostResponse:
    rend = (
        await db.execute(
            select(Rendition)
            .where(Rendition.post_id == post.id)
            .order_by(Rendition.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    judge = None
    if rend is not None:
        judge = JudgeSummary(
            fidelity=rend.fidelity_verdict,
            fit=rend.fit_verdict,
            overall_confidence=rend.overall_confidence,
            badge=rend.badge,
        )

    package_title: str | None = None
    sender_team_id: str | None = None
    sender_team_name: str | None = None
    sender_name: str | None = None
    topic_tags = [str(t) for t in (post.topic_tags or [])]
    pkg = await db.get(Package, post.package_id)
    if pkg is not None:
        package_title = pkg.title
        sender_team_id = str(pkg.team_id)
        team = await db.get(Team, pkg.team_id)
        if team is not None:
            sender_team_name = team.name
        user = await db.get(User, pkg.created_by)
        if user is not None:
            sender_name = user.name or user.username or user.email
        # Backfill topic tags from sender node labels when post was stored empty
        if not topic_tags and pkg.included_node_ids:
            from src.graph.models import Node

            for raw in pkg.included_node_ids:
                try:
                    nid = UUID(str(raw))
                except ValueError:
                    continue
                node = await db.get(Node, nid)
                if node is not None and node.label:
                    label = str(node.label)
                    if label not in topic_tags:
                        topic_tags.append(label)

    return PostResponse(
        id=str(post.id),
        channel_id=str(post.channel_id),
        package_id=str(post.package_id),
        package_title=package_title,
        version=post.version,
        adapted_body=post.adapted_body,
        original_body=post.original_body,
        what_was_done=post.what_was_done,
        ai_priority=post.ai_priority,
        ai_priority_reason=post.ai_priority_reason,
        topic_tags=topic_tags,
        bypassed_checks=[str(x) for x in (post.bypassed_checks or [])],
        attached_conflicts=[dict(c) for c in (post.attached_conflicts or []) if isinstance(c, dict)],  # noqa: E501
        updated_since_send=post.updated_since_send,
        is_read=is_read,
        judge=judge,
        sender_team_id=sender_team_id,
        sender_team_name=sender_team_name,
        sender_name=sender_name,
        created_at=post.created_at,
    )
