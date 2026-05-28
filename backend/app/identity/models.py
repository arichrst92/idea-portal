"""Identity & Auth domain — 4 tabel per ERD knowledge.md sec.20.

Tabel:
- users               — karyawan dengan login credentials (NIK + password)
- user_roles          — link table user → role (multi-role support)
- role_permissions    — link role → permission grant
- audit_logs          — semua aksi sensitif (per NC-EX-005 wajib persona explicit)

Aturan kunci (knowledge.md):
- Login pakai NIK (sec.1)
- Wakil Direktur Utama = role TERPISAH dari Direktur Utama (sec.2 + US-EX-005)
- Audit log wajib record persona name eksplisit (NC-EX-005 critical)
- 6 hierarchy levels (sec.2)
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.organization.models import Employee


class HierarchyLevel(int, enum.Enum):
    """6-level hierarchy per knowledge.md sec.2.

    L1 dan L1B punya permission identik tapi role berbeda untuk audit clarity.
    """

    L1_DIREKTUR_UTAMA = 1
    L1B_WAKIL_DIREKTUR_UTAMA = 11  # 11 = special encoding untuk Wakil (same level, beda persona)
    L2_C_LEVEL = 2
    L3_GM = 3
    L4_MANAGER = 4
    L5_LEAD = 5
    L6_STAFF = 6


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Role yang bisa di-assign ke user. Mapped ke HierarchyLevel + dept (optional)."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_executive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    permissions: Mapped[list[Permission]] = relationship(
        secondary="role_permissions", back_populates="roles", lazy="selectin"
    )
    users: Mapped[list[UserRole]] = relationship(back_populates="role")


class Permission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Granular permission (action × resource). RBAC enforce di API level."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    roles: Mapped[list[Role]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )


class RolePermission(Base, TimestampMixin):
    """Link table role ↔ permission (many-to-many)."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """User login record. NIK = login identifier (bukan email — knowledge.md sec.1)."""

    __tablename__ = "users"

    # NIK = primary business identifier, unique + indexed for fast lookup
    nik: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Email untuk profil, BUKAN untuk login (per knowledge.md gap #1 resolved)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Last login tracking
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 = 45 chars

    # Relationships
    # foreign_keys eksplisit karena user_roles punya 2 FK ke users.id
    # (user_id = PK, assigned_by_user_id = audit). Tanpa ini SQLAlchemy ambiguous.
    roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        foreign_keys="UserRole.user_id",
        lazy="selectin",
    )
    employee: Mapped[Employee | None] = relationship(back_populates="user", uselist=False)

    __table_args__ = (
        Index("ix_users_nik_active", "nik", "is_active"),
    )


class UserRole(Base, TimestampMixin):
    """Link table user ↔ role + audit trail (siapa assign, kapan)."""

    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[User] = relationship(
        back_populates="roles", foreign_keys=[user_id]
    )
    role: Mapped[Role] = relationship(back_populates="users")


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """Audit trail untuk semua aksi sensitif.

    Per NC-EX-005: WAJIB record persona name eksplisit (Direktur Utama / Wakil Direktur Utama),
    bukan generic 'Direktur'. CI test akan verify ini.
    """

    __tablename__ = "audit_logs"

    # Timestamp (immutable, no updated_at)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Actor (siapa yang melakukan aksi)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_nik: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    # PERSONA NAME — eksplisit "Rudi Atmadja (Direktur Utama)" bukan "Direktur"
    actor_persona: Mapped[str] = mapped_column(String(200), nullable=False)

    # Action
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Before/after state for changes (JSONB for flexible querying)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_audit_actor_timestamp", "actor_nik", "timestamp"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )
