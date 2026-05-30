"""Pydantic schemas — project document (TSK-068)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
FolderPath = Annotated[str, StringConstraints(max_length=500, strip_whitespace=True)]


class DocumentMetadataCreate(BaseModel):
    """Used after multipart upload — links file_url to project."""

    name: Name
    folder_path: FolderPath | None = None
    file_url: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    version: Annotated[str, StringConstraints(min_length=1, max_length=20)] = "v1.0"


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    folder_path: str | None
    file_url: str  # object_name di MinIO
    version: str
    uploaded_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    # Derived
    uploaded_by_nik: str | None = None
    download_url: str | None = None  # presigned (short-lived)
    file_size: int | None = None
    content_type: str | None = None


class DocumentDownloadUrl(BaseModel):
    """Returned by GET /documents/{id}/url — presigned URL."""

    url: str
    expires_in_seconds: int
