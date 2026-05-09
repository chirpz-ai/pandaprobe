"""Unit tests for the PostHog analytics service (no network required)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import app.services.analytics_service as analytics_module
from app.services.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_is_configured_returns_false_when_key_empty(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = ""
    assert AnalyticsService.is_configured() is False


@patch("app.services.analytics_service.settings")
def test_is_configured_returns_true_when_key_set(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key_123"
    assert AnalyticsService.is_configured() is True


# ---------------------------------------------------------------------------
# initialize / shutdown
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.posthog")
@patch("app.services.analytics_service.settings")
def test_initialize_creates_client_when_configured(
    mock_settings: MagicMock,
    mock_posthog: MagicMock,
) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_settings.POSTHOG_HOST = "https://eu.posthog.com"
    mock_posthog.Client.return_value = MagicMock()

    try:
        AnalyticsService.initialize()
        mock_posthog.Client.assert_called_once_with("phc_test_key", host="https://eu.posthog.com")
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.posthog")
@patch("app.services.analytics_service.settings")
def test_initialize_uses_default_host_when_empty(
    mock_settings: MagicMock,
    mock_posthog: MagicMock,
) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_settings.POSTHOG_HOST = ""
    mock_posthog.Client.return_value = MagicMock()

    try:
        AnalyticsService.initialize()
        mock_posthog.Client.assert_called_once_with("phc_test_key", host=None)
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.posthog")
@patch("app.services.analytics_service.settings")
def test_initialize_skips_when_unconfigured(
    mock_settings: MagicMock,
    mock_posthog: MagicMock,
) -> None:
    mock_settings.POSTHOG_API_KEY = ""
    AnalyticsService.initialize()
    mock_posthog.Client.assert_not_called()
    assert analytics_module._client is None


@patch("app.services.analytics_service.settings")
def test_shutdown_flushes_and_tears_down_client(mock_settings: MagicMock) -> None:
    mock_client = MagicMock()
    analytics_module._client = mock_client

    try:
        AnalyticsService.shutdown()
        mock_client.flush.assert_called_once()
        mock_client.shutdown.assert_called_once()
    finally:
        analytics_module._client = None

    assert analytics_module._client is None


def test_shutdown_noop_when_no_client() -> None:
    analytics_module._client = None
    AnalyticsService.shutdown()
    assert analytics_module._client is None


# ---------------------------------------------------------------------------
# _capture internals -- distinct_id derivation, project_name + org_id injection
# ---------------------------------------------------------------------------


def _setup_client() -> MagicMock:
    """Install a mock PostHog client and return it."""
    mock_client = MagicMock()
    analytics_module._client = mock_client
    return mock_client


@patch("app.services.analytics_service.settings")
def test_capture_uses_org_distinct_id(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(org_id="org-42", user_id="u1")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-42"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_capture_injects_project_name_and_org_id_automatically(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(org_id="org1", user_id="u1")

        props = mock_client.capture.call_args[1]["properties"]
        assert props["project_name"] == "pandaprobe_app"
        assert props["org_id"] == "org1"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_capture_omits_groups_kwarg(mock_settings: MagicMock) -> None:
    """Group Analytics is intentionally not used; groups= must not be sent."""
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(org_id="org-42", user_id="u1")

        kw = mock_client.capture.call_args[1]
        assert "groups" not in kw
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_capture_includes_user_id_in_properties_when_provided(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.trace_ingested(
            org_id="org-1",
            user_id="user-99",
            project_id="p1",
            has_session=False,
            span_count=1,
        )

        props = mock_client.capture.call_args[1]["properties"]
        assert props["user_id"] == "user-99"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_capture_omits_user_id_from_properties_when_none(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.trace_ingested(
            org_id="org-1",
            user_id=None,
            project_id="p1",
            has_session=False,
            span_count=1,
        )

        props = mock_client.capture.call_args[1]["properties"]
        assert "user_id" not in props
    finally:
        analytics_module._client = None


# ---------------------------------------------------------------------------
# No-op when unconfigured
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_capture_is_noop_when_unconfigured(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = ""
    analytics_module._client = None

    svc = AnalyticsService()
    svc.user_signed_up(org_id="o1", user_id="u1", email="a@b.com")
    svc.user_authenticated(org_id="o1", user_id="u1")
    svc.organization_created(org_id="o1", user_id="u1", source="signup")
    svc.trace_ingested(org_id="o1", user_id=None, project_id="p1", has_session=False, span_count=3)
    svc.api_key_created(org_id="o1", user_id="u1")
    svc.eval_run_created(org_id="o1", user_id=None, project_id="p1", metric_names=["m"], target_count=1, model=None)
    svc.session_eval_run_created(
        org_id="o1", user_id=None, project_id="p1", metric_names=["m"], session_count=1, model=None
    )
    svc.eval_monitor_created(
        org_id="o1", user_id=None, project_id="p1", target_type="TRACE", cadence="daily", metric_names=["m"]
    )
    svc.identify_org(
        org_id="o1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        owner_user_id="u1",
        owner_email="a@b.com",
        owner_display_name="A",
    )


# ---------------------------------------------------------------------------
# Error isolation -- SDK exceptions are swallowed
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_capture_swallows_sdk_exceptions(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    mock_client.capture.side_effect = RuntimeError("network failure")

    try:
        svc = AnalyticsService()
        svc.user_authenticated(org_id="o1", user_id="u1")
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_identify_swallows_sdk_exceptions(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    mock_client.set.side_effect = RuntimeError("network failure")

    try:
        svc = AnalyticsService()
        svc.identify_org(
            org_id="o1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            owner_user_id="u1",
            owner_email="a@b.com",
            owner_display_name="A",
        )
    finally:
        analytics_module._client = None


# ---------------------------------------------------------------------------
# P0 event methods
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_user_signed_up_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_signed_up(
            org_id="org-1",
            user_id="user-1",
            email="user@example.com",
        )

        mock_client.capture.assert_called_once()
        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-1"
        assert kw["event"] == "user_signed_up"
        assert kw["properties"]["project_name"] == "pandaprobe_app"
        assert kw["properties"]["email"] == "user@example.com"
        assert kw["properties"]["org_id"] == "org-1"
        assert kw["properties"]["user_id"] == "user-1"
        assert "groups" not in kw
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_user_authenticated_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(org_id="org-2", user_id="user-2")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-2"
        assert kw["event"] == "user_authenticated"
        assert kw["properties"]["org_id"] == "org-2"
        assert kw["properties"]["user_id"] == "user-2"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_organization_created_captures_signup_source(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.organization_created(org_id="org-9", user_id="user-9", source="signup")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-9"
        assert kw["event"] == "organization_created"
        assert kw["properties"]["org_id"] == "org-9"
        assert kw["properties"]["user_id"] == "user-9"
        assert kw["properties"]["source"] == "signup"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_organization_created_captures_api_source(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.organization_created(org_id="org-10", user_id="user-10", source="api")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-10"
        assert kw["event"] == "organization_created"
        assert kw["properties"]["source"] == "api"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_trace_ingested_captures_correct_event_with_user(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.trace_ingested(
            org_id="org-3",
            user_id="user-3",
            project_id="proj-1",
            has_session=True,
            span_count=5,
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-3"
        assert kw["event"] == "trace_ingested"
        assert kw["properties"]["project_id"] == "proj-1"
        assert kw["properties"]["has_session"] is True
        assert kw["properties"]["span_count"] == 5
        assert kw["properties"]["org_id"] == "org-3"
        assert kw["properties"]["user_id"] == "user-3"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_trace_ingested_captures_correct_event_without_user(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.trace_ingested(
            org_id="org-3",
            user_id=None,
            project_id="proj-1",
            has_session=False,
            span_count=2,
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-3"
        assert "user_id" not in kw["properties"]
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_api_key_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.api_key_created(org_id="org-4", user_id="user-4")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-4"
        assert kw["event"] == "api_key_created"
        assert kw["properties"]["user_id"] == "user-4"
        assert kw["properties"]["org_id"] == "org-4"
    finally:
        analytics_module._client = None


# ---------------------------------------------------------------------------
# P1 event methods
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_eval_run_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.eval_run_created(
            org_id="org-5",
            user_id="user-5",
            project_id="proj-2",
            metric_names=["task_completion", "tool_correctness"],
            target_count=50,
            model="openai/gpt-4o",
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-5"
        assert kw["event"] == "eval_run_created"
        assert kw["properties"]["metric_names"] == ["task_completion", "tool_correctness"]
        assert kw["properties"]["target_count"] == 50
        assert kw["properties"]["model"] == "openai/gpt-4o"
        assert kw["properties"]["user_id"] == "user-5"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_session_eval_run_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.session_eval_run_created(
            org_id="org-6",
            user_id=None,
            project_id="proj-3",
            metric_names=["agent_reliability"],
            session_count=10,
            model=None,
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-6"
        assert kw["event"] == "session_eval_run_created"
        assert kw["properties"]["session_count"] == 10
        assert kw["properties"]["model"] is None
        assert "user_id" not in kw["properties"]
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_eval_monitor_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.eval_monitor_created(
            org_id="org-7",
            user_id="user-7",
            project_id="proj-4",
            target_type="TRACE",
            cadence="daily",
            metric_names=["task_completion"],
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-7"
        assert kw["event"] == "eval_monitor_created"
        assert kw["properties"]["target_type"] == "TRACE"
        assert kw["properties"]["cadence"] == "daily"
        assert kw["properties"]["metric_names"] == ["task_completion"]
        assert kw["properties"]["user_id"] == "user-7"
    finally:
        analytics_module._client = None


# ---------------------------------------------------------------------------
# identify_org
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_identify_org_sets_org_profile(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        svc.identify_org(
            org_id="org-8",
            created_at=created_at,
            owner_user_id="user-8",
            owner_email="owner@acme.com",
            owner_display_name="Owner Name",
        )

        mock_client.set.assert_called_once()
        kw = mock_client.set.call_args[1]
        assert kw["distinct_id"] == "org:org-8"
        props = kw["properties"]
        assert props["project_name"] == "pandaprobe_app"
        assert props["org_id"] == "org-8"
        assert props["created_at"] == created_at.isoformat()
        assert props["owner_user_id"] == "user-8"
        assert props["owner_email"] == "owner@acme.com"
        assert props["owner_display_name"] == "Owner Name"
        assert "plan" not in props
        assert "org_name" not in props
    finally:
        analytics_module._client = None
