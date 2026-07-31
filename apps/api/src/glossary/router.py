"""Team glossary HTTP API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.glossary import service
from src.glossary.models import (
    GlossaryTermCreate,
    GlossaryTermResponse,
    GlossaryTermUpdate,
)
from src.lib.dependencies import DBSession, TenantScopeDep

router = APIRouter()


def _require_scope_team(scope: TenantScopeDep, team_id: UUID) -> None:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )


@router.get("/teams/{team_id}/glossary", response_model=list[GlossaryTermResponse])
async def list_glossary(
    team_id: UUID, scope: TenantScopeDep, db: DBSession
) -> list[GlossaryTermResponse]:
    _require_scope_team(scope, team_id)
    return await service.list_terms(db, org_id=scope.org_id, team_id=team_id)


@router.post(
    "/teams/{team_id}/glossary",
    response_model=GlossaryTermResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_glossary_term(
    team_id: UUID,
    body: GlossaryTermCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> GlossaryTermResponse:
    _require_scope_team(scope, team_id)
    return await service.create_term(
        db,
        org_id=scope.org_id,
        team_id=team_id,
        actor_role=scope.role,
        term=body.term,
        definition=body.definition,
        kind=body.kind,
    )


@router.patch(
    "/teams/{team_id}/glossary/{term_id}",
    response_model=GlossaryTermResponse,
)
async def update_glossary_term(
    team_id: UUID,
    term_id: UUID,
    body: GlossaryTermUpdate,
    scope: TenantScopeDep,
    db: DBSession,
) -> GlossaryTermResponse:
    _require_scope_team(scope, team_id)
    return await service.update_term(
        db,
        org_id=scope.org_id,
        team_id=team_id,
        term_id=term_id,
        actor_role=scope.role,
        term=body.term,
        definition=body.definition,
        kind=body.kind,
    )


@router.delete(
    "/teams/{team_id}/glossary/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_glossary_term(
    team_id: UUID,
    term_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> Response:
    _require_scope_team(scope, team_id)
    await service.delete_term(
        db,
        org_id=scope.org_id,
        team_id=team_id,
        term_id=term_id,
        actor_role=scope.role,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
