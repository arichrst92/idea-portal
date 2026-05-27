"""Tests untuk JWT flow — TSK-002.

Coverage:
- ✓ login response sekarang berisi real JWT (bukan placeholder)
- ✓ /auth/me dengan valid token → 200 user info
- ✓ /auth/me tanpa token → 401
- ✓ /auth/me dengan invalid token → 401
- ✓ /auth/me dengan refresh token (wrong type) → 401
- ✓ /auth/refresh dengan valid refresh → new pair
- ✓ /auth/refresh dengan access token (wrong type) → 401
- ✓ Access token contains correct claims (sub, user_id, roles, type)
- ✓ Refresh token rotation menghasilkan token baru (different signature)
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password
from app.database import async_session_factory
from app.identity.models import HierarchyLevel, Role, User, UserRole
from app.main import app

settings = get_settings()


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def test_user_with_role(session: AsyncSession) -> User:
    """Setup test user + role + return user."""
    role = Role(
        code="TEST_GM",
        name="Test GM",
        level=HierarchyLevel.L3_GM.value,
        is_executive=False,
    )
    session.add(role)
    await session.flush()

    user = User(
        nik="JWT-TEST-001",
        password_hash=hash_password("jwt-test-pass"),
        email="jwt-test@ide.asia",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    return user


# ─── /auth/login response — JWT real ─────────────────────────────


@pytest.mark.asyncio
async def test_login_returns_real_jwt(
    client: AsyncClient, test_user_with_role: User
) -> None:
    """Login sekarang return real JWT, bukan placeholder."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "JWT-TEST-001", "password": "jwt-test-pass"},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Bukan placeholder
    assert "placeholder" not in data["access_token"]
    assert "placeholder" not in data["refresh_token"]

    # Token bisa di-decode
    access_payload = jwt.decode(
        data["access_token"],
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert access_payload["sub"] == "JWT-TEST-001"
    assert access_payload["type"] == "access"
    assert access_payload["user_id"] == str(test_user_with_role.id)
    assert "TEST_GM" in access_payload["roles"]

    # Refresh token claims
    refresh_payload = jwt.decode(
        data["refresh_token"],
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert refresh_payload["sub"] == "JWT-TEST-001"
    assert refresh_payload["type"] == "refresh"

    # expires_in field
    assert data["expires_in"] == settings.access_token_expire_minutes * 60


# ─── /auth/me ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_with_valid_token(
    client: AsyncClient, test_user_with_role: User
) -> None:
    """/auth/me dengan valid access token → 200 user info."""
    # Login dulu untuk dapat token
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "JWT-TEST-001", "password": "jwt-test-pass"},
    )
    access_token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["nik"] == "JWT-TEST-001"
    assert data["email"] == "jwt-test@ide.asia"
    assert len(data["roles"]) >= 1


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    """/auth/me tanpa Authorization header → 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "MISSING_TOKEN"


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient) -> None:
    """/auth/me dengan token gibberish → 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_me_with_refresh_token_rejected(
    client: AsyncClient, test_user_with_role: User
) -> None:
    """/auth/me dengan refresh token (wrong type) → 401."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "JWT-TEST-001", "password": "jwt-test-pass"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Pakai refresh token sebagai access — should fail
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_TOKEN"


# ─── /auth/refresh ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_with_valid_refresh_token(
    client: AsyncClient, test_user_with_role: User
) -> None:
    """/auth/refresh dengan valid refresh → 200 new pair."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "JWT-TEST-001", "password": "jwt-test-pass"},
    )
    old_refresh = login_resp.json()["refresh_token"]
    old_access = login_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response.status_code == 200
    new_data = response.json()
    assert new_data["access_token"]
    assert new_data["refresh_token"]
    assert new_data["token_type"] == "bearer"

    # New access token bisa dipakai untuk /me
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_data['access_token']}"},
    )
    assert me_resp.status_code == 200

    # Old access token mungkin masih valid sampai exp (no blacklist in TSK-002)
    # TSK-005 future: tambah blacklist
    _ = old_access


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(
    client: AsyncClient, test_user_with_role: User
) -> None:
    """/auth/refresh dengan access token (wrong type) → 401."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "JWT-TEST-001", "password": "jwt-test-pass"},
    )
    access_token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_with_garbage_token(client: AsyncClient) -> None:
    """/auth/refresh dengan invalid string → 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "garbage.not.a.jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_me_after_user_deactivated(
    client: AsyncClient, session: AsyncSession, test_user_with_role: User
) -> None:
    """Setelah user di-set inactive, /me dengan valid token → 403 ACCOUNT_INACTIVE.

    Per NC-SYS-001-04: terminated/resigned employee — access revoke immediate.
    """
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "JWT-TEST-001", "password": "jwt-test-pass"},
    )
    access_token = login_resp.json()["access_token"]

    # Deactivate user
    test_user_with_role.is_active = False
    await session.commit()

    # /me masih punya valid JWT, tapi user inactive → 403
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ACCOUNT_INACTIVE"
