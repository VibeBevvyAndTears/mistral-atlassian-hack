"""Document upload + ingest enqueue (M1-6)."""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.jobs.queue import JobKind, enqueue
from src.lib.storage.base import StorageProvider
from src.notifications.service import create_notification
from src.tenancy.models import DocumentResponse, SourceDocument, Team


class PasteDocumentBody(BaseModel):
    text: str = Field(min_length=1)
    filename: str = Field(default="paste.txt", min_length=1, max_length=255)


async def _enqueue_document(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    user_id: UUID,
    data: bytes,
    filename: str,
    content_type: str | None,
    storage: StorageProvider | None,
) -> DocumentResponse:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file — upload rejected",
        )
    doc_id = uuid.uuid4()
    storage_uri: str | None = None

    from src.lib.storage.factory import get_storage_provider

    provider = storage or get_storage_provider()
    key = f"{org_id}/{team_id}/{doc_id}/{filename}"
    try:
        storage_uri = await provider.upload(
            "documents", key, data, content_type=content_type
        )
    except Exception:
        storage_uri = f"local://documents/{key}"
        try:
            from src.lib.storage.local import LocalStorageProvider

            await LocalStorageProvider().upload("documents", key, data, content_type)
            storage_uri = f"local://documents/{key}"
        except Exception:  # noqa: S110
            pass
    job_id = await enqueue(
        db,
        JobKind.ingest_document,
        {
            "document_id": str(doc_id),
            "team_id": str(team_id),
            "org_id": str(org_id),
        },
        dedupe_key=f"ingest:{doc_id}",
    )

    doc = SourceDocument(
        id=doc_id,
        org_id=org_id,
        team_id=team_id,
        filename=filename,
        storage_uri=storage_uri,
        content_type=content_type,
        status="queued",
        job_id=job_id,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    await create_notification(
        db,
        org_id=org_id,
        user_id=user_id,
        kind="document_uploaded",
        payload={
            "document_id": str(doc_id),
            "team_id": str(team_id),
            "filename": filename,
            "job_id": str(job_id),
            "status": "queued",
        },
    )
    return DocumentResponse(
        id=str(doc.id),
        team_id=str(doc.team_id),
        org_id=str(doc.org_id),
        filename=doc.filename,
        status=doc.status,
        storage_uri=doc.storage_uri,
        job_id=str(doc.job_id) if doc.job_id else None,
        created_at=doc.created_at,
    )


async def upload_document(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    user_id: UUID,
    file: UploadFile,
    storage: StorageProvider | None,
) -> DocumentResponse:
    data = await file.read()
    filename = file.filename or "upload.bin"
    return await _enqueue_document(
        db,
        team_id=team_id,
        org_id=org_id,
        user_id=user_id,
        data=data,
        filename=filename,
        content_type=file.content_type,
        storage=storage,
    )


async def paste_document(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    user_id: UUID,
    text: str,
    filename: str = "paste.txt",
    storage: StorageProvider | None,
) -> DocumentResponse:
    data = text.encode("utf-8")
    safe_name = filename if filename.lower().endswith(".txt") else f"{filename}.txt"
    return await _enqueue_document(
        db,
        team_id=team_id,
        org_id=org_id,
        user_id=user_id,
        data=data,
        filename=safe_name,
        content_type="text/plain",
        storage=storage,
    )


async def get_document(
    db: AsyncSession,
    *,
    document_id: UUID,
    org_id: UUID,
    team_id: UUID | None,
) -> DocumentResponse:
    doc = await db.get(SourceDocument, document_id)
    if doc is None or doc.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")  # noqa: E501
    if team_id is not None and doc.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")  # noqa: E501
    return DocumentResponse(
        id=str(doc.id),
        team_id=str(doc.team_id),
        org_id=str(doc.org_id),
        filename=doc.filename,
        status=doc.status,
        storage_uri=doc.storage_uri,
        job_id=str(doc.job_id) if doc.job_id else None,
        created_at=doc.created_at,
    )
