"""Pydantic schemas untuk Identity domain — request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login request body."""

    nik: str = Field(..., min_length=3, max_length=30, examples=["ADMIN-001"])
    password: str = Field(..., min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    """POST /api/v1/auth/refresh request body."""

    refresh_token: str = Field(..., description="Refresh token dari /auth/login")


class LogoutRequest(BaseModel):
    """POST /api/v1/auth/logout request body."""

    refresh_token: str = Field(..., description="Refresh token yang akan di-revoke")


class TokenPair(BaseModel):
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")


class LoginResponse(TokenPair):
    """POST /api/v1/auth/login response."""

    user: "UserPublic"


class RefreshResponse(TokenPair):
    """POST /api/v1/auth/refresh response."""

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


# ─── Audit log query schemas (TSK-011) ───────────────────────────


class AuditLogEntry(BaseModel):
    """Single audit log row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timestamp: datetime
    actor_user_id: UUID | None
    actor_nik: str | None
    actor_persona: str
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    notes: str | None


class AuditLogQuery(BaseModel):
    """GET /api/v1/auth/audit-logs query params."""

    actor_nik: str | None = Field(default=None, description="Filter by NIK")
    action: str | None = Field(default=None, description="Filter by action code")
    resource_type: str | None = Field(default=None, description="Filter by resource type")
    start_date: datetime | None = Field(default=None, description="Min timestamp")
    end_date: datetime | None = Field(default=None, description="Max timestamp")
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AuditLogPage(BaseModel):
    """Paginated audit log response."""

    items: list[AuditLogEntry]
    total: int
    limit: int
    offset: int


# Resolve forward references
LoginResponse.model_rebuild()
UserPublic.model_rebuild()
