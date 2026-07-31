"""Channels / packages / posts HTTP API (M4)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.channels import service as channels_service
from src.channels.models import (
    ChannelResponse,
    PackageCreate,
    PackageResponse,
    PackageSendBody,
    PostHistoryEntry,
    PostResponse,
    PostSourcesResponse,
)
from src.lib.dependencies import DBSession, TenantScopeDep

router = APIRouter()


class EnsureChannelBody(BaseModel):
    team_a_id: str = Field(min_length=1)
    team_b_id: str = Field(min_length=1)


@router.post(
    "/orgs/{org_id}/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ensure_channel(
    org_id: UUID,
    body: EnsureChannelBody,
    scope: TenantScopeDep,
    db: DBSession,
) -> ChannelResponse:
    if scope.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Org not found"
        )
    channel = await channels_service.get_or_create_channel(
        db,
        org_id=org_id,
        team_a=UUID(body.team_a_id),
        team_b=UUID(body.team_b_id),
    )
    return channels_service.channel_response(channel)


@router.get("/teams/{team_id}/channels", response_model=list[ChannelResponse])
async def list_team_channels(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[ChannelResponse]:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await channels_service.list_team_channels(
        db, org_id=scope.org_id, team_id=team_id
    )


@router.post(
    "/teams/{team_id}/packages",
    response_model=PackageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_package(
    team_id: UUID,
    body: PackageCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> PackageResponse:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await channels_service.create_package(
        db,
        org_id=scope.org_id,
        team_id=team_id,
        user_id=scope.user_id,
        title=body.title,
        body=body.body,
        target_team_id=UUID(body.target_team_id),
        bypass_incomplete=body.bypass_incomplete_pipeline,
        included_node_ids=[UUID(x) for x in body.included_node_ids],
    )


@router.get("/packages/{package_id}", response_model=PackageResponse)
async def get_package(
    package_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> PackageResponse:
    return await channels_service.get_package(
        db, org_id=scope.org_id, package_id=package_id, team_id=scope.team_id
    )


@router.post("/packages/{package_id}/send", response_model=PackageResponse)
async def send_package(
    package_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
    body: PackageSendBody | None = None,
) -> PackageResponse:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )
    ack = bool(body.acknowledge_conflicts) if body is not None else False
    return await channels_service.enqueue_send(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        package_id=package_id,
        actor_role=scope.role,
        acknowledge_conflicts=ack,
    )


@router.get("/channels/{channel_id}/posts", response_model=list[PostResponse])
async def list_posts(
    channel_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
    sort: Literal["priority", "newest", "oldest"] = "newest",
    unread_only: bool = False,
    topic_tags: str | None = Query(default=None),
) -> list[PostResponse]:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )
    return await channels_service.list_channel_posts(
        db,
        org_id=scope.org_id,
        channel_id=channel_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
        sort=sort,
        unread_only=unread_only,
        topic_tags=[tag.strip() for tag in topic_tags.split(",") if tag.strip()]
        if topic_tags
        else [],
    )


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> PostResponse:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return await channels_service.get_post(
        db,
        org_id=scope.org_id,
        post_id=post_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
    )


@router.get("/posts/{post_id}/history", response_model=list[PostHistoryEntry])
async def list_post_history(
    post_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[PostHistoryEntry]:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return await channels_service.list_post_history(
        db,
        org_id=scope.org_id,
        post_id=post_id,
        team_id=scope.team_id,
    )


@router.get("/posts/{post_id}/sources", response_model=PostSourcesResponse)
async def list_post_sources(
    post_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> PostSourcesResponse:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return await channels_service.list_post_sources(
        db,
        org_id=scope.org_id,
        post_id=post_id,
        team_id=scope.team_id,
    )


@router.post("/posts/{post_id}/read", response_model=PostResponse)
async def mark_post_read(
    post_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> PostResponse:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return await channels_service.mark_post_read(
        db,
        org_id=scope.org_id,
        post_id=post_id,
        team_id=scope.team_id,
        user_id=scope.user_id,
    )
