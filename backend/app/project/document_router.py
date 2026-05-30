"""Project documents router — TSK-068.

Endpoints di /api/v1:
- GET    /projects/{id}/documents               — list (filter folder optional)
- GET    /projects/{id}/document-folders        — distinct folder list
- POST   /projects/{id}/documents/upload        — multipart upload + auto register
- POST   /projects/{id}/documents               — register existing object metadata
- GET    /projects/documents/{doc_id}/url       — presigned download URL
- GET    /projects/documents/{doc_id}/versions  — version history
- DELETE /projects/documents/{doc_id}           — soft delete

Member-only access: cek di service level (require_permission project.view + member check).
TODO: enforce membership at API level di TSK lanjutan.
"""

from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import DBSession, require_permission
from app.core.storage import (
    get_presigned_url,
    object_name_from_url,
    upload_fileobj,
)
from app.identity.models import User
from app.project import document_service as service
from app.project.document_schemas import (
    DocumentDownloadUrl,
    DocumentMetadataCreate,
    DocumentOut,
)
from app.project.document_service import DocumentNotFoundError

router = APIRouter(tags=["project-documents"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _doc_to_out(session, d, include_download_url: bool = False) -> DocumentOut:
    uploader_nik = None
    if d.uploaded_by_user_id:
        r = await session.execute(
            select(User.nik).where(User.id == d.uploaded_by_user_id)
        )
        uploader_nik = r.scalar_one_or_none()

    download_url = None
    if include_download_url:
        try:
            download_url = get_presigned_url(
                object_name_from_url(d.file_url), expires_in_seconds=3600
            )
        except Exception:
            download_url = None

    return DocumentOut(
        id=d.id,
        project_id=d.project_id,
        name=d.name,
        folder_path=d.folder_path,
        file_url=d.file_url,
        version=d.version,
        uploaded_by_user_id=d.uploaded_by_user_id,
        created_at=d.created_at,
        updated_at=d.updated_at,
        uploaded_by_nik=uploader_nik,
        download_url=download_url,
        file_size=None,  # MinIO stat not fetched (saves round-trip)
        content_type=None,
    )


# ─── Endpoints ─────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/documents",
    response_model=list[DocumentOut],
)
async def list_documents_endpoint(
    project_id: UUID,
    session: DBSession,
    folder_path: str | None = None,
    _user=Depends(require_permission("project.view")),
) -> list[DocumentOut]:
    docs = await service.list_documents(session, project_id, folder_path=folder_path)
    return [await _doc_to_out(session, d) for d in docs]


@router.get(
    "/projects/{project_id}/document-folders",
    response_model=list[str],
)
async def list_folders_endpoint(
    project_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[str]:
    return await service.list_folders(session, project_id)


@router.post(
    "/projects/{project_id}/documents/upload",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document_endpoint(
    request: Request,
    project_id: UUID,
    session: DBSession,
    file: UploadFile = File(...),
    name: str = Form(...),
    folder_path: str | None = Form(None),
    version: str = Form("v1.0"),
    user=Depends(require_permission("project.edit")),
) -> DocumentOut:
    """Upload file ke MinIO + register metadata di satu request."""
    content = await file.read()
    object_name = f"projects/{project_id}/documents/{name.replace(' ', '_')}-{version}"
    upload_fileobj(
        BytesIO(content),
        object_name,
        content_type=file.content_type or "application/octet-stream",
        length=len(content),
    )

    data = DocumentMetadataCreate(
        name=name,
        folder_path=folder_path,
        file_url=object_name,
        version=version,
    )
    doc = await service.register_document(session, project_id, data, user.id)

    await audit_log(
        session=session,
        actor=user,
        action="DOCUMENT_UPLOADED",
        resource_type="project_document",
        resource_id=str(doc.id),
        ip_address=request.client.host if request.client else None,
        after_state={"name": doc.name, "version": doc.version, "size": len(content)},
    )
    return await _doc_to_out(session, doc)


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def register_document_endpoint(
    request: Request,
    project_id: UUID,
    data: DocumentMetadataCreate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> DocumentOut:
    """Register metadata untuk file yang sudah di-upload manual (direct MinIO)."""
    doc = await service.register_document(session, project_id, data, user.id)
    await audit_log(
        session=session,
        actor=user,
        action="DOCUMENT_REGISTERED",
        resource_type="project_document",
        resource_id=str(doc.id),
        ip_address=request.client.host if request.client else None,
        after_state={"name": doc.name, "version": doc.version},
    )
    return await _doc_to_out(session, doc)


@router.get(
    "/projects/documents/{doc_id}/url",
    response_model=DocumentDownloadUrl,
)
async def get_download_url_endpoint(
    doc_id: UUID,
    session: DBSession,
    expires_in: int = 3600,
    _user=Depends(require_permission("project.view")),
) -> DocumentDownloadUrl:
    try:
        d = await service.get_document(session, doc_id)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    url = get_presigned_url(object_name_from_url(d.file_url), expires_in_seconds=expires_in)
    return DocumentDownloadUrl(url=url, expires_in_seconds=expires_in)


@router.get(
    "/projects/documents/{doc_id}/versions",
    response_model=list[DocumentOut],
)
async def list_versions_endpoint(
    doc_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[DocumentOut]:
    try:
        d = await service.get_document(session, doc_id)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    versions = await service.list_versions(session, d.project_id, d.name, d.folder_path)
    return [await _doc_to_out(session, v) for v in versions]


@router.delete(
    "/projects/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document_endpoint(
    request: Request,
    doc_id: UUID,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        d = await service.soft_delete_document(session, doc_id)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session,
        actor=user,
        action="DOCUMENT_DELETED",
        resource_type="project_document",
        resource_id=str(d.id),
        ip_address=request.client.host if request.client else None,
    )
