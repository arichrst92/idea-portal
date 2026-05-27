"""Tests untuk /api/v1/auth/login — TSK-001.

Coverage:
- ✓ login success (happy path)
- ✓ login invalid NIK (404 user / generic 401)
- ✓ login invalid password (401)
- ✓ login inactive account (403)
- ✓ login validation: empty NIK / password (422)

Sprint 1 (TSK-002): tests untuk JWT generation + refresh token.
Sprint 1 (TSK-006): tests untuk account lock setelah 5x failed (NC-SYS-001-01).
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import async_session_factory
from app.identity.models import HierarchyLevel, Role, User, UserRole
from app.main import app


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session per test (rollback at end)."""
    async with async_session_factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client untuk testing endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def test_user(session: AsyncSession) -> User:
    """Setup test user dengan role Direktur Utama untuk test."""
    # Insert role kalau belum ada
    role = Role(
        code="TEST_DIREKTUR",
        name="Test Direktur Utama",
        level=HierarchyLevel.L1_DIREKTUR_UTAMA.value,
        is_executive=True,
    )
    session.add(role)
    await session.flush()

    user = User(
        nik="TEST-001",
        password_hash=hash_password("test-password-123"),
        email="test@ide.asia",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User) -> None:
    """Login dengan kredensial valid → 200 + access_token + user info."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "TEST-001", "password": "test-password-123"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]  # placeholder OK di TSK-001
    assert data["user"]["nik"] == "TEST-001"
    assert data["user"]["is_active"] is True
    assert len(data["user"]["roles"]) >= 1


@pytest.mark.asyncio
async def test_login_invalid_nik(client: AsyncClient) -> None:
    """Login dengan NIK yang tidak ada → 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "NONEXISTENT-999", "password": "anything"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_CREDENTIALS"
    # Tidak boleh leak info "NIK tidak ditemukan" — generic message
    assert "NIK atau password tidak valid" in detail["message"]


@pytest.mark.asyncio
async def test_login_invalid_password(
    client: AsyncClient, test_user: User
) -> None:
    """Login dengan password salah → 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "TEST-001", "password": "wrong-password"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_inactive_account(
    client: AsyncClient, session: AsyncSession, test_user: User
) -> None:
    """Login dengan account inactive → 403 (NC-SYS-001-04)."""
    test_user.is_active = False
    await session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "TEST-001", "password": "test-password-123"},
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_login_validation_empty_nik(client: AsyncClient) -> None:
    """Empty NIK → 422 validation error dari Pydantic."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "", "password": "anything"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_validation_missing_password(client: AsyncClient) -> None:
    """Missing password → 422."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "TEST-001"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_locked_account_after_5_failed_attempts(
    client: AsyncClient, session: AsyncSession, test_user: User
) -> None:
    """5x failed login → account locked 30 menit (NC-SYS-001-01)."""
    # Simulate 4 failed attempts (di bawah threshold)
    for _ in range(4):
        response = await client.post(
            "/api/v1/auth/login",
            json={"nik": "TEST-001", "password": "wrong"},
        )
        assert response.status_code == 401

    # Refresh user untuk lihat counter
    await session.refresh(test_user)
    assert test_user.failed_login_attempts == 4
    assert test_user.is_locked is False

    # 5th attempt — should lock
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "TEST-001", "password": "wrong"},
    )
    assert response.status_code == 401

    await session.refresh(test_user)
    assert test_user.is_locked is True
    assert test_user.locked_until is not None
    assert test_user.locked_until > datetime.now(UTC)

    # Subsequent attempts — even correct password → still locked
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "TEST-001", "password": "test-password-123"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "ACCOUNT_LOCKED"
