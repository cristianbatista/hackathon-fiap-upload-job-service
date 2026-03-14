"""Contract tests for GET /jobs — job listing endpoint."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.main import app
from src.models.job_status import JobStatus

TEST_SECRET = "test-secret-key-for-upload-service"
ALGORITHM = "HS256"


def make_token(user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    return jwt.encode({"sub": str(uid)}, TEST_SECRET, algorithm=ALGORITHM)


def make_fake_job(
    user_id: uuid.UUID, status: JobStatus = JobStatus.PENDING
) -> MagicMock:
    job = MagicMock()
    job.id = uuid.uuid4()
    job.user_id = user_id
    job.filename = "video.mp4"
    job.status = status
    job.error_message = None
    job.created_at = datetime.now(timezone.utc)
    return job


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_list_jobs_without_jwt_returns_401(client):
    response = client.get("/jobs")
    assert response.status_code == 401


def test_list_jobs_with_valid_jwt_returns_200(client):
    user_id = uuid.uuid4()
    token = make_token(user_id)
    fake_jobs = [make_fake_job(user_id)]

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch("src.services.job_service.list_jobs", return_value=(fake_jobs, 1)),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get("/jobs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert data["total"] == 1
    assert len(data["jobs"]) == 1


def test_list_jobs_empty_for_new_user(client):
    user_id = uuid.uuid4()
    token = make_token(user_id)

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch("src.services.job_service.list_jobs", return_value=([], 0)),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get("/jobs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["jobs"] == []
    assert data["total"] == 0


def test_list_jobs_error_message_present_for_error_status(client):
    user_id = uuid.uuid4()
    token = make_token(user_id)
    fake_job = make_fake_job(user_id, status=JobStatus.ERROR)
    fake_job.error_message = "Processing failed: codec not supported"

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch("src.services.job_service.list_jobs", return_value=([fake_job], 1)),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get("/jobs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["jobs"][0]["error_message"] == "Processing failed: codec not supported"
    assert data["jobs"][0]["status"] == "ERROR"


def test_user_a_cannot_see_user_b_jobs(client):
    """list_jobs filters by user_id from JWT.

    User A always gets empty list if B owns all jobs.
    """
    user_a = uuid.uuid4()
    token_a = make_token(user_a)

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch("src.services.job_service.list_jobs", return_value=([], 0)) as mock_list,
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get("/jobs", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 200
    assert response.json()["total"] == 0
    # Verify list_jobs was called with user_a's id
    called_user_id = mock_list.call_args[0][1]
    assert called_user_id == user_a
