"""Test the complete logs filter flow end-to-end."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.app_log import AppLog
from app.services import auth_service
import uuid
from datetime import datetime, UTC

@pytest.mark.asyncio
async def test_logs_filter_returns_correct_total_and_items(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,
) -> None:
    user = await auth_service.upsert_user(
        db_session, sub="admin-logs-full", provider="oidc",
        email="adminlogsfull@example.com", display_name="Admin"
    )
    user.role = "admin"
    await db_session.commit()
    token = auth_service.create_access_token(user.id)

    for level in ['INFO', 'INFO', 'ERROR', 'WARNING', 'DEBUG']:
        db_session.add(AppLog(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            level=level,
            service='backend',
            logger_name='app.test',
            message=f'Test {level} message',
        ))
    await db_session.commit()

    # Unfiltered - works
    resp = await client.get("/api/admin/logs?limit=100&offset=0",
        headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    print(f"\nUnfiltered: total={data['total']}, items={len(data['items'])}")
    assert data['total'] >= 5
    assert len(data['items']) >= 5

    # Filtered by level=INFO
    resp = await client.get("/api/admin/logs?level=INFO&limit=100&offset=0",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    print(f"level=INFO: total={data['total']}, items={len(data['items'])}")
    # total AND items should both be 2
    assert data['total'] == 2, f"FAIL: expected total=2, got {data['total']}"
    assert len(data['items']) == 2, f"FAIL: expected 2 items, got {len(data['items'])}"
    
    # Filtered by search
    resp = await client.get("/api/admin/logs?search=ERROR&limit=100&offset=0",
        headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    print(f"search=ERROR: total={data['total']}, items={len(data['items'])}")
    assert data['total'] == 1
    assert len(data['items']) == 1
