"""Project document business logic — TSK-068.

Workflow:
1. Upload file (multipart) → MinIO → returns object_name.
2. Register document metadata via DocumentMetadataCreate (auto-increment version
   kalau name+folder_path sudah ada).
3. List documents per project (members + executive only di router level).
4. Get presigned URL untuk download.
5. Soft delete (set deleted_at).

Versioning strategy: latest minor bump. Kalau ada document dengan name+folder
yang sama, version baru = max(version)+0.1. User bisa override version manual.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import delete_object, object_name_from_url
from app.project.document_schemas import DocumentMetadataCreate
from app.project.models import ProjectDocument


class DocumentNotFoundError(Exception):
    pass


async def list_documents(
    session: AsyncSession,
    project_id: UUID,
    folder_path: str | None = None,
) -> list[ProjectDocument]:
    stmt = select(ProjectDocument).where(
        ProjectDocument.project_id == project_id,
        ProjectDocument.deleted_at.is_(None),
    )
    if folder_path is not None:
        stmt = stmt.where(ProjectDocument.folder_path == folder_path)
    stmt = stmt.order_by(ProjectDocument.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_document(session: AsyncSession, doc_id: UUID) -> ProjectDocument:
    stmt = select(ProjectDocument).where(
        ProjectDocument.id == doc_id, ProjectDocument.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    d = result.scalar_one_or_none()
    if d is None:
        raise DocumentNotFoundError(f"Document {doc_id} not found")
    return d


async def list_versions(
    session: AsyncSession,
    project_id: UUID,
    name: str,
    folder_path: str | None,
) -> list[ProjectDocument]:
    """All versions (including soft-deleted) for a given name+folder."""
    stmt = select(ProjectDocument).where(
        ProjectDocument.project_id == project_id,
        ProjectDocument.name == name,
    )
    if folder_path is None:
        stmt = stmt.where(ProjectDocument.folder_path.is_(None))
    else:
        stmt = stmt.where(ProjectDocument.folder_path == folder_path)
    stmt = stmt.order_by(ProjectDocument.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _parse_version(v: str) -> tuple[int, int]:
    """Parse 'v1.2' → (1, 2). Falls back to (0, 0)."""
    s = v.lstrip("vV ")
    try:
        parts = s.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return major, minor
    except (ValueError, IndexError):
        return 0, 0


def _bump_version(prev: str) -> str:
    major, minor = _parse_version(prev)
    return f"v{major}.{minor + 1}"


async def register_document(
    session: AsyncSession,
    project_id: UUID,
    data: DocumentMetadataCreate,
    uploaded_by_user_id: UUID | None,
) -> ProjectDocument:
    """Register doc setelah file di-upload ke MinIO.

    Kalau ada version sebelumnya untuk (project, name, folder), version
    di-bump otomatis kecuali user override.
    """
    user_version = data.version

    existing = await list_versions(session, project_id, data.name, data.folder_path)
    if existing and user_version == "v1.0":
        # Bump dari latest
        latest = existing[0]
        user_version = _bump_version(latest.version)

    doc = ProjectDocument(
        project_id=project_id,
        name=data.name,
        folder_path=data.folder_path,
        file_url=data.file_url,
        version=user_version,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def soft_delete_document(session: AsyncSession, doc_id: UUID) -> ProjectDocument:
    """Soft delete + optionally cleanup MinIO object (best-effort)."""
    doc = await get_document(session, doc_id)
    doc.deleted_at = datetime.now(UTC)
    await session.commit()
    # Best-effort MinIO cleanup (kalau file_url berformat object_name)
    try:
        delete_object(object_name_from_url(doc.file_url))
    except Exception:
        pass
    return doc


async def list_folders(session: AsyncSession, project_id: UUID) -> list[str]:
    """Distinct folder_path list untuk navigation tree."""
    stmt = (
        select(ProjectDocument.folder_path)
        .where(
            ProjectDocument.project_id == project_id,
            ProjectDocument.deleted_at.is_(None),
            ProjectDocument.folder_path.is_not(None),
        )
        .distinct()
    )
    result = await session.execute(stmt)
    return [r[0] for r in result.all() if r[0]]
