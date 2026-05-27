"""Pydantic schemas untuk Identity domain — request/response models.

Konvensi:
- *Request    — input dari API consumer
- *Response   — output ke API consumer
- *In         — internal service input (DTO)
- *Out        — internal service output (DTO)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login request body."""

    nik: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="NIK karyawan (Nomor Induk Karyawan)",
        examples=["ADMIN-001"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Password karyawan",
    )


class LoginResponse(BaseModel):
    """POST /api/v1/auth/login response.

    Sprint 1 (TSK-001): placeholder access_token field.
    Sprint 1 (TSK-002): isi dengan real JWT.
    """

    access_token: str = Field(..., description="JWT access token (placeholder di TSK-001)")
    token_type: str = Field(default="bearer", description="Token type — always 'bearer'")
    user: "UserPublic"


class UserPublic(BaseModel):
    """User info yang aman dikirim ke client (TANPA password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nik: str
    email: str | None
    is_active: bool
    last_login_at: datetime | None
    roles: list["RolePublic"] = []


class RolePublic(BaseModel):
    """Role info untuk display."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    level: int


# Resolve forward references
LoginResponse.model_rebuild()
UserPublic.model_rebuild()
