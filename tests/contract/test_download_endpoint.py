"""Contract tests for GET /jobs/{job_id}/download."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
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
    status: JobStatus, user_id: uuid.UUID, result_path: str = "/tmp/frames.zip"
) -> MagicMock:
    job = MagicMock()
    job.id = uuid.uuid4()
    job.user_id = user_id
    job.status = status
    job.result_path = result_path
    return job


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_download_done_job_returns_200(tmp_path, client):
    user_id = uuid.uuid4()
    token = make_token(user_id)
    zip_file = tmp_path / "frames.zip"
    zip_file.write_bytes(b"PK fake zip content")
    fake_job = make_fake_job(JobStatus.DONE, user_id, str(zip_file))

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch(
            "src.services.download_service.get_job_for_download", return_value=fake_job
        ),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get(
            f"/jobs/{fake_job.id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "application/zip" in response.headers.get("content-type", "")


def test_download_pending_job_returns_409(client):
    user_id = uuid.uuid4()
    token = make_token(user_id)
    job_id = uuid.uuid4()

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch(
            "src.services.download_service.get_job_for_download",
            side_effect=HTTPException(status_code=409, detail="Job não concluído"),
        ),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get(
            f"/jobs/{job_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409


def test_download_other_user_job_returns_404(client):
    user_id = uuid.uuid4()
    token = make_token(user_id)
    job_id = uuid.uuid4()

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch(
            "src.services.download_service.get_job_for_download",
            side_effect=HTTPException(status_code=404, detail="Job não encontrado"),
        ),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get(
            f"/jobs/{job_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


def test_download_error_job_returns_410(client):
    user_id = uuid.uuid4()
    token = make_token(user_id)
    job_id = uuid.uuid4()

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch(
            "src.services.download_service.get_job_for_download",
            side_effect=HTTPException(status_code=410, detail="Job falhou"),
        ),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        response = client.get(
            f"/jobs/{job_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 410


def test_download_without_jwt_returns_401(client):
    job_id = uuid.uuid4()
    response = client.get(f"/jobs/{job_id}/download")
    assert response.status_code == 401
