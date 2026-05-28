"""Tests untuk password reset flow — TSK-007.

Coverage:
- ✓ forgot-password generic response (no enumeration)
- ✓ forgot-password generate token (DEV mode includes token)
- ✓ reset-password dengan valid token → password updated
- ✓ reset-password dengan invalid token → 400
- ✓ reset-password single-use (token consumed)
- ✓ change-password dengan correct current → success
- ✓ change-password dengan wrong current → 400
- ✓ change-password same password → 400
- ✓ Audit logs PASSWORD_RESET_* terekam
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.database import async_session_factory
from app.identity.models import AuditLog, HierarchyLevel, Role, User, UserRole
from app.main import app


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
async def test_user(session: AsyncSession) -> User:
    """Create test user dengan password 'original-pass-123'."""
    role = Role(
        code="TEST_GM_PWD",
        name="Test GM",
        level=HierarchyLevel.L3_GM.value,
        is_executive=False,
    )
    session.add(role)
    await session.flush()

    user = User(
        nik="PWD-TEST-001",
        password_hash=hash_password("original-pass-123"),
        email="pwd-test@ide.asia",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    from app.identity.service import get_user_by_id

    user_full = await get_user_by_id(session, user.id)
    assert user_full is not None
    return user_full


# ─── Forgot password ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_existing_user_returns_token_dev(
    client: AsyncClient, test_user: User
) -> None:
    """DEV mode: forgot-password return reset_token untuk testing."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"nik": "PWD-TEST-001"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    # Dev mode: token disertakan
    assert data.get("reset_token"), "DEV mode should return reset_token"


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_user_generic_response(
    client: AsyncClient,
) -> None:
    """Forgot-password untuk NIK yang tidak ada → tetap 200 generic (anti-enumeration)."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"nik": "NONEXISTENT-999"},
    )
    assert response.status_code == 200
    data = response.json()
    # Generic message, NO token
    assert "message" in data
    assert data.get("reset_token") is None


# ─── Reset password ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_updates_password(
    client: AsyncClient, session: AsyncSession, test_user: User
) -> None:
    """Reset password dengan valid token → password ter-update."""
    # 1. Request reset
    response1 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"nik": "PWD-TEST-001"},
    )
    token = response1.json()["reset_token"]
    assert token

    # 2. Reset dengan token
    response2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "new-pass-456"},
    )
    assert response2.status_code == 200
    assert response2.json()["success"] is True

    # 3. Verify password updated di DB
    await session.refresh(test_user)
    assert verify_password("new-pass-456", test_user.password_hash) is True
    assert verify_password("original-pass-123", test_user.password_hash) is False


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token_returns_400(
    client: AsyncClient,
) -> None:
    """Reset dengan token gibberish → 400."""
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid-token-string-doesnt-exist", "new_password": "any-pass-123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_RESET_TOKEN"


@pytest.mark.asyncio
async def test_reset_password_token_single_use(
    client: AsyncClient, test_user: User
) -> None:
    """Reset token hanya bisa dipakai sekali."""
    response1 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"nik": "PWD-TEST-001"},
    )
    token = response1.json()["reset_token"]

    # Use sekali — sukses
    r1 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "first-new-pass-789"},
    )
    assert r1.status_code == 200

    # Use kedua kali — fail
    r2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "another-pass-000"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["code"] == "INVALID_RESET_TOKEN"


# ─── Change password (authenticated) ─────────────────────────────


@pytest.mark.asyncio
async def test_change_password_with_correct_current(
    client: AsyncClient, session: AsyncSession, test_user: User
) -> None:
    """Authenticated user ganti password sendiri."""
    # Login dulu
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "PWD-TEST-001", "password": "original-pass-123"},
    )
    token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "original-pass-123", "new_password": "totally-new-pass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    await session.refresh(test_user)
    assert verify_password("totally-new-pass", test_user.password_hash) is True


@pytest.mark.asyncio
async def test_change_password_wrong_current_rejected(
    client: AsyncClient, test_user: User
) -> None:
    """Change password dengan current salah → 400."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "PWD-TEST-001", "password": "original-pass-123"},
    )
    token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WRONG-current", "new_password": "anything-new-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "WRONG_CURRENT_PASSWORD"


@pytest.mark.asyncio
async def test_change_password_same_as_current_rejected(
    client: AsyncClient, test_user: User
) -> None:
    """New password sama dengan current → 400."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"nik": "PWD-TEST-001", "password": "original-pass-123"},
    )
    token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "original-pass-123", "new_password": "original-pass-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SAME_PASSWORD"


@pytest.mark.asyncio
async def test_password_reset_audit_log_created(
    client: AsyncClient, session: AsyncSession, test_user: User
) -> None:
    """PASSWORD_RESET_TOKEN_ISSUED + PASSWORD_RESET_SUCCESS audit entries."""
    response1 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"nik": "PWD-TEST-001"},
    )
    token = response1.json()["reset_token"]
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "audit-test-pass-123"},
    )

    # Cek 2 audit entries
    stmt = (
        select(AuditLog)
        .where(AuditLog.actor_nik == "PWD-TEST-001", AuditLog.action.like("PASSWORD_RESET%"))
        .order_by(AuditLog.timestamp)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()
    actions = [log.action for log in logs]

    assert "PASSWORD_RESET_TOKEN_ISSUED" in actions
    assert "PASSWORD_RESET_SUCCESS" in actions
