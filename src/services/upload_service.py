"""Upload service — validation and atomic job creation."""

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.queue import publish_job
from src.models.job import Job
from src.models.job_status import JobStatus
from src.storage.file_storage import delete_upload, save_upload

logger = logging.getLogger("upload-job-service")


def validate_mime_type(content_type: str) -> None:
    """Raise HTTP 422 if content_type is not in ALLOWED_MIME_TYPES."""
    if content_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de arquivo não permitido: {content_type}. "
            f"Tipos aceitos: {', '.join(settings.allowed_mime_types)}",
        )


def validate_size(size_bytes: int) -> None:
    """Raise HTTP 413 if size_bytes exceeds MAX_UPLOAD_SIZE_MB."""
    if size_bytes > settings.max_upload_size_bytes:
        max_mb = settings.max_upload_size_mb
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede o tamanho máximo de {max_mb} MB.",
        )


async def create_job(
    db: Session,
    user_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
) -> Job:
    """Atomically save the uploaded file, create a DB job, and publish to the queue.

    If RabbitMQ publish fails → DB is rolled back and the uploaded file is deleted.
    Raises StorageUnavailableError (→ 503) if storage cannot be written.
    Raises the queue exception after cleanup if publish fails.
    """
    # Create job object first so we have a job_id for the storage path
    job = Job(
        user_id=user_id,
        filename=filename,
        file_size_bytes=len(file_bytes),
        status=JobStatus.PENDING,
    )

    file_path = save_upload(job.id, file_bytes, filename)

    db.add(job)
    db.flush()  # write to DB without committing (allows rollback)

    try:
        await publish_job(job.id, user_id, file_path)
        db.commit()
        db.refresh(job)
        logger.info(
            "Job created",
            extra={
                "job_id": str(job.id),
                "user_id": str(user_id),
                "event": "job_created",
            },
        )
        return job
    except Exception:
        db.rollback()
        delete_upload(job.id, filename)
        raise
