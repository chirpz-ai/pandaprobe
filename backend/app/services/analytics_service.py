"""PostHog product analytics service.

Wraps the PostHog Python SDK behind a centralized interface that every
route handler and dependency can call.  Follows the same conventions as
``EmailService`` and ``CrmService``:

- A static ``is_configured()`` guard checks for ``POSTHOG_API_KEY``.
- Every public method is a silent no-op when unconfigured.
- Exceptions from the PostHog SDK are caught and logged, never propagated.

The SDK batches events in a background thread and flushes asynchronously,
so ``capture()`` appends to an in-memory queue and returns in microseconds.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import posthog

from app.logging import logger
from app.registry.settings import settings

_PROJECT_NAME = "pandaprobe_app"
_PROJECT_NAME_KEY = "project_name"

_client: posthog.Client | None = None


class AnalyticsService:
    """Stateless adapter around the PostHog Python SDK."""

    @staticmethod
    def is_configured() -> bool:
        """Return *True* when the PostHog API key is present."""
        return bool(settings.POSTHOG_API_KEY)

    @classmethod
    def initialize(cls) -> None:
        """Create the PostHog client.  Call once during app startup."""
        global _client
        if not cls.is_configured():
            logger.info("posthog_disabled", reason="POSTHOG_API_KEY not set")
            return

        host = settings.POSTHOG_HOST or None
        _client = posthog.Client(settings.POSTHOG_API_KEY, host=host)
        logger.info("posthog_initialized", host=host)

    @classmethod
    def shutdown(cls) -> None:
        """Flush pending events and tear down the client.  Call during app shutdown."""
        global _client
        if _client is None:
            return
        try:
            _client.flush()
            _client.shutdown()
        except Exception:
            logger.exception("posthog_shutdown_error")
        finally:
            _client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _capture(
        *,
        org_id: str,
        event: str,
        user_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if _client is None:
            return
        try:
            props: dict[str, Any] = {
                _PROJECT_NAME_KEY: _PROJECT_NAME,
                "org_id": org_id,
            }
            if user_id is not None:
                props["user_id"] = user_id
            if properties:
                props.update(properties)
            _client.capture(
                distinct_id=f"org:{org_id}",
                event=event,
                properties=props,
            )
        except Exception:
            logger.exception("posthog_capture_error", event_name=event, org_id=org_id)

    @staticmethod
    def _set(
        distinct_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if _client is None:
            return
        try:
            props = {_PROJECT_NAME_KEY: _PROJECT_NAME, **(properties or {})}
            _client.set(distinct_id=distinct_id, properties=props)
        except Exception:
            logger.exception("posthog_identify_error", distinct_id=distinct_id)

    # ------------------------------------------------------------------
    # Organization-profile management
    # ------------------------------------------------------------------

    def identify_org(
        self,
        *,
        org_id: str,
        created_at: datetime,
        owner_user_id: str,
        owner_email: str,
        owner_display_name: str | None,
    ) -> None:
        """Set the org profile.  Call once at org creation."""
        if not self.is_configured():
            return
        self._set(
            f"org:{org_id}",
            {
                "org_id": org_id,
                "created_at": created_at.isoformat(),
                "owner_user_id": owner_user_id,
                "owner_email": owner_email,
                "owner_display_name": owner_display_name,
            },
        )

    # ------------------------------------------------------------------
    # Public API — P0 events
    # ------------------------------------------------------------------

    def user_signed_up(
        self,
        *,
        org_id: str,
        user_id: str,
        email: str,
    ) -> None:
        """Capture a new user registration."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="user_signed_up",
            user_id=user_id,
            properties={"email": email},
        )

    def user_authenticated(
        self,
        *,
        org_id: str,
        user_id: str,
    ) -> None:
        """Capture a successful authentication event."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="user_authenticated",
            user_id=user_id,
        )

    def organization_created(
        self,
        *,
        org_id: str,
        user_id: str,
        source: str,
    ) -> None:
        """Capture an organization creation event.

        Fires for every org that comes into existence.
        ``source`` distinguishes the origin:

        - ``"signup"`` — JIT-created during the user's first auth.
        - ``"api"`` — explicitly created via ``POST /organizations``.
        """
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="organization_created",
            user_id=user_id,
            properties={"source": source},
        )

    def trace_ingested(
        self,
        *,
        org_id: str,
        user_id: str | None,
        project_id: str,
        has_session: bool,
        span_count: int,
    ) -> None:
        """Capture a trace ingestion event."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="trace_ingested",
            user_id=user_id,
            properties={
                "project_id": project_id,
                "has_session": has_session,
                "span_count": span_count,
            },
        )

    def api_key_created(
        self,
        *,
        org_id: str,
        user_id: str,
    ) -> None:
        """Capture an API key creation event."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="api_key_created",
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Public API — P1 events
    # ------------------------------------------------------------------

    def eval_run_created(
        self,
        *,
        org_id: str,
        user_id: str | None,
        project_id: str,
        metric_names: list[str],
        target_count: int,
        model: str | None,
    ) -> None:
        """Capture a trace evaluation run creation."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="eval_run_created",
            user_id=user_id,
            properties={
                "project_id": project_id,
                "metric_names": metric_names,
                "target_count": target_count,
                "model": model,
            },
        )

    def session_eval_run_created(
        self,
        *,
        org_id: str,
        user_id: str | None,
        project_id: str,
        metric_names: list[str],
        session_count: int,
        model: str | None,
    ) -> None:
        """Capture a session evaluation run creation."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="session_eval_run_created",
            user_id=user_id,
            properties={
                "project_id": project_id,
                "metric_names": metric_names,
                "session_count": session_count,
                "model": model,
            },
        )

    def eval_monitor_created(
        self,
        *,
        org_id: str,
        user_id: str | None,
        project_id: str,
        target_type: str,
        cadence: str,
        metric_names: list[str],
    ) -> None:
        """Capture an evaluation monitor creation."""
        if not self.is_configured():
            return
        self._capture(
            org_id=org_id,
            event="eval_monitor_created",
            user_id=user_id,
            properties={
                "project_id": project_id,
                "target_type": target_type,
                "cadence": cadence,
                "metric_names": metric_names,
            },
        )
