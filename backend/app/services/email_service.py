"""Transactional email service powered by Resend.

Encapsulates all Resend-specific logic: API configuration, HTML template
rendering, and scheduled sending.  Designed to be called from Celery
tasks so that email dispatch never blocks the request thread.

When ``RESEND_API_KEY`` is empty (the default for self-hosted
deployments), every public method is a silent no-op.
"""

from datetime import datetime, timedelta, timezone
from html import escape as html_escape

import resend

from app.logging import logger
from app.registry.settings import settings

_WELCOME_DELAY = timedelta(minutes=20)
_FOLLOWUP_DELAY = timedelta(days=7)
_INVITATION_DELAY = timedelta(minutes=2)


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
        """Schedule an invitation notification email with a short delay."""
        if not self.is_configured():
            return

        scheduled_at = (datetime.now(timezone.utc) + _INVITATION_DELAY).isoformat()

        params: resend.Emails.SendParams = {
            "from": settings.RESEND_FROM_INFO,
            "to": [to],
            "subject": f"You've been invited to join {org_name} on PandaProbe",
            "html": self._invitation_html(
                inviter_name=inviter_name,
                role=role,
                app_url=app_url,
            ),
            "scheduled_at": scheduled_at,
        }

        resp = resend.Emails.send(params)
        logger.info(
            "invitation_email_scheduled", to=to, email_id=resp.get("id") if isinstance(resp, dict) else str(resp)
        )

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
        Fastest path: let your coding agent drive it with our packaged skill.
        From your project root:
    </p>

    <p style="margin: 0 0 15px 0;">
        <code style="display: block; background: #f4f4f4; border: 1px solid #e0e0e0;
          border-radius: 4px; padding: 10px 12px; font-family: 'Courier New', monospace;
          font-size: 9pt; white-space: nowrap; overflow-x: auto;">npx skills add chirpz-ai/pandaprobe-skills --skill '*' --yes</code>
    </p>

    <p style="margin: 0 0 15px 0;">
        Then ask your coding agent &ldquo;set up PandaProbe&rdquo; and it'll walk you
        through the onboarding, wiring up PandaProbe, and running your first
        instrumented agent.
    </p>

    <p style="margin: 0 0 15px 0;">
        Prefer to explore on your own? These will help:
    </p>

    <p style="margin: 0 0 8px 0;">
        &bull; Our docs: <a href="https://docs.pandaprobe.com"
          style="color: #0000EE; text-decoration: underline;">https://docs.pandaprobe.com</a>
    </p>
    <p style="margin: 0 0 15px 0;">
        &bull; Our repo: <a href="https://github.com/chirpz-ai/pandaprobe"
          style="color: #0000EE; text-decoration: underline;">https://github.com/chirpz-ai/pandaprobe</a>
    </p>

    <p style="margin: 15px 0;">
        Btw, if you'd like to share what you're building,
        I'd love to chat about how PandaProbe can fit your use case. Grab some time with me here:
        <a href="https://cal.com/sina-tayebati/pandaprobe-intro"
          style="color: #0000EE; text-decoration: underline;">https://cal.com/sina-tayebati/pandaprobe-intro</a>
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
    def _invitation_html(*, inviter_name: str, role: str, app_url: str) -> str:
        inviter = html_escape(inviter_name) if inviter_name else "A team member"
        safe_role = html_escape(role)
        safe_url = html_escape(app_url, quote=True)
        return f"""\
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        {inviter} has invited you to join their organization on PandaProbe
        as a <strong>{safe_role}</strong>.
    </p>

    <p style="margin: 0 0 15px 0;">
        To accept the invitation, visit your PandaProbe dashboard:
        <a href="{safe_url}" style="color: #0000EE; text-decoration: underline;">{safe_url}</a>
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
