"""Unit tests for the PostHog analytics service (no network required)."""

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
# _capture internals -- project_name injection & groups
# ---------------------------------------------------------------------------


def _setup_client() -> MagicMock:
    """Install a mock PostHog client and return it."""
    mock_client = MagicMock()
    analytics_module._client = mock_client
    return mock_client


@patch("app.services.analytics_service.settings")
def test_capture_injects_project_name_automatically(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(user_id="u1", org_id="org1")

        call_kwargs = mock_client.capture.call_args[1]
        assert call_kwargs["properties"]["project_name"] == "pandaprobe_app"
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_capture_attaches_organization_group(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(user_id="u1", org_id="org-42")

        call_kwargs = mock_client.capture.call_args[1]
        assert call_kwargs["groups"] == {"organization": "org-42"}
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
    svc.user_signed_up(user_id="u1", email="a@b.com", org_id="o1")
    svc.user_authenticated(user_id="u1", org_id="o1")
    svc.trace_ingested(distinct_id="u1", project_id="p1", org_id="o1", has_session=False, span_count=3)
    svc.api_key_created(user_id="u1", org_id="o1")
    svc.eval_run_created(
        distinct_id="u1", project_id="p1", org_id="o1", metric_names=["m"], target_count=1, model=None
    )
    svc.session_eval_run_created(
        distinct_id="u1", project_id="p1", org_id="o1", metric_names=["m"], session_count=1, model=None
    )
    svc.eval_monitor_created(
        distinct_id="u1", project_id="p1", org_id="o1", target_type="TRACE", cadence="daily", metric_names=["m"]
    )
    svc.identify_user(user_id="u1", email="a@b.com", display_name="A", org_id="o1")


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
        svc.user_authenticated(user_id="u1", org_id="o1")
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_identify_swallows_sdk_exceptions(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    mock_client.set.side_effect = RuntimeError("network failure")

    try:
        svc = AnalyticsService()
        svc.identify_user(user_id="u1", email="a@b.com", display_name="A", org_id="o1")
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
            user_id="user-1",
            email="user@example.com",
            org_id="org-1",
        )

        mock_client.capture.assert_called_once()
        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "user-1"
        assert kw["event"] == "user_signed_up"
        assert kw["properties"]["project_name"] == "pandaprobe_app"
        assert kw["properties"]["email"] == "user@example.com"
        assert kw["properties"]["org_id"] == "org-1"
        assert kw["groups"] == {"organization": "org-1"}
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_user_authenticated_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.user_authenticated(user_id="user-2", org_id="org-2")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "user-2"
        assert kw["event"] == "user_authenticated"
        assert kw["properties"]["org_id"] == "org-2"
        assert kw["groups"] == {"organization": "org-2"}
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_trace_ingested_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.trace_ingested(
            distinct_id="org:org-3",
            project_id="proj-1",
            org_id="org-3",
            has_session=True,
            span_count=5,
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "org:org-3"
        assert kw["event"] == "trace_ingested"
        assert kw["properties"]["project_id"] == "proj-1"
        assert kw["properties"]["has_session"] is True
        assert kw["properties"]["span_count"] == 5
        assert kw["groups"] == {"organization": "org-3"}
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_api_key_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.api_key_created(user_id="user-4", org_id="org-4")

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "user-4"
        assert kw["event"] == "api_key_created"
        assert kw["properties"]["user_id"] == "user-4"
        assert kw["properties"]["org_id"] == "org-4"
        assert kw["groups"] == {"organization": "org-4"}
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
            distinct_id="user-5",
            project_id="proj-2",
            org_id="org-5",
            metric_names=["task_completion", "tool_correctness"],
            target_count=50,
            model="openai/gpt-4o",
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "user-5"
        assert kw["event"] == "eval_run_created"
        assert kw["properties"]["metric_names"] == ["task_completion", "tool_correctness"]
        assert kw["properties"]["target_count"] == 50
        assert kw["properties"]["model"] == "openai/gpt-4o"
        assert kw["groups"] == {"organization": "org-5"}
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_session_eval_run_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.session_eval_run_created(
            distinct_id="user-6",
            project_id="proj-3",
            org_id="org-6",
            metric_names=["agent_reliability"],
            session_count=10,
            model=None,
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "user-6"
        assert kw["event"] == "session_eval_run_created"
        assert kw["properties"]["session_count"] == 10
        assert kw["properties"]["model"] is None
        assert kw["groups"] == {"organization": "org-6"}
    finally:
        analytics_module._client = None


@patch("app.services.analytics_service.settings")
def test_eval_monitor_created_captures_correct_event(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.eval_monitor_created(
            distinct_id="user-7",
            project_id="proj-4",
            org_id="org-7",
            target_type="TRACE",
            cadence="daily",
            metric_names=["task_completion"],
        )

        kw = mock_client.capture.call_args[1]
        assert kw["distinct_id"] == "user-7"
        assert kw["event"] == "eval_monitor_created"
        assert kw["properties"]["target_type"] == "TRACE"
        assert kw["properties"]["cadence"] == "daily"
        assert kw["properties"]["metric_names"] == ["task_completion"]
        assert kw["groups"] == {"organization": "org-7"}
    finally:
        analytics_module._client = None


# ---------------------------------------------------------------------------
# identify_user
# ---------------------------------------------------------------------------


@patch("app.services.analytics_service.settings")
def test_identify_user_sets_person_properties(mock_settings: MagicMock) -> None:
    mock_settings.POSTHOG_API_KEY = "phc_test_key"
    mock_client = _setup_client()
    try:
        svc = AnalyticsService()
        svc.identify_user(
            user_id="user-8",
            email="test@example.com",
            display_name="Test User",
            org_id="org-8",
        )

        mock_client.set.assert_called_once()
        kw = mock_client.set.call_args[1]
        assert kw["distinct_id"] == "user-8"
        assert kw["properties"]["project_name"] == "pandaprobe_app"
        assert kw["properties"]["email"] == "test@example.com"
        assert kw["properties"]["display_name"] == "Test User"
        assert kw["properties"]["org_id"] == "org-8"
    finally:
        analytics_module._client = None
