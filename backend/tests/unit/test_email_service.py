"""Unit tests for the email service and Celery task (no network or DB required)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailService, _FOLLOWUP_DELAY, _WELCOME_DELAY


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


@patch("app.services.email_service.settings")
def test_is_configured_returns_false_when_key_empty(mock_settings: MagicMock) -> None:
    mock_settings.RESEND_API_KEY = ""
    assert EmailService.is_configured() is False


@patch("app.services.email_service.settings")
def test_is_configured_returns_true_when_key_set(mock_settings: MagicMock) -> None:
    mock_settings.RESEND_API_KEY = "re_test_123"
    assert EmailService.is_configured() is True


# ---------------------------------------------------------------------------
# send_welcome_email
# ---------------------------------------------------------------------------


@patch("app.services.email_service.resend")
@patch("app.services.email_service.settings")
def test_send_welcome_email_calls_resend_with_correct_params(
    mock_settings: MagicMock,
    mock_resend: MagicMock,
) -> None:
    mock_settings.RESEND_API_KEY = "re_test_key"
    mock_settings.RESEND_FROM = "Test <test@example.com>"
    mock_settings.RESEND_REPLY_TO = "reply@example.com"
    mock_resend.Emails.send.return_value = {"id": "email-123"}

    before = datetime.now(timezone.utc)
    svc = EmailService()
    svc.send_welcome_email(to="user@example.com")
    after = datetime.now(timezone.utc)

    mock_resend.Emails.send.assert_called_once()
    params = mock_resend.Emails.send.call_args[0][0]

    assert params["to"] == ["user@example.com"]
    assert params["subject"] == "Welcome to PandaProbe"
    assert params["from"] == "Test <test@example.com>"
    assert params["reply_to"] == "reply@example.com"
    assert "Hey," in params["html"]

    scheduled = datetime.fromisoformat(params["scheduled_at"])
    assert before + _WELCOME_DELAY <= scheduled <= after + _WELCOME_DELAY


# ---------------------------------------------------------------------------
# send_followup_email
# ---------------------------------------------------------------------------


@patch("app.services.email_service.resend")
@patch("app.services.email_service.settings")
def test_send_followup_email_calls_resend_with_correct_params(
    mock_settings: MagicMock,
    mock_resend: MagicMock,
) -> None:
    mock_settings.RESEND_API_KEY = "re_test_key"
    mock_settings.RESEND_FROM = "Test <test@example.com>"
    mock_settings.RESEND_REPLY_TO = "reply@example.com"
    mock_resend.Emails.send.return_value = {"id": "email-789"}

    before = datetime.now(timezone.utc)
    svc = EmailService()
    svc.send_followup_email(to="user@example.com")
    after = datetime.now(timezone.utc)

    mock_resend.Emails.send.assert_called_once()
    params = mock_resend.Emails.send.call_args[0][0]

    assert params["to"] == ["user@example.com"]
    assert params["subject"] == "how's your PandaProbe setup going?"
    assert params["from"] == "Test <test@example.com>"
    assert params["reply_to"] == "reply@example.com"

    scheduled = datetime.fromisoformat(params["scheduled_at"])
    assert before + _FOLLOWUP_DELAY <= scheduled <= after + _FOLLOWUP_DELAY


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------


def test_welcome_html_contains_key_links() -> None:
    html = EmailService._welcome_html()
    assert "docs.pandaprobe.com" in html
    assert "github.com/chirpz-ai/pandaprobe" in html
    assert "discord.gg/A2VfrRhx" in html
    assert "Hey," in html


def test_followup_html_contains_expected_copy() -> None:
    html = EmailService._followup_html()
    assert "checking in" in html
    assert "Sina (founder at PandaProbe)" in html


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@patch("app.services.email_service.resend")
@patch("app.services.email_service.settings")
def test_send_welcome_email_propagates_resend_error(
    mock_settings: MagicMock,
    mock_resend: MagicMock,
) -> None:
    """Errors from Resend bubble up so Celery can retry."""
    mock_settings.RESEND_API_KEY = "re_test_key"
    mock_settings.RESEND_FROM = "Test <test@example.com>"
    mock_settings.RESEND_REPLY_TO = "reply@example.com"
    mock_resend.Emails.send.side_effect = Exception("rate limited")

    svc = EmailService()
    with pytest.raises(Exception, match="rate limited"):
        svc.send_welcome_email(to="user@example.com")


# ---------------------------------------------------------------------------
# Celery task: send_welcome_sequence
# ---------------------------------------------------------------------------


@patch("app.services.email_service.resend")
@patch("app.services.email_service.settings")
def test_celery_task_sends_both_emails(
    mock_settings: MagicMock,
    mock_resend: MagicMock,
) -> None:
    mock_settings.RESEND_API_KEY = "re_test_key"
    mock_settings.RESEND_FROM = "Test <test@example.com>"
    mock_settings.RESEND_REPLY_TO = "reply@example.com"
    mock_resend.Emails.send.return_value = {"id": "ok"}

    from app.infrastructure.queue.tasks import send_welcome_sequence

    result = send_welcome_sequence("user@example.com")

    assert result["status"] == "sent"
    assert mock_resend.Emails.send.call_count == 2


@patch("app.services.email_service.settings")
def test_celery_task_skips_when_unconfigured(mock_settings: MagicMock) -> None:
    mock_settings.RESEND_API_KEY = ""

    from app.infrastructure.queue.tasks import send_welcome_sequence

    result = send_welcome_sequence("user@example.com")

    assert result["status"] == "skipped"
    assert result["reason"] == "resend_not_configured"
