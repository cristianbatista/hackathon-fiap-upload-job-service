import uuid
from datetime import datetime

from pydantic import BaseModel

from src.models.job_status import JobStatus

# ---------------------------------------------------------------------------
# US1 — Upload
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    job_id: uuid.UUID
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# US2 — Listing
# ---------------------------------------------------------------------------


class JobSummary(BaseModel):
    job_id: uuid.UUID
    filename: str
    status: JobStatus
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_job(cls, job) -> "JobSummary":
        return cls(
            job_id=job.id,
            filename=job.filename,
            status=job.status,
            error_message=job.error_message,
            created_at=job.created_at,
        )


class JobListResponse(BaseModel):
    jobs: list[JobSummary]
    total: int
    page: int
    limit: int


# ---------------------------------------------------------------------------
# US3 — Download (no request body needed; response is FileResponse)
# ---------------------------------------------------------------------------


class DownloadJobResponse(BaseModel):
    """Not used as HTTP response body — here for documentation/test purposes."""

    job_id: uuid.UUID
    result_path: str
