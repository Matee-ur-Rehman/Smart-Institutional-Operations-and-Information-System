"""Test environment. This module MUST be imported before anything from `app` (conftest.py does it
first), because app.core.config reads the environment once at import time.

Default: in-memory SQLite, so `pytest` needs no PostgreSQL. To run against PostgreSQL instead:
    export TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/school_test_db
(use a SEPARATE test database, never the development one: every test wipes all tables).
"""
import os
import tempfile

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or "sqlite://"
os.environ["JWT_SECRET_KEY"] = "pytest-only-secret-key-0123456789abcdef"
os.environ["JWT_ACCESS_MINUTES"] = "30"
os.environ["JWT_REFRESH_DAYS"] = "7"
os.environ["CORS_ORIGINS"] = "http://localhost:5000"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="school_test_uploads_")
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["FCM_ENABLED"] = "false"
os.environ["FCM_CREDENTIALS_FILE"] = ""
os.environ["SEED_DEFAULT_PASSWORD"] = "TestPass#123"
