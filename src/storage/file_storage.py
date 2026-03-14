import logging
import os
from pathlib import Path
from uuid import UUID

from src.core.config import settings

logger = logging.getLogger("upload-job-service")


class StorageUnavailableError(Exception):
    """Raised when the file storage backend cannot perform the requested I/O."""


def _input_dir(job_id: UUID) -> Path:
    return Path(settings.storage_path) / str(job_id) / "input"


def save_upload(job_id: UUID, file_bytes: bytes, filename: str) -> str:
    """Persist uploaded bytes to disk.

    Returns the absolute path of the saved file.
    Raises StorageUnavailableError on any I/O failure.
    """
    target_dir = _input_dir(job_id)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        target_path.write_bytes(file_bytes)
        logger.info(
            "File saved", extra={"job_id": str(job_id), "path": str(target_path)}
        )
        return str(target_path)
    except OSError as exc:
        logger.error("Storage write failed: %s", exc, extra={"job_id": str(job_id)})
        raise StorageUnavailableError(f"Could not write file: {exc}") from exc


def get_result_path(job_id: UUID) -> str:
    """Return the expected output path for a processed job.

    The path follows the convention: {STORAGE_PATH}/{job_id}/output/
    Existence of the path is not verified here — callers are responsible.
    """
    return str(Path(settings.storage_path) / str(job_id) / "output")


def delete_upload(job_id: UUID, filename: str) -> None:
    """Remove an uploaded file — used for cleanup on failed queue publish."""
    target = _input_dir(job_id) / filename
    try:
        if target.exists():
            os.remove(target)
    except OSError as exc:
        logger.warning(
            "Cleanup failed for %s: %s", target, exc, extra={"job_id": str(job_id)}
        )
