"""Pydantic schemas untuk Identity domain — request/response models."""

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


class RefreshRequest(BaseModel):
    """POST /api/v1/auth/refresh request body."""

    refresh_token: str = Field(..., description="Refresh token dari /auth/login")


class TokenPair(BaseModel):
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")


class LoginResponse(TokenPair):
    """POST /api/v1/auth/login response — token pair + user info."""

    user: "UserPublic"


class RefreshResponse(TokenPair):
    """POST /api/v1/auth/refresh response — new token pair (rotated)."""

    pass


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
