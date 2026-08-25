"""Shared test configuration.

Sets environment variables before any application code is imported.
These apply to both unit and integration test suites.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5433"
os.environ["POSTGRES_DB"] = "pandaprobe_test_db"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6380"
os.environ["AUTH_PROVIDER"] = "supabase"
# Constructing BillingService configures the Stripe SDK, which now refuses to
# run without a key. Tests patch the Stripe calls themselves, so a dummy value
# is enough — CI mounts no real secret.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
# Set explicitly (not just for CI): the webhook test signs payloads with this, and
# ``.env.development`` would otherwise supply a real secret locally, making the
# suite behave differently on a developer machine than in CI.
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
