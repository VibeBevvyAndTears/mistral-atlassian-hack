"""Review HTTP API (M5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.lib.dependencies import DBSession, TenantScopeDep
from src.review import service as review_service
from src.review.models import (
    CommentCreate,
    CommentResponse,
    ReviewActionCreate,
    ReviewActionResponse,
    SuggestionCreate,
    SuggestionRespond,
    SuggestionResponse,
)

router = APIRouter()


@router.get("/teams/{team_id}/suggestions", response_model=list[SuggestionResponse])
async def list_suggestions(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[SuggestionResponse]:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await review_service.list_suggestions_for_team(
        db, org_id=scope.org_id, team_id=team_id
    )


@router.post(
    "/posts/{post_id}/suggestions",
    response_model=SuggestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_suggestion(
    post_id: UUID,
    body: SuggestionCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> SuggestionResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    node_id = UUID(body.target_node_id) if body.target_node_id else None
    return await review_service.create_suggestion(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
        post_id=post_id,
        text=body.text,
        target_node_id=node_id,
        suggestion_type=body.suggestion_type,
    )


@router.post("/suggestions/{suggestion_id}/respond", response_model=SuggestionResponse)
async def respond_suggestion(
    suggestion_id: UUID,
    body: SuggestionRespond,
    scope: TenantScopeDep,
    db: DBSession,
) -> SuggestionResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")  # noqa: E501
    return await review_service.respond_suggestion(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
        suggestion_id=suggestion_id,
        response=body.response,
        reason=body.reason,
        edited_text=body.edited_text,
        actor_role=scope.role,
    )


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
async def approve_suggestion(
    suggestion_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> SuggestionResponse:
    """Record this team's approval; applies when both teams have approved."""
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    return await review_service.approve_suggestion(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
        suggestion_id=suggestion_id,
    )


@router.post("/suggestions/{suggestion_id}/cancel", response_model=SuggestionResponse)
async def cancel_suggestion(
    suggestion_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> SuggestionResponse:
    """Proposer withdraws the edit request (open or awaiting approvals only)."""
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    return await review_service.cancel_suggestion(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        suggestion_id=suggestion_id,
    )


@router.post("/suggestions/{suggestion_id}/close", response_model=SuggestionResponse)
async def close_suggestion(
    suggestion_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> SuggestionResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")  # noqa: E501
    return await review_service.close_suggestion(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        suggestion_id=suggestion_id,
    )


@router.post(
    "/posts/{post_id}/review-actions",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review_action(
    post_id: UUID,
    body: ReviewActionCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> ReviewActionResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    return await review_service.create_review_action(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
        post_id=post_id,
        action=body.action,
        note=body.note,
    )


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    post_id: UUID,
    body: CommentCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> CommentResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")  # noqa: E501
    return await review_service.create_comment(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
        post_id=post_id,
        body=body.body,
    )


@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    post_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[CommentResponse]:
    return await review_service.list_comments(
        db, org_id=scope.org_id, post_id=post_id
    )
