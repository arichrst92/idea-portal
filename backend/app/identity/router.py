"""FastAPI router untuk Identity domain — auth endpoints.

Endpoint:
- POST /api/v1/auth/login        — NIK + password → JWT pair + audit
- POST /api/v1/auth/refresh      — refresh token rotation
- GET  /api/v1/auth/me           — current user info (protected)
- GET  /api/v1/auth/me/permissions — list permissions yang dimiliki user
- GET  /api/v1/auth/executive-ping — demo Executive Portal access (DIREKTUR_UTAMA or WAKIL only)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import get_settings
from app.core.audit import audit_log
from app.core.deps import DBSession, get_current_user, require_executive
from app.identity import service
from app.identity.models import User
from app.identity.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RolePublic,
    UserPublic,
)

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


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login dengan NIK + password",
    responses={
        401: {"description": "Invalid credentials atau account locked"},
        403: {"description": "Account inactive"},
    },
)
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
            session,
            nik=payload.nik,
            password=payload.password,
            client_ip=client_ip,
        )
    except service.AuthenticationError as e:
        # Log failed login (anonymous actor)
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
            status.HTTP_403_FORBIDDEN
            if e.code == "ACCOUNT_INACTIVE"
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": e.message},
        ) from e

    # Audit success
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


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token via refresh token",
    responses={
        401: {"description": "Refresh token invalid/expired"},
        403: {"description": "User inactive"},
    },
)
async def refresh(
    payload: RefreshRequest,
    session: DBSession,
) -> RefreshResponse:
    """POST /api/v1/auth/refresh — rotate token pair."""
    try:
        _, access, refresh_token = await service.refresh_token_pair(
            session, payload.refresh_token
        )
    except service.AuthenticationError as e:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if e.code == "ACCOUNT_INACTIVE"
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": e.message},
        ) from e

    return RefreshResponse(
        access_token=access,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
    summary="Get current user info dari JWT",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """GET /api/v1/auth/me — return info user dari JWT."""
    return _user_to_public(current_user)


@router.get(
    "/me/permissions",
    status_code=status.HTTP_200_OK,
    summary="List permissions yang dimiliki current user",
)
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
) -> dict[str, list[str]]:
    """GET /api/v1/auth/me/permissions — frontend bisa pakai untuk hide/show UI."""
    return {"permissions": sorted(service.get_user_permissions(current_user))}


@router.get(
    "/executive-ping",
    status_code=status.HTTP_200_OK,
    summary="Demo Executive Portal — Direktur Utama atau Wakil only",
    description=(
        "Demo endpoint untuk verify Executive Portal RBAC. "
        "Hanya Direktur Utama atau Wakil Direktur Utama yang bisa akses. "
        "Response include persona name eksplisit (NC-EX-005)."
    ),
    responses={403: {"description": "Bukan Direktur Utama / Wakil"}},
)
async def executive_ping(
    current_user: User = Depends(require_executive()),
) -> dict[str, str]:
    """GET /api/v1/auth/executive-ping — demo Executive Portal access."""
    return {
        "message": "Welcome to Executive Portal",
        "persona": service.get_persona_name(current_user),
        "nik": current_user.nik,
    }
