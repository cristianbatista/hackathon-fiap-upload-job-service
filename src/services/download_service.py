import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.job import Job
from src.models.job_status import JobStatus


class JobNotFoundError(Exception):
    pass


class JobNotReadyError(Exception):
    pass


class JobFailedError(Exception):
    pass


def get_job_for_download(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> Job:
    """Retrieve a job for download, enforcing ownership and status checks.

    Raises:
        HTTPException(404) — job not found or belongs to another user
        HTTPException(409) — job is PENDING or PROCESSING (not yet ready)
        HTTPException(410) — job completed with ERROR status
    """
    job: Job | None = (
        db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job não encontrado",
        )

    if job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job ainda não foi concluído. Aguarde o processamento.",
        )

    if job.status == JobStatus.ERROR:
        error_msg = job.error_message or "erro desconhecido"
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Job falhou durante o processamento: {error_msg}",
        )

    return job
