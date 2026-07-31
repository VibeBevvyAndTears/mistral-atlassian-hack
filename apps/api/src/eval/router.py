"""Organization-scoped evaluation HTTP API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.eval import service
from src.eval.models import (
    EvalRunResponse,
    GoldenExampleCreate,
    GoldenExampleResponse,
    GoldenExampleUpdate,
    HumanOverrideRequest,
)
from src.lib.dependencies import DBSession, TenantScopeDep

router = APIRouter()


def _authorize_org(org_id: UUID, scope: TenantScopeDep, *, write: bool = False) -> None:
    if scope.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    if write:
        scope.require_role("owner", "lead")


@router.get("/orgs/{org_id}/eval/goldens", response_model=list[GoldenExampleResponse])
async def list_goldens(
    org_id: UUID, scope: TenantScopeDep, db: DBSession
) -> list[GoldenExampleResponse]:
    _authorize_org(org_id, scope)
    return await service.list_goldens(db, org_id)


@router.post(
    "/orgs/{org_id}/eval/goldens",
    response_model=GoldenExampleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_golden(
    org_id: UUID,
    body: GoldenExampleCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> GoldenExampleResponse:
    _authorize_org(org_id, scope, write=True)
    return await service.create_golden(db, org_id, body)


@router.patch(
    "/orgs/{org_id}/eval/goldens/{golden_id}",
    response_model=GoldenExampleResponse,
)
async def update_golden(
    org_id: UUID,
    golden_id: UUID,
    body: GoldenExampleUpdate,
    scope: TenantScopeDep,
    db: DBSession,
) -> GoldenExampleResponse:
    _authorize_org(org_id, scope, write=True)
    return await service.update_golden(db, org_id, golden_id, body)


@router.delete(
    "/orgs/{org_id}/eval/goldens/{golden_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_golden(
    org_id: UUID,
    golden_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> Response:
    _authorize_org(org_id, scope, write=True)
    await service.delete_golden(db, org_id, golden_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/orgs/{org_id}/eval/run", response_model=EvalRunResponse)
async def run_regression(
    org_id: UUID, scope: TenantScopeDep, db: DBSession
) -> EvalRunResponse:
    _authorize_org(org_id, scope, write=True)
    return await service.run_regression(db, org_id)


@router.post(
    "/orgs/{org_id}/eval/goldens/{golden_id}/override",
    response_model=GoldenExampleResponse,
)
async def override_golden(
    org_id: UUID,
    golden_id: UUID,
    body: HumanOverrideRequest,
    scope: TenantScopeDep,
    db: DBSession,
) -> GoldenExampleResponse:
    _authorize_org(org_id, scope, write=True)
    return await service.override_golden(db, org_id, golden_id, body.human_override)


@router.post("/orgs/{org_id}/eval/verdicts/{verdict_id}/override")
async def override_verdict(
    org_id: UUID,
    verdict_id: UUID,
    body: HumanOverrideRequest,
    scope: TenantScopeDep,
    db: DBSession,
) -> dict[str, Any]:
    _authorize_org(org_id, scope, write=True)
    return await service.override_verdict(db, org_id, verdict_id, body.human_override)
