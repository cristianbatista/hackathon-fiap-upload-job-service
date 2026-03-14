"""Unit tests for upload_service — validate_mime_type, validate_size, create_job."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.job_status import JobStatus

# ---------------------------------------------------------------------------
# validate_mime_type
# ---------------------------------------------------------------------------


def test_validate_mime_type_accepts_mp4():
    from src.services.upload_service import validate_mime_type

    validate_mime_type("video/mp4")  # should not raise


def test_validate_mime_type_accepts_avi():
    from src.services.upload_service import validate_mime_type

    validate_mime_type("video/avi")


def test_validate_mime_type_accepts_quicktime():
    from src.services.upload_service import validate_mime_type

    validate_mime_type("video/quicktime")


def test_validate_mime_type_accepts_mkv():
    from src.services.upload_service import validate_mime_type

    validate_mime_type("video/x-matroska")


def test_validate_mime_type_rejects_pdf():
    from fastapi import HTTPException

    from src.services.upload_service import validate_mime_type

    with pytest.raises(HTTPException) as exc_info:
        validate_mime_type("application/pdf")
    assert exc_info.value.status_code == 422


def test_validate_mime_type_rejects_image():
    from fastapi import HTTPException

    from src.services.upload_service import validate_mime_type

    with pytest.raises(HTTPException) as exc_info:
        validate_mime_type("image/jpeg")
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# validate_size
# ---------------------------------------------------------------------------


def test_validate_size_accepts_under_limit():
    from src.services.upload_service import validate_size

    validate_size(100 * 1024 * 1024)  # 100 MB — under default 200 MB


def test_validate_size_rejects_above_limit():
    from fastapi import HTTPException

    from src.services.upload_service import validate_size

    with pytest.raises(HTTPException) as exc_info:
        validate_size(201 * 1024 * 1024)  # 201 MB — over default 200 MB
    assert exc_info.value.status_code == 413


def test_validate_size_accepts_at_limit():
    from src.core.config import settings
    from src.services.upload_service import validate_size

    validate_size(settings.max_upload_size_bytes)  # exactly at limit


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_job_returns_pending_job():
    from src.services.upload_service import create_job

    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    user_id = uuid.uuid4()
    file_bytes = b"fake video content"
    filename = "test.mp4"

    with (
        patch(
            "src.services.upload_service.save_upload",
            return_value="/storage/fake/test.mp4",
        ),
        patch("src.services.upload_service.publish_job", new_callable=AsyncMock),
    ):
        job = await create_job(db, user_id, filename, file_bytes)

    assert job.status == JobStatus.PENDING
    assert job.user_id == user_id
    assert job.filename == filename
    assert job.file_size_bytes == len(file_bytes)


@pytest.mark.asyncio
async def test_create_job_rollback_on_queue_failure():
    from src.services.upload_service import create_job

    db = MagicMock()
    user_id = uuid.uuid4()
    file_bytes = b"fake video content"
    filename = "test.mp4"

    with (
        patch(
            "src.services.upload_service.save_upload",
            return_value="/storage/fake/test.mp4",
        ),
        patch(
            "src.services.upload_service.publish_job",
            new_callable=AsyncMock,
            side_effect=Exception("queue down"),
        ),
        patch("src.services.upload_service.delete_upload") as mock_delete,
        pytest.raises(Exception, match="queue down"),
    ):
        await create_job(db, user_id, filename, file_bytes)

    db.rollback.assert_called_once()
    # delete_upload called with (job_id, filename);
    # job_id is a UUID generated internally
    # (verified via call_args below)
    assert mock_delete.call_count == 1
    _, called_filename = mock_delete.call_args[0]
    assert called_filename == filename
