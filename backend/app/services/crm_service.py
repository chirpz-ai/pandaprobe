"""Attio CRM integration for recording new signups.

Implements a two-step flow against the Attio v2 REST API:
1. Assert (upsert) a Person record matched by email.
2. Add that record to a designated list for outreach tracking.

When ``ATTIO_API_KEY`` is empty (the default for self-hosted
deployments), every public method is a silent no-op.
"""

import httpx

from app.logging import logger
from app.registry.settings import settings

_BASE_URL = "https://api.attio.com/v2"
_TIMEOUT = 15.0


class CrmService:
    """Stateless adapter around the Attio v2 REST API."""

    @staticmethod
    def is_configured() -> bool:
        """Return *True* when both the API key and list ID are present."""
        return bool(settings.ATTIO_API_KEY and settings.ATTIO_LIST_ID)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.ATTIO_API_KEY}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync_contact(self, *, email: str) -> None:
        """Assert a Person record in Attio and add it to the target list."""
        if not self.is_configured():
            return

        record_id = self._assert_person(email=email)
        self._add_to_list(record_id=record_id)
        logger.info("attio_contact_synced", email=email, record_id=record_id)

    # ------------------------------------------------------------------
    # Internal API calls
    # ------------------------------------------------------------------

    def _assert_person(self, *, email: str) -> str:
        """Create or update a Person record, returning the ``record_id``."""
        url = f"{_BASE_URL}/objects/people/records"
        payload = {
            "data": {
                "values": {
                    "email_addresses": [email],
                },
            },
        }

        resp = httpx.put(
            url,
            headers=self._headers(),
            json=payload,
            params={"matching_attribute": "email_addresses"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()

        record_id: str = resp.json()["data"]["id"]["record_id"]
        logger.debug("attio_person_asserted", email=email, record_id=record_id)
        return record_id

    def _add_to_list(self, *, record_id: str) -> None:
        """Add an existing Person record to the configured Attio list."""
        url = f"{_BASE_URL}/lists/{settings.ATTIO_LIST_ID}/entries"
        payload = {
            "data": {
                "parent_object": "people",
                "parent_record_id": record_id,
            },
        }

        resp = httpx.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        logger.debug("attio_list_entry_created", record_id=record_id, list_id=settings.ATTIO_LIST_ID)
