"""Tests for Session 05 — Email service and scheduled analysis task."""
from __future__ import annotations

import uuid
from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_smtp_context(sent_messages: list[MIMEMultipart]) -> MagicMock:
    """Return an async context manager mock that captures sent messages."""
    smtp_instance = AsyncMock()

    async def _send_message(msg: MIMEMultipart) -> None:
        sent_messages.append(msg)

    smtp_instance.send_message = _send_message
    smtp_instance.login = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=smtp_instance)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _plain_text(msg: MIMEMultipart) -> str:
    """Extract the plain-text payload from a MIME message, handling both str and bytes."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            raw = part.get_payload(decode=True)
            if isinstance(raw, bytes):
                return raw.decode()
            # Already decoded (e.g. 7bit encoding)
            return part.get_payload() or ""
    return ""


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_analysis_result_sends_email() -> None:
    """send_analysis_result should send a message with the correct subject."""
    from app.services.email_service import send_analysis_result

    sent: list[MIMEMultipart] = []
    ctx = _mock_smtp_context(sent)

    with patch("app.services.email_service.aiosmtplib.SMTP", return_value=ctx):
        await send_analysis_result(
            recipient="listener@example.com",
            schedule_name="Weekly Report",
            analysis_name="Test Analysis",
            result_text="You listened to a lot of jazz.",
            time_window_days=7,
        )

    assert len(sent) == 1
    msg = sent[0]
    assert "Weekly Report" in msg["Subject"]
    assert msg["To"] == "listener@example.com"


@pytest.mark.asyncio
async def test_send_analysis_result_includes_result_text() -> None:
    """The email body (plain part) should contain the result text."""
    from app.services.email_service import send_analysis_result

    sent: list[MIMEMultipart] = []
    ctx = _mock_smtp_context(sent)

    with patch("app.services.email_service.aiosmtplib.SMTP", return_value=ctx):
        await send_analysis_result(
            recipient="a@b.com",
            schedule_name="Sched",
            analysis_name="Ana",
            result_text="Heavy metal phase detected.",
            time_window_days=14,
        )

    msg = sent[0]
    # Walk the MIME parts and find the plain text payload
    plain_payload = _plain_text(msg)
    assert "Heavy metal phase detected." in plain_payload


@pytest.mark.asyncio
async def test_send_analysis_result_smtp_login_called_when_credentials_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """login() should be called when smtp_username is configured."""
    from app.config import settings
    from app.services import email_service

    monkeypatch.setattr(settings, "smtp_username", "user@mail.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")

    sent: list[MIMEMultipart] = []
    smtp_instance = AsyncMock()

    async def _send_message(msg: MIMEMultipart) -> None:
        sent.append(msg)

    smtp_instance.send_message = _send_message
    login_calls: list[tuple[str, str]] = []

    async def _login(u: str, p: str) -> None:
        login_calls.append((u, p))

    smtp_instance.login = _login

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=smtp_instance)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.email_service.aiosmtplib.SMTP", return_value=ctx):
        await email_service.send_analysis_result(
            recipient="r@r.com",
            schedule_name="S",
            analysis_name="A",
            result_text="text",
            time_window_days=7,
        )

    assert len(login_calls) == 1
    assert login_calls[0] == ("user@mail.com", "secret")


@pytest.mark.asyncio
async def test_send_analysis_result_propagates_smtp_error() -> None:
    """SMTP errors should propagate so callers can handle them."""
    from app.services.email_service import send_analysis_result

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=ConnectionRefusedError("SMTP down"))
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.email_service.aiosmtplib.SMTP", return_value=ctx), pytest.raises(
        ConnectionRefusedError
    ):
        await send_analysis_result(
            recipient="r@r.com",
            schedule_name="S",
            analysis_name="A",
            result_text="text",
            time_window_days=7,
        )


# ── Scheduled analysis task: email always sent ────────────────────────────────


def _make_run(
    *, status: str, result_text: str | None = None, error: str | None = None
) -> MagicMock:
    """Return a fake AnalysisRun-like object."""
    run = MagicMock()
    run.id = uuid.uuid4()
    run.status = status
    run.result_text = result_text
    run.error = error
    return run


def _make_schedule(*, schedule_id: uuid.UUID, analysis_id: uuid.UUID) -> MagicMock:
    schedule = MagicMock()
    schedule.id = schedule_id
    schedule.analysis_id = analysis_id
    schedule.is_active = True
    schedule.recipient_email = "user@example.com"
    schedule.time_window_days = 7
    return schedule


def _make_analysis(*, analysis_id: uuid.UUID) -> MagicMock:
    analysis = MagicMock()
    analysis.id = analysis_id
    analysis.name = "My Analysis"
    return analysis


@pytest.mark.asyncio
async def test_run_scheduled_analysis_sends_email_on_failure() -> None:
    """An email must be sent even when the analysis run has status='failed'."""
    from app.tasks.analysis_tasks import _run

    schedule_id = uuid.uuid4()
    analysis_id = uuid.uuid4()
    schedule = _make_schedule(schedule_id=schedule_id, analysis_id=analysis_id)
    analysis = _make_analysis(analysis_id=analysis_id)
    run = _make_run(
        status="failed",
        error="Spotify account is missing required scope(s): user-top-read.",
    )

    sent: list[MIMEMultipart] = []
    smtp_ctx = _mock_smtp_context(sent)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[schedule, analysis])
    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_engine = AsyncMock()
    mock_session_maker = MagicMock(return_value=session_ctx)

    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine),
        patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_session_maker),
        patch("app.services.analysis_service.run_analysis", new=AsyncMock(return_value=run)),
        patch("app.services.schedule_service.mark_schedule_ran", new=AsyncMock()),
        patch("app.services.email_service.aiosmtplib.SMTP", return_value=smtp_ctx),
    ):
        result = await _run(schedule_id)

    assert result["status"] == "failed"
    assert len(sent) == 1, "Expected exactly one email to be sent on failure"
    msg = sent[0]
    assert "user-top-read" in _plain_text(msg)


@pytest.mark.asyncio
async def test_run_scheduled_analysis_sends_email_on_success() -> None:
    """An email must be sent when the analysis run has status='completed'."""
    from app.tasks.analysis_tasks import _run

    schedule_id = uuid.uuid4()
    analysis_id = uuid.uuid4()
    schedule = _make_schedule(schedule_id=schedule_id, analysis_id=analysis_id)
    analysis = _make_analysis(analysis_id=analysis_id)
    run = _make_run(status="completed", result_text="You love jazz.")

    sent: list[MIMEMultipart] = []
    smtp_ctx = _mock_smtp_context(sent)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[schedule, analysis])
    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_engine = AsyncMock()
    mock_session_maker = MagicMock(return_value=session_ctx)

    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine),
        patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_session_maker),
        patch("app.services.analysis_service.run_analysis", new=AsyncMock(return_value=run)),
        patch("app.services.schedule_service.mark_schedule_ran", new=AsyncMock()),
        patch("app.services.email_service.aiosmtplib.SMTP", return_value=smtp_ctx),
    ):
        result = await _run(schedule_id)

    assert result["status"] == "completed"
    assert len(sent) == 1, "Expected exactly one email to be sent on success"
    msg = sent[0]
    assert "You love jazz." in _plain_text(msg)
