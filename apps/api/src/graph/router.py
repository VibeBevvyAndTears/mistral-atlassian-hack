"""Graph HTTP router (M2-7)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.graph import service as graph_service
from src.graph.models import NodeDiffResponse, NodeHistoryResponse, NodeResponse
from src.lib.dependencies import DBSession, TenantScopeDep

router = APIRouter()


@router.get("/teams/{team_id}/nodes", response_model=list[NodeResponse])
async def list_team_nodes(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[NodeResponse]:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await graph_service.list_nodes(db, org_id=scope.org_id, team_id=team_id)


@router.get("/nodes/{node_id}/history", response_model=list[NodeHistoryResponse])
async def get_node_history(
    node_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[NodeHistoryResponse]:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Node not found"
        )
    history = await graph_service.list_node_history(
        db, org_id=scope.org_id, team_id=scope.team_id, node_id=node_id
    )
    if not history:
        # Distinguish missing vs empty: if node not in tenant → 404
        from src.graph.models import Node

        node = await db.get(Node, node_id)
        if node is None or node.org_id != scope.org_id or node.team_id != scope.team_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Node not found"
            )
    return history


@router.get("/nodes/{node_id}/diff", response_model=NodeDiffResponse)
async def get_node_diff(
    node_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
) -> NodeDiffResponse:
    if scope.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Node not found"
        )
    if to_version != from_version + 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Versions must be consecutive",
        )
    result = await graph_service.get_node_diff(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        node_id=node_id,
        from_version=from_version,
        to_version=to_version,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node history versions not found",
        )
    return result
