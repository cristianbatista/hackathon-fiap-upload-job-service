"""Shared pytest fixtures and configuration for upload-job-service tests."""

import os

# Set required env vars before any src module is imported.
# These are overridden per-test where needed via patch("src.core.auth.settings").
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-upload-service")
