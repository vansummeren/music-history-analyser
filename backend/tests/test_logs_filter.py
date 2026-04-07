"""Quick test to verify logs filtering works."""
import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.app_log import AppLog
from app.services import auth_service
from tests.conftest import FakeRedis
import uuid
from datetime import datetime, UTC

@pytest.mark.asyncio
async def test_logs_filter_by_level(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Filtering logs by level should return only matching entries."""
    # Create an admin user
    user = await auth_service.upsert_user(
        db_session, sub="admin-logs-test", provider="oidc",
        email="adminlogs@example.com", display_name="Admin Logs"
    )
    user.role = "admin"
    await db_session.commit()
    token = auth_service.create_access_token(user.id)

    # Insert test log entries
    for level in ['INFO', 'INFO', 'ERROR', 'WARNING']:
        db_session.add(AppLog(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            level=level,
            service='backend',
            logger_name='app.test',
            message=f'Test {level} message',
        ))
    await db_session.commit()

    # Test unfiltered
    resp = await client.get(
        "/api/admin/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    print(f"\nUnfiltered: total={data['total']}, items={len(data['items'])}")
    assert data['total'] >= 4

    # Test filtered by level=INFO
    resp = await client.get(
        "/api/admin/logs?level=INFO",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    print(f"level=INFO: total={data['total']}, items={len(data['items'])}")
    assert data['total'] == 2, f"Expected 2 INFO logs, got {data['total']}"
    assert all(item['level'] == 'INFO' for item in data['items'])

    # Test filtered by level=ERROR
    resp = await client.get(
        "/api/admin/logs?level=ERROR",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    print(f"level=ERROR: total={data['total']}, items={len(data['items'])}")
    assert data['total'] == 1, f"Expected 1 ERROR log, got {data['total']}"

    # Test filtered by service
    resp = await client.get(
        "/api/admin/logs?service=backend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    print(f"service=backend: total={data['total']}, items={len(data['items'])}")
    assert data['total'] >= 4

    # Test search
    resp = await client.get(
        "/api/admin/logs?search=ERROR",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    print(f"search=ERROR: total={data['total']}, items={len(data['items'])}")
    assert data['total'] >= 1
