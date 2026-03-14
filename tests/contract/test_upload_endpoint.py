"""Contract tests for POST /jobs — upload endpoint."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.main import app

TEST_SECRET = "test-secret-key-for-upload-service"
ALGORITHM = "HS256"


def make_token(user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    payload = {"sub": str(uid)}
    return jwt.encode(payload, TEST_SECRET, algorithm=ALGORITHM)


def make_upload_file(content: bytes = b"fake video", filename: str = "test.mp4"):
    return ("file", (filename, io.BytesIO(content), "video/mp4"))


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_headers():
    token = make_token()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_upload_valid_video_returns_202(client, auth_headers):
    job_id = uuid.uuid4()
    fake_job = MagicMock()
    fake_job.id = job_id
    fake_job.status.value = "PENDING"

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch(
            "src.services.upload_service.create_job",
            new_callable=AsyncMock,
            return_value=fake_job,
        ),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.post(
            "/jobs",
            files=[make_upload_file()],
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"


def test_upload_without_jwt_returns_401(client):
    response = client.post(
        "/jobs",
        files=[make_upload_file()],
    )
    assert response.status_code == 401


def test_upload_invalid_mime_returns_422(client, auth_headers):
    with patch("src.core.auth.settings") as mock_settings:
        mock_settings.jwt_secret = TEST_SECRET
        response = client.post(
            "/jobs",
            files=[
                ("file", ("doc.pdf", io.BytesIO(b"pdf content"), "application/pdf"))
            ],
            headers=auth_headers,
        )
    assert response.status_code == 422


def test_upload_oversized_file_returns_413(client, auth_headers):
    with (
        patch("src.core.auth.settings") as mock_settings,
        patch("src.core.config.settings") as config_mock,
    ):
        mock_settings.jwt_secret = TEST_SECRET
        config_mock.jwt_secret = TEST_SECRET
        config_mock.max_upload_size_bytes = 10  # 10 bytes limit for test
        config_mock.allowed_mime_types = [
            "video/mp4",
            "video/avi",
            "video/quicktime",
            "video/x-matroska",
        ]

        with patch("src.services.upload_service.settings", config_mock):
            response = client.post(
                "/jobs",
                files=[
                    make_upload_file(content=b"x" * 20)
                ],  # 20 bytes > 10 bytes limit
                headers=auth_headers,
            )
    assert response.status_code == 413


def test_upload_with_invalid_token_returns_401(client):
    response = client.post(
        "/jobs",
        files=[make_upload_file()],
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert response.status_code == 401
