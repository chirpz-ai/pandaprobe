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

from typing import Any

import posthog

from app.logging import logger
from app.registry.settings import settings

_PRODUCT_NAME = "pandaprobe"
_PRODUCT_NAME_KEY = "product_name"

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
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
        *,
        org_id: str | None = None,
    ) -> None:
        if _client is None:
            return
        try:
            props = {_PRODUCT_NAME_KEY: _PRODUCT_NAME, **(properties or {})}
            groups = {"organization": org_id} if org_id else None
            _client.capture(distinct_id=distinct_id, event=event, properties=props, groups=groups)
        except Exception:
            logger.exception("posthog_capture_error", event_name=event, distinct_id=distinct_id)

    @staticmethod
    def _identify(
        distinct_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if _client is None:
            return
        try:
            props = {_PRODUCT_NAME_KEY: _PRODUCT_NAME, **(properties or {})}
            _client.set(distinct_id=distinct_id, properties=props)
        except Exception:
            logger.exception("posthog_identify_error", distinct_id=distinct_id)

    # ------------------------------------------------------------------
    # Public API — P0 events
    # ------------------------------------------------------------------

    def identify_user(
        self,
        *,
        user_id: str,
        email: str,
        display_name: str | None,
        org_id: str,
    ) -> None:
        """Set person properties on the PostHog user profile."""
        if not self.is_configured():
            return
        self._identify(user_id, {"email": email, "display_name": display_name, "org_id": org_id})

    def user_signed_up(
        self,
        *,
        user_id: str,
        email: str,
        org_id: str,
    ) -> None:
        """Capture a new user registration."""
        if not self.is_configured():
            return
        self._capture(
            user_id,
            "user_signed_up",
            {"email": email, "org_id": org_id},
            org_id=org_id,
        )

    def user_authenticated(
        self,
        *,
        user_id: str,
        org_id: str,
    ) -> None:
        """Capture a successful authentication event."""
        if not self.is_configured():
            return
        self._capture(
            user_id,
            "user_authenticated",
            {"org_id": org_id},
            org_id=org_id,
        )

    def trace_ingested(
        self,
        *,
        distinct_id: str,
        project_id: str,
        org_id: str,
        has_session: bool,
        span_count: int,
    ) -> None:
        """Capture a trace ingestion event."""
        if not self.is_configured():
            return
        self._capture(
            distinct_id,
            "trace_ingested",
            {
                "project_id": project_id,
                "org_id": org_id,
                "has_session": has_session,
                "span_count": span_count,
            },
            org_id=org_id,
        )

    def api_key_created(
        self,
        *,
        user_id: str,
        org_id: str,
    ) -> None:
        """Capture an API key creation event."""
        if not self.is_configured():
            return
        self._capture(
            user_id,
            "api_key_created",
            {"org_id": org_id, "user_id": user_id},
            org_id=org_id,
        )

    # ------------------------------------------------------------------
    # Public API — P1 events
    # ------------------------------------------------------------------

    def eval_run_created(
        self,
        *,
        distinct_id: str,
        project_id: str,
        org_id: str,
        metric_names: list[str],
        target_count: int,
        model: str | None,
    ) -> None:
        """Capture a trace evaluation run creation."""
        if not self.is_configured():
            return
        self._capture(
            distinct_id,
            "eval_run_created",
            {
                "project_id": project_id,
                "org_id": org_id,
                "metric_names": metric_names,
                "target_count": target_count,
                "model": model,
            },
            org_id=org_id,
        )

    def session_eval_run_created(
        self,
        *,
        distinct_id: str,
        project_id: str,
        org_id: str,
        metric_names: list[str],
        session_count: int,
        model: str | None,
    ) -> None:
        """Capture a session evaluation run creation."""
        if not self.is_configured():
            return
        self._capture(
            distinct_id,
            "session_eval_run_created",
            {
                "project_id": project_id,
                "org_id": org_id,
                "metric_names": metric_names,
                "session_count": session_count,
                "model": model,
            },
            org_id=org_id,
        )

    def eval_monitor_created(
        self,
        *,
        distinct_id: str,
        project_id: str,
        org_id: str,
        target_type: str,
        cadence: str,
        metric_names: list[str],
    ) -> None:
        """Capture an evaluation monitor creation."""
        if not self.is_configured():
            return
        self._capture(
            distinct_id,
            "eval_monitor_created",
            {
                "project_id": project_id,
                "org_id": org_id,
                "target_type": target_type,
                "cadence": cadence,
                "metric_names": metric_names,
            },
            org_id=org_id,
        )
