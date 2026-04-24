"""Unit tests for the CRM service and Celery task (no network required)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.crm_service import CrmService


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


@patch("app.services.crm_service.settings")
def test_is_configured_false_when_key_empty(mock_settings: MagicMock) -> None:
    mock_settings.ATTIO_API_KEY = ""
    mock_settings.ATTIO_LIST_ID = "some-list-id"
    assert CrmService.is_configured() is False


@patch("app.services.crm_service.settings")
def test_is_configured_false_when_list_id_empty(mock_settings: MagicMock) -> None:
    mock_settings.ATTIO_API_KEY = "atk_test_key"
    mock_settings.ATTIO_LIST_ID = ""
    assert CrmService.is_configured() is False


@patch("app.services.crm_service.settings")
def test_is_configured_true_when_both_set(mock_settings: MagicMock) -> None:
    mock_settings.ATTIO_API_KEY = "atk_test_key"
    mock_settings.ATTIO_LIST_ID = "list-uuid"
    assert CrmService.is_configured() is True


# ---------------------------------------------------------------------------
# sync_contact -- no-op when unconfigured
# ---------------------------------------------------------------------------


@patch("app.services.crm_service.httpx")
@patch("app.services.crm_service.settings")
def test_sync_contact_noop_when_unconfigured(
    mock_settings: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    mock_settings.ATTIO_API_KEY = ""
    mock_settings.ATTIO_LIST_ID = ""

    svc = CrmService()
    svc.sync_contact(email="user@example.com")

    mock_httpx.put.assert_not_called()
    mock_httpx.post.assert_not_called()


# ---------------------------------------------------------------------------
# sync_contact -- happy path
# ---------------------------------------------------------------------------


_ASSERT_RESPONSE = {
    "data": {
        "id": {
            "workspace_id": "ws-123",
            "object_id": "obj-456",
            "record_id": "rec-789",
        },
        "created_at": "2026-04-22T10:00:00Z",
    },
}


@patch("app.services.crm_service.httpx")
@patch("app.services.crm_service.settings")
def test_sync_contact_asserts_person_and_adds_to_list(
    mock_settings: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    mock_settings.ATTIO_API_KEY = "atk_test_key"
    mock_settings.ATTIO_LIST_ID = "list-uuid"

    put_resp = MagicMock()
    put_resp.json.return_value = _ASSERT_RESPONSE
    mock_httpx.put.return_value = put_resp

    post_resp = MagicMock()
    mock_httpx.post.return_value = post_resp

    svc = CrmService()
    svc.sync_contact(email="user@example.com")

    # Step 1: assert person by email only
    mock_httpx.put.assert_called_once()
    put_kwargs = mock_httpx.put.call_args
    assert "objects/people/records" in put_kwargs[0][0]
    assert put_kwargs[1]["params"] == {"matching_attribute": "email_addresses"}
    body = put_kwargs[1]["json"]
    assert body["data"]["values"]["email_addresses"] == ["user@example.com"]
    assert "name" not in body["data"]["values"]
    assert "Bearer atk_test_key" in put_kwargs[1]["headers"]["Authorization"]

    # Step 2: add to list
    mock_httpx.post.assert_called_once()
    post_kwargs = mock_httpx.post.call_args
    assert "lists/list-uuid/entries" in post_kwargs[0][0]
    entry_body = post_kwargs[1]["json"]
    assert entry_body["data"]["parent_object"] == "people"
    assert entry_body["data"]["parent_record_id"] == "rec-789"


# ---------------------------------------------------------------------------
# sync_contact -- error propagation
# ---------------------------------------------------------------------------


@patch("app.services.crm_service.httpx")
@patch("app.services.crm_service.settings")
def test_sync_contact_raises_on_assert_failure(
    mock_settings: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    mock_settings.ATTIO_API_KEY = "atk_test_key"
    mock_settings.ATTIO_LIST_ID = "list-uuid"
    mock_httpx.HTTPStatusError = httpx.HTTPStatusError

    put_resp = MagicMock()
    put_resp.raise_for_status.side_effect = httpx.HTTPStatusError("422", request=MagicMock(), response=MagicMock())
    mock_httpx.put.return_value = put_resp

    svc = CrmService()
    with pytest.raises(httpx.HTTPStatusError):
        svc.sync_contact(email="bad@example.com")

    mock_httpx.post.assert_not_called()


@patch("app.services.crm_service.httpx")
@patch("app.services.crm_service.settings")
def test_sync_contact_raises_on_list_entry_failure(
    mock_settings: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    mock_settings.ATTIO_API_KEY = "atk_test_key"
    mock_settings.ATTIO_LIST_ID = "list-uuid"
    mock_httpx.HTTPStatusError = httpx.HTTPStatusError

    put_resp = MagicMock()
    put_resp.json.return_value = _ASSERT_RESPONSE
    mock_httpx.put.return_value = put_resp

    post_resp = MagicMock()
    post_resp.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
    mock_httpx.post.return_value = post_resp

    svc = CrmService()
    with pytest.raises(httpx.HTTPStatusError):
        svc.sync_contact(email="user@example.com")


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@patch("app.services.crm_service.httpx")
@patch("app.services.crm_service.settings")
def test_celery_task_syncs_contact(
    mock_settings: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    mock_settings.ATTIO_API_KEY = "atk_test_key"
    mock_settings.ATTIO_LIST_ID = "list-uuid"

    put_resp = MagicMock()
    put_resp.json.return_value = _ASSERT_RESPONSE
    mock_httpx.put.return_value = put_resp
    mock_httpx.post.return_value = MagicMock()

    from app.infrastructure.queue.tasks import sync_new_user_to_crm

    result = sync_new_user_to_crm("user@example.com")

    assert result["status"] == "synced"
    mock_httpx.put.assert_called_once()
    mock_httpx.post.assert_called_once()


@patch("app.services.crm_service.settings")
def test_celery_task_skips_when_unconfigured(mock_settings: MagicMock) -> None:
    mock_settings.ATTIO_API_KEY = ""
    mock_settings.ATTIO_LIST_ID = ""

    from app.infrastructure.queue.tasks import sync_new_user_to_crm

    result = sync_new_user_to_crm("user@example.com")

    assert result["status"] == "skipped"
    assert result["reason"] == "attio_not_configured"
