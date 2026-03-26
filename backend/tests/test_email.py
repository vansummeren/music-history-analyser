"""Tests for Session 05 — Email service."""
from __future__ import annotations

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
    plain_payload = ""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            plain_payload = part.get_payload()
            break
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
