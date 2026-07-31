"""Documents HTTP router (M1-6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.documents import service as documents_service
from src.documents.service import PasteDocumentBody
from src.lib.dependencies import DBSession, Storage, TenantScopeDep
from src.tenancy.models import DocumentResponse

router = APIRouter()


@router.post(
    "/teams/{team_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
    storage: Storage,
    file: UploadFile = File(...),
) -> DocumentResponse:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await documents_service.upload_document(
        db,
        team_id=team_id,
        org_id=scope.org_id,
        user_id=scope.user_id,
        file=file,
        storage=storage,
    )


@router.post(
    "/teams/{team_id}/documents/paste",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def paste_document(
    team_id: UUID,
    body: PasteDocumentBody,
    scope: TenantScopeDep,
    db: DBSession,
    storage: Storage,
) -> DocumentResponse:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await documents_service.paste_document(
        db,
        team_id=team_id,
        org_id=scope.org_id,
        user_id=scope.user_id,
        text=body.text,
        filename=body.filename,
        storage=storage,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> DocumentResponse:
    return await documents_service.get_document(
        db,
        document_id=document_id,
        org_id=scope.org_id,
        team_id=scope.team_id,
    )
