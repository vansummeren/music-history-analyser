"""Email service — send analysis results over SMTP."""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)

_HTML_TEMPLATE = """\
<!doctype html>
<html>
<head><meta charset="utf-8" /></head>
<body style="font-family: sans-serif; max-width: 640px; margin: auto; padding: 24px;">
  <h1 style="color: #1db954;">Music History Analysis</h1>
  <p><strong>Schedule:</strong> {schedule_name}</p>
  <p><strong>Time window:</strong> last {time_window_days} days</p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;" />
  <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.6;">
{result_text}
  </div>
  <hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;" />
  <p style="font-size: 12px; color: #888;">
    Sent by Music History Analyser &middot;
    Analysis: {analysis_name}
  </p>
</body>
</html>
"""


def _build_message(
    *,
    recipient: str,
    schedule_name: str,
    analysis_name: str,
    result_text: str,
    time_window_days: int,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Music History Analysis — {schedule_name}"
    msg["From"] = settings.smtp_from
    msg["To"] = recipient

    plain = (
        f"Music History Analysis\n"
        f"Schedule: {schedule_name}\n"
        f"Time window: last {time_window_days} days\n"
        f"Analysis: {analysis_name}\n\n"
        f"{result_text}"
    )
    html = _HTML_TEMPLATE.format(
        schedule_name=schedule_name,
        analysis_name=analysis_name,
        result_text=result_text,
        time_window_days=time_window_days,
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


async def send_analysis_result(
    *,
    recipient: str,
    schedule_name: str,
    analysis_name: str,
    result_text: str,
    time_window_days: int,
) -> None:
    """Send the analysis result email to *recipient*.

    Uses the SMTP settings from ``app.config.settings``.
    All SMTP errors are propagated to the caller.
    """
    msg = _build_message(
        recipient=recipient,
        schedule_name=schedule_name,
        analysis_name=analysis_name,
        result_text=result_text,
        time_window_days=time_window_days,
    )

    smtp_kwargs: dict[str, object] = {
        "hostname": settings.smtp_host,
        "port": settings.smtp_port,
    }
    if settings.smtp_tls:
        smtp_kwargs["use_tls"] = False  # STARTTLS below
        smtp_kwargs["start_tls"] = True

    tls_label = "STARTTLS" if settings.smtp_tls else "plain"
    logger.debug(
        "Connecting to SMTP %s:%d (%s) for schedule %r",
        settings.smtp_host, settings.smtp_port, tls_label, schedule_name,
    )
    try:
        async with aiosmtplib.SMTP(**smtp_kwargs) as smtp:  # type: ignore[arg-type]
            if settings.smtp_username:
                await smtp.login(settings.smtp_username, settings.smtp_password)
            await smtp.send_message(msg)
    except Exception:
        logger.exception(
            "Failed to send analysis email to %s for schedule %r",
            recipient, schedule_name,
        )
        raise

    logger.info("Analysis email sent to %s for schedule %r", recipient, schedule_name)


async def send_test_email(*, recipient: str) -> None:
    """Send a plain test email to *recipient* to verify SMTP connectivity.

    Uses the same SMTP settings as :func:`send_analysis_result`.
    All SMTP errors are propagated to the caller.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Music History Analyser — SMTP test"
    msg["From"] = settings.smtp_from
    msg["To"] = recipient

    plain = (
        "This is a test email from Music History Analyser.\n\n"
        "If you received this, your SMTP configuration is working correctly."
    )
    html = """\
<!doctype html>
<html>
<head><meta charset="utf-8" /></head>
<body style="font-family: sans-serif; max-width: 640px; margin: auto; padding: 24px;">
  <h1 style="color: #1db954;">Music History Analyser</h1>
  <p>This is a <strong>test email</strong>.</p>
  <p>If you received this, your SMTP configuration is working correctly.</p>
</body>
</html>
"""
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    smtp_kwargs: dict[str, object] = {
        "hostname": settings.smtp_host,
        "port": settings.smtp_port,
    }
    if settings.smtp_tls:
        smtp_kwargs["use_tls"] = False  # STARTTLS below
        smtp_kwargs["start_tls"] = True

    tls_label = "STARTTLS" if settings.smtp_tls else "plain"
    logger.debug(
        "Connecting to SMTP %s:%d (%s) for test email",
        settings.smtp_host, settings.smtp_port, tls_label,
    )
    try:
        async with aiosmtplib.SMTP(**smtp_kwargs) as smtp:  # type: ignore[arg-type]
            if settings.smtp_username:
                await smtp.login(settings.smtp_username, settings.smtp_password)
            await smtp.send_message(msg)
    except Exception:
        logger.exception("Failed to send test email to %s", recipient)
        raise

    logger.info("Test email sent to %s", recipient)
