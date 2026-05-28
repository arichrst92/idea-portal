"""FastAPI router untuk Identity domain — auth endpoints.

Endpoint:
- POST /api/v1/auth/login            — NIK + password → JWT pair + audit
- POST /api/v1/auth/refresh          — refresh token rotation + blacklist old
- POST /api/v1/auth/logout           — revoke refresh token (TSK-005)
- GET  /api/v1/auth/me               — current user info
- GET  /api/v1/auth/me/permissions   — list user's permissions
- GET  /api/v1/auth/audit-logs       — paginated audit log query (Executive only, TSK-011)
- GET  /api/v1/auth/executive-ping   — demo Executive Portal access
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.config import get_settings
from app.core.audit import audit_log
from app.core.deps import (
    DBSession,
    get_current_user,
    require_executive,
    require_permission,
)
from app.identity import service
from app.identity.models import AuditLog, User
from app.identity.schemas import (
    AuditLogEntry,
    AuditLogPage,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
    RolePublic,
    UserPublic,
)
from app.identity import password_reset
from app.core.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _user_to_public(user: User) -> UserPublic:
    """Convert User ORM → UserPublic schema."""
    return UserPublic(
        id=user.id,
        nik=user.nik,
        email=user.email,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        roles=[
            RolePublic(id=ur.role.id, code=ur.role.code, name=ur.role.name, level=ur.role.level)
            for ur in user.roles
        ],
    )


# ─── Login / Refresh / Logout ────────────────────────────────────


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    session: DBSession,
) -> LoginResponse:
    """POST /api/v1/auth/login — NIK + password → JWT pair + audit log."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        user = await service.authenticate(
            session, nik=payload.nik, password=payload.password, client_ip=client_ip
        )
    except service.AuthenticationError as e:
        await audit_log(
            session,
            actor=None,
            action=f"LOGIN_FAILED_{e.code}",
            resource_type="auth",
            resource_id=payload.nik,
            ip_address=client_ip,
            user_agent=user_agent,
            notes=e.message,
            commit=True,
        )
        status_code = (
            status.HTTP_403_FORBIDDEN if e.code == "ACCOUNT_INACTIVE"
            else status.HTTP_401_UNAUTHORIZED
        )
        # Include lock info (TSK-006) jika account locked
        detail: dict[str, object] = {"code": e.code, "message": e.message}
        if e.locked_until is not None:
            detail["locked_until"] = e.locked_until.isoformat()
            detail["remaining_seconds"] = e.remaining_seconds
        raise HTTPException(
            status_code=status_code,
            detail=detail,
        ) from e

    await audit_log(
        session,
        actor=user,
        action="LOGIN_SUCCESS",
        resource_type="auth",
        resource_id=user.nik,
        ip_address=client_ip,
        user_agent=user_agent,
        commit=True,
    )

    access, refresh = service.issue_token_pair(user)

    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=_user_to_public(user),
    )


@router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: DBSession,
) -> RefreshResponse:
    """POST /api/v1/auth/refresh — rotate token pair (old refresh di-revoke)."""
    client_ip = request.client.host if request.client else None

    try:
        user, access, refresh_token = await service.refresh_token_pair(
            session, payload.refresh_token
        )
    except service.AuthenticationError as e:
        # Log refresh failure (anonymous if user not identifiable)
        await audit_log(
            session,
            actor=None,
            action=f"REFRESH_FAILED_{e.code}",
            resource_type="auth",
            ip_address=client_ip,
            notes=e.message,
            commit=True,
        )
        status_code = (
            status.HTTP_403_FORBIDDEN if e.code == "ACCOUNT_INACTIVE"
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": e.message},
        ) from e

    await audit_log(
        session,
        actor=user,
        action="TOKEN_REFRESHED",
        resource_type="auth",
        resource_id=user.nik,
        ip_address=client_ip,
        commit=True,
    )

    return RefreshResponse(
        access_token=access,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    payload: LogoutRequest,
    request: Request,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict[str, bool | str]:
    """POST /api/v1/auth/logout — revoke refresh token (TSK-005).

    Butuh valid access token (current user identifiable) + refresh token (yang akan di-revoke).
    """
    client_ip = request.client.host if request.client else None
    revoked = await service.logout(payload.refresh_token)

    await audit_log(
        session,
        actor=current_user,
        action="LOGOUT_SUCCESS",
        resource_type="auth",
        resource_id=current_user.nik,
        ip_address=client_ip,
        notes=f"Refresh token revoked={revoked}",
        commit=True,
    )

    return {"success": True, "revoked": revoked}


# ─── Password reset / change (TSK-007) ───────────────────────────


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset token",
    description=(
        "Generate password reset token. Selalu return 200 (tidak leak whether NIK exists). "
        "DEV mode: token di-return di response. "
        "Production (TODO PH4): token dikirim via email."
    ),
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: DBSession,
) -> ForgotPasswordResponse:
    """POST /api/v1/auth/forgot-password — generate reset token."""
    client_ip = request.client.host if request.client else None

    user = await service.get_user_by_nik(session, payload.nik)

    # Generic response — JANGAN leak whether NIK exists (anti-enumeration)
    generic_msg = (
        "Jika NIK valid, link reset password telah dibuat. "
        "Cek email Anda dalam beberapa menit."
    )

    if user is None or not user.is_active:
        # Log attempt tapi return 200 generic
        await audit_log(
            session,
            actor=None,
            action="PASSWORD_RESET_REQUESTED_INVALID_NIK",
            resource_type="auth",
            resource_id=payload.nik,
            ip_address=client_ip,
            commit=True,
        )
        return ForgotPasswordResponse(message=generic_msg)

    token, expires_at = await password_reset.issue_reset_token(user.id)

    await audit_log(
        session,
        actor=user,
        action="PASSWORD_RESET_TOKEN_ISSUED",
        resource_type="auth",
        resource_id=user.nik,
        ip_address=client_ip,
        commit=True,
    )

    # DEV mode: return token di response (untuk testing tanpa email)
    if settings.app_env == "development":
        return ForgotPasswordResponse(
            message=generic_msg + " [DEV: token disertakan di response]",
            reset_token=token,
            expires_at=expires_at,
        )

    # Production: token tidak di-return (akan dikirim via email — TODO PH4)
    return ForgotPasswordResponse(message=generic_msg)


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password dengan token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: DBSession,
) -> dict[str, bool | str]:
    """POST /api/v1/auth/reset-password — single-use token consumption."""
    client_ip = request.client.host if request.client else None

    user_id = await password_reset.consume_reset_token(payload.token)
    if user_id is None:
        await audit_log(
            session,
            actor=None,
            action="PASSWORD_RESET_FAILED_INVALID_TOKEN",
            resource_type="auth",
            ip_address=client_ip,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RESET_TOKEN", "message": "Token tidak valid atau sudah expired."},
        )

    user = await service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USER_NOT_FOUND", "message": "User tidak ditemukan."},
        )

    # Update password + reset failed attempts + unlock
    user.password_hash = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None
    await session.commit()

    await audit_log(
        session,
        actor=user,
        action="PASSWORD_RESET_SUCCESS",
        resource_type="auth",
        resource_id=user.nik,
        ip_address=client_ip,
        commit=True,
    )

    return {"success": True, "message": "Password berhasil di-reset. Silakan login dengan password baru."}


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password (authenticated)",
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict[str, bool | str]:
    """POST /api/v1/auth/change-password — user ganti password sendiri."""
    client_ip = request.client.host if request.client else None

    # Verify current password
    if not verify_password(payload.current_password, current_user.password_hash):
        await audit_log(
            session,
            actor=current_user,
            action="PASSWORD_CHANGE_FAILED_WRONG_CURRENT",
            resource_type="auth",
            resource_id=current_user.nik,
            ip_address=client_ip,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WRONG_CURRENT_PASSWORD", "message": "Password lama tidak sesuai."},
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SAME_PASSWORD", "message": "Password baru tidak boleh sama dengan password lama."},
        )

    current_user.password_hash = hash_password(payload.new_password)
    await session.commit()

    await audit_log(
        session,
        actor=current_user,
        action="PASSWORD_CHANGE_SUCCESS",
        resource_type="auth",
        resource_id=current_user.nik,
        ip_address=client_ip,
        commit=True,
    )

    return {"success": True, "message": "Password berhasil diubah."}


# ─── User info ───────────────────────────────────────────────────


@router.get("/me", response_model=UserPublic, status_code=status.HTTP_200_OK)
async def get_me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """GET /api/v1/auth/me — return info user dari JWT."""
    return _user_to_public(current_user)


@router.get("/me/permissions", status_code=status.HTTP_200_OK)
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
) -> dict[str, list[str]]:
    """GET /api/v1/auth/me/permissions — frontend pakai untuk hide/show UI."""
    return {"permissions": sorted(service.get_user_permissions(current_user))}


# ─── Audit log query (TSK-011) ───────────────────────────────────


@router.get(
    "/audit-logs",
    response_model=AuditLogPage,
    status_code=status.HTTP_200_OK,
    summary="Query audit logs (Executive only)",
    description=(
        "Paginated audit log query. Hanya Direktur Utama atau Wakil Direktur Utama. "
        "Filter: actor_nik, action, resource_type, start_date, end_date."
    ),
)
async def get_audit_logs(
    session: DBSession,
    actor_nik: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: User = Depends(
        require_permission("audit_log.view")
    ),  # GM+ punya view; Executive auto karena include all
) -> AuditLogPage:
    """GET /api/v1/auth/audit-logs — paginated query dengan filter."""
    # Build filter conditions
    conditions = []
    if actor_nik:
        conditions.append(AuditLog.actor_nik == actor_nik)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if start_date:
        conditions.append(AuditLog.timestamp >= start_date)
    if end_date:
        conditions.append(AuditLog.timestamp <= end_date)

    # Total count
    count_stmt = select(func.count()).select_from(AuditLog)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginated query
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    if conditions:
        stmt = stmt.where(*conditions)
    result = await session.execute(stmt)
    items = result.scalars().all()

    return AuditLogPage(
        items=[AuditLogEntry.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ─── Demo Executive Portal ───────────────────────────────────────


@router.get("/executive-ping", status_code=status.HTTP_200_OK)
async def executive_ping(
    current_user: User = Depends(require_executive()),
) -> dict[str, str]:
    """GET /api/v1/auth/executive-ping — demo Executive Portal access."""
    return {
        "message": "Welcome to Executive Portal",
        "persona": service.get_persona_name(current_user),
        "nik": current_user.nik,
    }
