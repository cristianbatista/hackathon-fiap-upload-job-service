"""Unit tests for file_storage.

Covers save_upload, get_result_path, StorageUnavailableError.
"""

import uuid
from unittest.mock import patch

import pytest

from src.storage.file_storage import (
    StorageUnavailableError,
    delete_upload,
    get_result_path,
    save_upload,
)


def test_save_upload_creates_file(tmp_path):
    job_id = uuid.uuid4()
    file_bytes = b"video content"
    filename = "video.mp4"

    with patch("src.storage.file_storage.settings") as mock_settings:
        mock_settings.storage_path = str(tmp_path)
        result = save_upload(job_id, file_bytes, filename)

    expected = tmp_path / str(job_id) / "input" / filename
    assert expected.exists()
    assert expected.read_bytes() == file_bytes
    assert result == str(expected)


def test_save_upload_raises_storage_unavailable_on_oserror():
    job_id = uuid.uuid4()
    file_bytes = b"video content"
    filename = "video.mp4"

    with patch("src.storage.file_storage.settings") as mock_settings:
        mock_settings.storage_path = "/nonexistent_readonly_path"
        with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
            with pytest.raises(StorageUnavailableError):
                save_upload(job_id, file_bytes, filename)


def test_get_result_path_returns_expected_path(tmp_path):
    job_id = uuid.uuid4()
    with patch("src.storage.file_storage.settings") as mock_settings:
        mock_settings.storage_path = str(tmp_path)
        result = get_result_path(job_id)

    expected = str(tmp_path / str(job_id) / "output")
    assert result == expected


def test_delete_upload_removes_file(tmp_path):
    job_id = uuid.uuid4()
    filename = "video.mp4"
    target_dir = tmp_path / str(job_id) / "input"
    target_dir.mkdir(parents=True)
    target_file = target_dir / filename
    target_file.write_bytes(b"data")
    assert target_file.exists()

    with patch("src.storage.file_storage.settings") as mock_settings:
        mock_settings.storage_path = str(tmp_path)
        delete_upload(job_id, filename)

    assert not target_file.exists()


def test_delete_upload_noop_if_file_missing(tmp_path):
    """delete_upload should not raise if file does not exist."""
    job_id = uuid.uuid4()
    with patch("src.storage.file_storage.settings") as mock_settings:
        mock_settings.storage_path = str(tmp_path)
        delete_upload(job_id, "notexistent.mp4")  # should not raise
