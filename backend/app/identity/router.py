"""FastAPI router untuk Identity domain — auth endpoints.

Endpoint mapping (per CLAUDE.md):
- POST /api/v1/auth/login        — NIK + password → JWT
- POST /api/v1/auth/refresh      — refresh token (TSK-002)
- POST /api/v1/auth/logout       — revoke token (TSK-005)
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.core.deps import DBSession
from app.identity import service
from app.identity.schemas import LoginRequest, LoginResponse, RolePublic, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login dengan NIK + password",
    description=(
        "Authenticate karyawan IDEA dengan NIK dan password. "
        "Returns JWT access token + user info. "
        "TSK-001: placeholder token. TSK-002: real JWT."
    ),
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
    """POST /api/v1/auth/login — NIK + password → JWT."""
    client_ip = request.client.host if request.client else None

    try:
        user = await service.authenticate(
            session,
            nik=payload.nik,
            password=payload.password,
            client_ip=client_ip,
        )
    except service.AuthenticationError as e:
        status_code = status.HTTP_403_FORBIDDEN if e.code == "ACCOUNT_INACTIVE" else status.HTTP_401_UNAUTHORIZED
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": e.message},
        ) from e

    # TSK-001: placeholder token. TSK-002 akan replace dengan JWT real.
    placeholder_token = f"placeholder-token-for-{user.nik}-replace-in-tsk-002"

    return LoginResponse(
        access_token=placeholder_token,
        token_type="bearer",
        user=UserPublic(
            id=user.id,
            nik=user.nik,
            email=user.email,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            roles=[
                RolePublic(
                    id=ur.role.id,
                    code=ur.role.code,
                    name=ur.role.name,
                    level=ur.role.level,
                )
                for ur in user.roles
            ],
        ),
    )
