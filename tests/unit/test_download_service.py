"""Unit tests for download_service."""

import uuid
from unittest.mock import MagicMock

import pytest

from src.models.job_status import JobStatus


def _make_job(
    status: JobStatus, owner_id: uuid.UUID, result_path: str = "/storage/out.zip"
) -> MagicMock:
    job = MagicMock()
    job.id = uuid.uuid4()
    job.user_id = owner_id
    job.status = status
    job.result_path = result_path
    return job


def test_get_job_for_download_returns_done_job():
    from src.services.download_service import get_job_for_download

    user_id = uuid.uuid4()
    job = _make_job(JobStatus.DONE, user_id)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = job

    result = get_job_for_download(db, job.id, user_id)
    assert result is job


def test_get_job_for_download_raises_not_found_for_wrong_owner():
    from fastapi import HTTPException

    from src.services.download_service import get_job_for_download

    owner_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    job = _make_job(JobStatus.DONE, owner_id)
    db = MagicMock()
    # query returns None because filter includes user_id check
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_job_for_download(db, job.id, requester_id)
    assert exc_info.value.status_code == 404


def test_get_job_for_download_raises_not_found_for_unknown_job():
    from fastapi import HTTPException

    from src.services.download_service import get_job_for_download

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_job_for_download(db, uuid.uuid4(), uuid.uuid4())
    assert exc_info.value.status_code == 404


def test_get_job_for_download_raises_conflict_for_pending():
    from fastapi import HTTPException

    from src.services.download_service import get_job_for_download

    user_id = uuid.uuid4()
    job = _make_job(JobStatus.PENDING, user_id)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = job

    with pytest.raises(HTTPException) as exc_info:
        get_job_for_download(db, job.id, user_id)
    assert exc_info.value.status_code == 409


def test_get_job_for_download_raises_gone_for_error():
    from fastapi import HTTPException

    from src.services.download_service import get_job_for_download

    user_id = uuid.uuid4()
    job = _make_job(JobStatus.ERROR, user_id)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = job

    with pytest.raises(HTTPException) as exc_info:
        get_job_for_download(db, job.id, user_id)
    assert exc_info.value.status_code == 410
