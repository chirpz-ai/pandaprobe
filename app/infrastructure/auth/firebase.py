"""Firebase auth adapter for managed cloud deployments.

Uses the Firebase Admin SDK to verify ID tokens.  Initialises using
``GOOGLE_CLOUD_PROJECT_ID`` and Application Default Credentials (ADC),
which automatically resolves the right credential source:

- **Local dev**: ``gcloud auth application-default login``
- **Cloud Run**: attached service account
- **Explicit**: ``GOOGLE_APPLICATION_CREDENTIALS`` env var
"""

from __future__ import annotations

import os
import threading

import firebase_admin

from app.infrastructure.auth.base import AuthAdapter, AuthClaims
from app.logging import logger
from app.registry.exceptions import AuthenticationError
from app.registry.settings import settings

_firebase_app: firebase_admin.App | None = None
_firebase_lock = threading.Lock()


def _ensure_firebase_app() -> firebase_admin.App:
    """Lazily initialise the Firebase Admin SDK (once per process).

    Uses Application Default Credentials with an explicit project ID
    so no service-account JSON file is needed in most deployments.
    """
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    with _firebase_lock:
        if _firebase_app is not None:
            return _firebase_app

        project_id = settings.GOOGLE_CLOUD_PROJECT_ID

        try:
            if project_id:
                _firebase_app = firebase_admin.initialize_app(
                    options={"projectId": project_id},
                )
                logger.info("firebase_initialized", project_id=project_id)
            else:
                _firebase_app = firebase_admin.initialize_app()
                logger.info("firebase_initialized", project_id="auto-detected")

            _log_credential_source()
            return _firebase_app

        except Exception as exc:
            logger.error("firebase_init_failed", error=str(exc))
            raise AuthenticationError(f"Firebase SDK failed to initialise: {exc}")


def _log_credential_source() -> None:
    """Log which credential source the SDK picked up (for debugging)."""
    google_app_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    k_service = os.environ.get("K_SERVICE")

    if google_app_creds:
        logger.info("firebase_creds_source", source="GOOGLE_APPLICATION_CREDENTIALS", path=google_app_creds)
    elif k_service:
        logger.info("firebase_creds_source", source="cloud_run_service_account", service=k_service)
    else:
        logger.info("firebase_creds_source", source="application_default_credentials")


class FirebaseAdapter(AuthAdapter):
    """Verify Firebase ID tokens via the Admin SDK."""

    def verify_token(self, token: str) -> AuthClaims:
        """Validate a Firebase ID token and return normalised claims."""
        app = _ensure_firebase_app()

        from firebase_admin import auth as fb_auth

        try:
            decoded = fb_auth.verify_id_token(token, app=app)
        except fb_auth.ExpiredIdTokenError:
            raise AuthenticationError("Token has expired.")
        except fb_auth.InvalidIdTokenError as exc:
            raise AuthenticationError(f"Invalid token: {exc}")
        except Exception as exc:
            raise AuthenticationError(f"Firebase verification failed: {exc}")

        if not decoded.get("uid"):
            raise AuthenticationError("Invalid token: missing user ID.")
        if not decoded.get("email"):
            raise AuthenticationError("Invalid token: missing email.")

        return AuthClaims(
            sub=decoded["uid"],
            email=decoded["email"],
            display_name=decoded.get("name", ""),
        )
