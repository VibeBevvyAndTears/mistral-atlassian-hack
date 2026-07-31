"""Review-loop services (M5) — suggestions, actions, comments, reverse adapt, notif collapse."""  # noqa: E501

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import get_mistral_provider
from src.channels.models import Channel, Package, Post
from src.graph.models import Node, NodeHistory
from src.jobs.queue import JobKind, enqueue
from src.lib.config import settings
from src.notifications.service import create_notification
from src.pipeline.contracts._common import (
    AdaptationDirection,
    SubjectType,
    TeamProfileSnapshot,
)
from src.pipeline.contracts.adaptation import (
    CONTRACT_VERSION as ADAPT_CV,
)
from src.pipeline.contracts.adaptation import (
    AdaptationInput,
    AdaptationOutput,
)
from src.pipeline.errors import AgentContractError
from src.pipeline.runner import AgentStage, run_agent
from src.review.models import (
    Comment,
    CommentResponse,
    ReviewAction,
    ReviewActionResponse,
    Suggestion,
    SuggestionApproval,
    SuggestionResponse,
    SuggestionType,
)
from src.tenancy.models import Notification, TeamProfile

AWAITING = "awaiting_approvals"
APPLIED = "applied"
CANCELLED = "cancelled"


async def _profile(session: AsyncSession, team_id: UUID) -> TeamProfileSnapshot:
    row = (
        await session.execute(
            select(TeamProfile)
            .where(TeamProfile.team_id == team_id)
            .order_by(TeamProfile.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return TeamProfileSnapshot(team_id=str(team_id), version=0, data={})
    return TeamProfileSnapshot(
        team_id=str(team_id), version=row.version, data=dict(row.data or {})
    )


async def reverse_adapt_text(
    session: AsyncSession,
    *,
    text: str,
    source_team_id: UUID,
    target_team_id: UUID,
) -> str:
    """Reverse adaptation via live MistralProvider (passthrough on sqlite/tests)."""
    if settings.DATABASE_URL.startswith("sqlite") or not settings.MISTRAL_API_KEY:
        return text
    if settings.MISTRAL_KILL_SWITCH:
        return text
    provider = get_mistral_provider()
    try:
        out, _ = await run_agent(
            AgentStage.adaptation,
            AdaptationInput(
                subject_type=SubjectType.suggestion,
                subject_content=text,
                source_team_profile=await _profile(session, source_team_id),
                target_team_profile=await _profile(session, target_team_id),
                direction=AdaptationDirection.reverse,
            ),
            AdaptationOutput,
            provider=provider,
            contract_version=ADAPT_CV,
            model=settings.MISTRAL_CHAT_MODEL,
        )
        return out.body
    except (AgentContractError, ValueError, RuntimeError):
        return text


async def collapse_notification(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    kind: str,
    post_id: UUID,
    payload: dict | None = None,
) -> Notification:
    """One unread notification per (user, post, kind) — collapse duplicates."""
    existing = (
        await db.execute(
            select(Notification).where(
                Notification.org_id == org_id,
                Notification.user_id == user_id,
                Notification.kind == kind,
                Notification.read_at.is_(None),
            )
        )
    ).scalars().all()
    for n in existing:
        if (n.payload or {}).get("post_id") == str(post_id):
            n.payload = {**(n.payload or {}), **(payload or {}), "post_id": str(post_id)}  # noqa: E501
            await db.flush()
            return n
    return await create_notification(
        db,
        org_id=org_id,
        user_id=user_id,
        kind=kind,
        payload={**(payload or {}), "post_id": str(post_id)},
    )


def _sug_resp(
    s: Suggestion, *, approved_team_ids: list[str] | None = None
) -> SuggestionResponse:
    approved = list(approved_team_ids or [])
    parties = [str(s.target_team_id), str(s.proposer_team_id)]
    awaiting: list[str] = []
    if s.status == AWAITING:
        awaiting = [t for t in parties if t not in approved]
    return SuggestionResponse(
        id=str(s.id),
        post_id=str(s.post_id),
        package_id=str(s.package_id),
        proposer_team_id=str(s.proposer_team_id),
        target_team_id=str(s.target_team_id),
        original_text=s.original_text,
        adapted_preview=s.adapted_preview,
        proposed_text=s.proposed_text,
        status=s.status,
        response=s.response,
        response_reason=s.response_reason,
        target_node_id=str(s.target_node_id) if s.target_node_id else None,
        target_node_version=s.target_node_version,
        suggestion_type=(s.payload or {}).get("suggestion_type"),
        approved_team_ids=approved,
        awaiting_team_ids=awaiting,
        applied_at=s.applied_at,
        created_at=s.created_at,
    )


async def _approval_team_ids(
    db: AsyncSession, *, suggestion_id: UUID
) -> list[str]:
    rows = (
        await db.execute(
            select(SuggestionApproval.team_id).where(
                SuggestionApproval.suggestion_id == suggestion_id
            )
        )
    ).scalars().all()
    return [str(t) for t in rows]


async def _record_approval(
    db: AsyncSession,
    *,
    org_id: UUID,
    suggestion_id: UUID,
    team_id: UUID,
    user_id: UUID,
) -> None:
    existing = (
        await db.execute(
            select(SuggestionApproval).where(
                SuggestionApproval.suggestion_id == suggestion_id,
                SuggestionApproval.team_id == team_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        SuggestionApproval(
            id=uuid.uuid4(),
            org_id=org_id,
            suggestion_id=suggestion_id,
            team_id=team_id,
            user_id=user_id,
        )
    )
    await db.flush()


async def _apply_approved_change(
    db: AsyncSession,
    *,
    org_id: UUID,
    sug: Suggestion,
) -> None:
    """Apply proposed_text to the target node and enqueue rendition regen."""
    text = sug.proposed_text or sug.original_text
    if sug.target_node_id is not None:
        node = await db.get(Node, sug.target_node_id)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Node not found"
            )
        if (
            sug.target_node_version is not None
            and node.version != sug.target_node_version
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="stale_target"
            )
        node.summary = text
        node.search_text = f"{node.label} {text}"
        node.version = node.version + 1
        db.add(
            NodeHistory(
                id=uuid.uuid4(),
                node_id=node.id,
                org_id=org_id,
                team_id=sug.target_team_id,
                version=node.version,
                snapshot={"summary": text, "source_suggestion_id": str(sug.id)},
                source="suggestion",
            )
        )
        post = await db.get(Post, sug.post_id)
        if post is not None:
            post.updated_since_send = True
            await enqueue(
                db,
                JobKind.regenerate_rendition,
                {
                    "post_id": str(post.id),
                    "org_id": str(org_id),
                    "suggestion_id": str(sug.id),
                },
                dedupe_key=f"regen:{post.id}",
            )
    sug.status = APPLIED
    sug.applied_at = datetime.now(UTC)
    sug.updated_at = datetime.now(UTC)
    await db.flush()


async def create_suggestion(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    post_id: UUID,
    text: str,
    target_node_id: UUID | None,
    suggestion_type: SuggestionType | None,
) -> SuggestionResponse:
    post = await db.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    channel = await db.get(Channel, post.channel_id)
    if channel is None or team_id not in (channel.team_a_id, channel.team_b_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    pkg = await db.get(Package, post.package_id)
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")  # noqa: E501
    target_team = pkg.team_id  # sender owns the graph
    node_version = None
    if target_node_id is not None:
        node = await db.get(Node, target_node_id)
        if node is None or node.org_id != org_id or node.team_id != target_team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")  # noqa: E501
        included = {str(x) for x in (pkg.included_node_ids or [])}
        if str(target_node_id) not in included:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Suggestion target must be a package-included node",
            )
        node_version = node.version

    adapted = await reverse_adapt_text(
        db, text=text, source_team_id=team_id, target_team_id=target_team
    )
    sug = Suggestion(
        id=uuid.uuid4(),
        org_id=org_id,
        post_id=post_id,
        package_id=post.package_id,
        proposer_team_id=team_id,
        target_team_id=target_team,
        created_by=user_id,
        original_text=text,
        adapted_preview=adapted,
        target_node_id=target_node_id,
        target_node_version=node_version,
        status="open",
        payload={"suggestion_type": suggestion_type} if suggestion_type else {},
    )
    db.add(sug)
    await db.flush()
    await collapse_notification(
        db,
        org_id=org_id,
        user_id=pkg.created_by,
        kind="suggestion_received",
        post_id=post_id,
        payload={"suggestion_id": str(sug.id)},
    )
    return _sug_resp(sug)


async def list_suggestions_for_team(
    db: AsyncSession, *, org_id: UUID, team_id: UUID
) -> list[SuggestionResponse]:
    """Inbound queue for target team + outbound awaiting approvals for proposer."""
    from sqlalchemy import and_, or_

    rows = (
        await db.execute(
            select(Suggestion)
            .where(
                Suggestion.org_id == org_id,
                or_(
                    and_(
                        Suggestion.target_team_id == team_id,
                        Suggestion.status.in_(("open", AWAITING, APPLIED)),
                    ),
                    and_(
                        Suggestion.proposer_team_id == team_id,
                        Suggestion.status.in_(
                            ("open", AWAITING, APPLIED, "closed", CANCELLED)
                        ),
                    ),
                ),
            )
            .order_by(Suggestion.created_at.desc())
        )
    ).scalars().all()
    out: list[SuggestionResponse] = []
    for s in rows:
        approved = await _approval_team_ids(db, suggestion_id=s.id)
        out.append(_sug_resp(s, approved_team_ids=approved))
    return out


async def respond_suggestion(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    suggestion_id: UUID,
    response: str,
    reason: str | None,
    edited_text: str | None,
    actor_role: str,
) -> SuggestionResponse:
    """Target-team Lead responds.

    accept/edit → propose text + record target approval; apply only after both
    teams approve.
    reject → terminal rejection (no dual approve).
    """
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Lead role required"
        )
    sug = await db.get(Suggestion, suggestion_id)
    if sug is None or sug.org_id != org_id or sug.target_team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")  # noqa: E501
    if sug.status not in ("open", "responded"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_resolved")  # noqa: E501

    if response == "reject" and not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection requires a reason"  # noqa: E501
        )

    sug.response = response
    sug.response_reason = reason
    sug.responded_by = user_id
    sug.responded_at = datetime.now(UTC)
    sug.updated_at = datetime.now(UTC)

    if response == "reject":
        sug.status = "rejected"
        await db.flush()
        await collapse_notification(
            db,
            org_id=org_id,
            user_id=sug.created_by,
            kind="suggestion_response",
            post_id=sug.post_id,
            payload={"suggestion_id": str(sug.id), "response": response},
        )
        return _sug_resp(sug, approved_team_ids=[])

    # accept / edit — stage proposed text; do not apply until dual approval
    text = edited_text if response == "edit" and edited_text else sug.original_text
    if sug.target_node_id is not None:
        node = await db.get(Node, sug.target_node_id)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Node not found"
            )
        if (
            sug.target_node_version is not None
            and node.version != sug.target_node_version
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="stale_target"
            )
    sug.proposed_text = text
    sug.status = AWAITING
    await db.flush()
    await _record_approval(
        db,
        org_id=org_id,
        suggestion_id=sug.id,
        team_id=team_id,
        user_id=user_id,
    )
    await collapse_notification(
        db,
        org_id=org_id,
        user_id=sug.created_by,
        kind="suggestion_response",
        post_id=sug.post_id,
        payload={
            "suggestion_id": str(sug.id),
            "response": response,
            "status": AWAITING,
        },
    )
    approved = await _approval_team_ids(db, suggestion_id=sug.id)
    return _sug_resp(sug, approved_team_ids=approved)


async def approve_suggestion(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    suggestion_id: UUID,
) -> SuggestionResponse:
    """Either party team records approval; applies when both have approved."""
    sug = await db.get(Suggestion, suggestion_id)
    if sug is None or sug.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    if team_id not in (sug.proposer_team_id, sug.target_team_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    if sug.status != AWAITING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suggestion is not awaiting dual approval",
        )
    await _record_approval(
        db,
        org_id=org_id,
        suggestion_id=sug.id,
        team_id=team_id,
        user_id=user_id,
    )
    approved = await _approval_team_ids(db, suggestion_id=sug.id)
    needed = {str(sug.proposer_team_id), str(sug.target_team_id)}
    if needed.issubset(set(approved)):
        await _apply_approved_change(db, org_id=org_id, sug=sug)
        await collapse_notification(
            db,
            org_id=org_id,
            user_id=sug.created_by,
            kind="suggestion_applied",
            post_id=sug.post_id,
            payload={"suggestion_id": str(sug.id)},
        )
        # also notify target team lead via package creator if different
        approved = await _approval_team_ids(db, suggestion_id=sug.id)
    return _sug_resp(sug, approved_team_ids=approved)


async def cancel_suggestion(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    suggestion_id: UUID,
) -> SuggestionResponse:
    """Proposer (Team B) withdraws an edit request before it is applied."""
    sug = await db.get(Suggestion, suggestion_id)
    if sug is None or sug.org_id != org_id or sug.proposer_team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    if sug.status not in ("open", AWAITING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only cancel while open or awaiting approvals",
        )
    sug.status = CANCELLED
    sug.updated_at = datetime.now(UTC)
    await db.flush()

    pkg = await db.get(Package, sug.package_id)
    if pkg is not None:
        await collapse_notification(
            db,
            org_id=org_id,
            user_id=pkg.created_by,
            kind="suggestion_cancelled",
            post_id=sug.post_id,
            payload={"suggestion_id": str(sug.id)},
        )
    approved = await _approval_team_ids(db, suggestion_id=sug.id)
    return _sug_resp(sug, approved_team_ids=approved)


async def close_suggestion(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    suggestion_id: UUID,
) -> SuggestionResponse:
    sug = await db.get(Suggestion, suggestion_id)
    if sug is None or sug.org_id != org_id or sug.proposer_team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")  # noqa: E501
    if sug.status not in (APPLIED, "rejected", "closed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Close after the change is applied (or rejected)",
        )
    sug.closed_by_receiver = True
    sug.status = "closed"
    sug.updated_at = datetime.now(UTC)
    await db.flush()
    approved = await _approval_team_ids(db, suggestion_id=sug.id)
    return _sug_resp(sug, approved_team_ids=approved)


async def create_review_action(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    post_id: UUID,
    action: str,
    note: str | None,
) -> ReviewActionResponse:
    post = await db.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    row = ReviewAction(
        id=uuid.uuid4(),
        org_id=org_id,
        post_id=post_id,
        team_id=team_id,
        user_id=user_id,
        action=action,
        note=note,
    )
    db.add(row)
    try:
        await db.flush()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="review_action_exists"
        ) from exc
    # FR-6.4 — mark sender-team decisions contested / agreed from post review
    if action in ("agree", "request_changes", "blocked"):
        from src.channels.models import Package
        from src.conflict.models import Decision

        pkg = await db.get(Package, post.package_id)
        if pkg is not None:
            decisions = (
                await db.execute(
                    select(Decision).where(
                        Decision.org_id == org_id,
                        Decision.team_id == pkg.team_id,
                        Decision.status.in_(("open", "proposed", "contested")),
                    )
                )
            ).scalars().all()
            for d in decisions:
                if action == "agree":
                    d.status = "agreed"
                else:
                    d.status = "contested"
                if pkg.channel_id is not None and d.channel_id is None:
                    d.channel_id = pkg.channel_id
            await db.flush()
    return ReviewActionResponse(
        id=str(row.id),
        post_id=str(row.post_id),
        team_id=str(row.team_id),
        action=row.action,
        note=row.note,
        created_at=row.created_at,
    )


async def create_comment(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    post_id: UUID,
    body: str,
) -> CommentResponse:
    post = await db.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    pkg = await db.get(Package, post.package_id)
    reader_team = pkg.team_id if pkg else team_id
    adapted = await reverse_adapt_text(
        db, text=body, source_team_id=team_id, target_team_id=reader_team
    )
    comment = Comment(
        id=uuid.uuid4(),
        org_id=org_id,
        post_id=post_id,
        author_team_id=team_id,
        author_user_id=user_id,
        original_body=body,
        adapted_body=adapted,
    )
    db.add(comment)
    await db.flush()
    return CommentResponse(
        id=str(comment.id),
        post_id=str(comment.post_id),
        author_team_id=str(comment.author_team_id),
        original_body=comment.original_body,
        adapted_body=comment.adapted_body,
        created_at=comment.created_at,
    )


async def list_comments(
    db: AsyncSession, *, org_id: UUID, post_id: UUID
) -> list[CommentResponse]:
    rows = (
        await db.execute(
            select(Comment)
            .where(Comment.org_id == org_id, Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
        )
    ).scalars().all()
    return [
        CommentResponse(
            id=str(c.id),
            post_id=str(c.post_id),
            author_team_id=str(c.author_team_id),
            original_body=c.original_body,
            adapted_body=c.adapted_body,
            created_at=c.created_at,
        )
        for c in rows
    ]
