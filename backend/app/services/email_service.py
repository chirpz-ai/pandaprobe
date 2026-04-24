"""Transactional email service powered by Resend.

Encapsulates all Resend-specific logic: API configuration, HTML template
rendering, and scheduled sending.  Designed to be called from Celery
tasks so that email dispatch never blocks the request thread.

When ``RESEND_API_KEY`` is empty (the default for self-hosted
deployments), every public method is a silent no-op.
"""

from datetime import datetime, timedelta, timezone

import resend

from app.logging import logger
from app.registry.settings import settings

_WELCOME_DELAY = timedelta(minutes=20)
_FOLLOWUP_DELAY = timedelta(days=7)


class EmailService:
    """Stateless adapter around the Resend Emails API."""

    def __init__(self) -> None:
        if self.is_configured():
            resend.api_key = settings.RESEND_API_KEY

    @staticmethod
    def is_configured() -> bool:
        """Return *True* when the Resend API key is present."""
        return bool(settings.RESEND_API_KEY)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_welcome_email(self, *, to: str) -> None:
        """Schedule a welcome email ~20 minutes after signup."""
        if not self.is_configured():
            return
        scheduled_at = (datetime.now(timezone.utc) + _WELCOME_DELAY).isoformat()

        params: resend.Emails.SendParams = {
            "from": settings.RESEND_FROM,
            "to": [to],
            "reply_to": settings.RESEND_REPLY_TO,
            "subject": "Welcome to PandaProbe",
            "html": self._welcome_html(),
            "scheduled_at": scheduled_at,
        }

        resp = resend.Emails.send(params)
        logger.info("welcome_email_scheduled", to=to, email_id=resp.get("id") if isinstance(resp, dict) else str(resp))

    def send_followup_email(self, *, to: str) -> None:
        """Schedule a follow-up email 7 days after signup."""
        if not self.is_configured():
            return
        scheduled_at = (datetime.now(timezone.utc) + _FOLLOWUP_DELAY).isoformat()

        params: resend.Emails.SendParams = {
            "from": settings.RESEND_FROM,
            "to": [to],
            "reply_to": settings.RESEND_REPLY_TO,
            "subject": "how's your PandaProbe setup going?",
            "html": self._followup_html(),
            "scheduled_at": scheduled_at,
        }

        resp = resend.Emails.send(params)
        logger.info(
            "followup_email_scheduled", to=to, email_id=resp.get("id") if isinstance(resp, dict) else str(resp)
        )

    def send_invitation_email(
        self,
        *,
        to: str,
        org_name: str,
        inviter_name: str,
        role: str,
        app_url: str,
    ) -> None:
        """Send an invitation notification email immediately."""
        if not self.is_configured():
            return

        params: resend.Emails.SendParams = {
            "from": settings.RESEND_FROM_INFO,
            "to": [to],
            "subject": f"You've been invited to join {org_name} on PandaProbe",
            "html": self._invitation_html(
                org_name=org_name,
                inviter_name=inviter_name,
                role=role,
                app_url=app_url,
            ),
        }

        resp = resend.Emails.send(params)
        logger.info("invitation_email_sent", to=to, email_id=resp.get("id") if isinstance(resp, dict) else str(resp))

    # ------------------------------------------------------------------
    # HTML templates
    # ------------------------------------------------------------------

    @staticmethod
    def _welcome_html() -> str:
        return """\
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        Thanks for signing up, this is Sina (founder at PandaProbe).
    </p>

    <p style="margin: 0 0 15px 0;">
        Here's some useful resources to get you started:
    </p>

    <p style="margin: 0 0 8px 0;">
        &bull; Our docs: <a href="https://docs.pandaprobe.com"
          style="color: #0000EE; text-decoration: underline;">https://docs.pandaprobe.com</a>
    </p>
    <p style="margin: 0 0 8px 0;">
        &bull; Our repo: <a href="https://github.com/chirpz-ai/pandaprobe"
          style="color: #0000EE; text-decoration: underline;">https://github.com/chirpz-ai/pandaprobe</a>
    </p>
    <p style="margin: 0 0 15px 0;">
        &bull; Our discord: <a href="https://discord.gg/A2VfrRhx"
          style="color: #0000EE; text-decoration: underline;">https://discord.gg/A2VfrRhx</a>
    </p>

    <p style="margin: 15px 0;">
        Btw, if you want to see PandaProbe in action or just chat about what you're building,
        feel free to book some time with me here:
        <a href="https://www.pandaprobe.com/contact"
          style="color: #0000EE; text-decoration: underline;">https://www.pandaprobe.com/contact</a>
    </p>

    <p style="margin: 15px 0 0 0;">
        Sina<br>
    </p>
</div>"""

    @staticmethod
    def _followup_html() -> str:
        return """\
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey, just checking in.
    </p>

    <p style="margin: 0 0 15px 0;">
        Saw you signed up last week and wanted to see how things are going
        with PandaProbe. Have you had the chance to trace and evaluate an agent yet?
    </p>

    <p style="margin: 0 0 15px 0;">
        Would love to hear what you're building, and let me know if there's
        anything I can do to help.
    </p>

    <p style="margin: 15px 0 0 0;">
        Sina (founder at PandaProbe)
    </p>
</div>"""

    @staticmethod
    def _invitation_html(*, org_name: str, inviter_name: str, role: str, app_url: str) -> str:
        inviter = inviter_name or "A team member"
        return f"""\
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        {inviter} has invited you to join <strong>{org_name}</strong> on PandaProbe
        as a <strong>{role}</strong>.
    </p>

    <p style="margin: 0 0 15px 0;">
        To accept the invitation, visit your PandaProbe dashboard:
        <a href="{app_url}" style="color: #0000EE; text-decoration: underline;">{app_url}</a>
    </p>

    <p style="margin: 0 0 15px 0;">
        If you don't have a PandaProbe account yet, sign up with this email
        address and the invitation will be waiting for you.
    </p>

    <p style="margin: 0 0 15px 0;">
        This invitation expires in 7 days.
    </p>

    <p style="margin: 15px 0 0 0;">
        &mdash; The PandaProbe Team
    </p>
</div>"""
