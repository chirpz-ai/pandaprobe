"""Shared test configuration.

Sets environment variables before any application code is imported.
These apply to both unit and integration test suites.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_HOST"] = "localhost"
os.environ["AUTH_PROVIDER"] = "supabase"
