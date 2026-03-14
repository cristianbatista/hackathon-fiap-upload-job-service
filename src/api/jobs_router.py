import logging
import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from src.api.schemas import JobListResponse, JobSummary, UploadResponse
from src.core.auth import decode_access_token, oauth2_scheme
from src.core.database import get_db
from src.services import download_service, job_service, upload_service

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger("upload-job-service")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    return decode_access_token(token)


# ---------------------------------------------------------------------------
# US1 — POST /jobs
# ---------------------------------------------------------------------------


@router.post("", status_code=202, response_model=UploadResponse)
async def upload_video(
    file: UploadFile,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    upload_service.validate_mime_type(file.content_type or "")
    file_bytes = await file.read()
    upload_service.validate_size(len(file_bytes))

    job = await upload_service.create_job(
        db, user_id, file.filename or "upload", file_bytes
    )

    logger.info(
        "Upload received",
        extra={"job_id": str(job.id), "user_id": str(user_id), "event": "job_created"},
    )
    return JSONResponse(
        status_code=202,
        content={"job_id": str(job.id), "status": job.status.value},
    )


# ---------------------------------------------------------------------------
# US2 — GET /jobs
# ---------------------------------------------------------------------------


@router.get("", response_model=JobListResponse)
def list_jobs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobListResponse:
    jobs, total = job_service.list_jobs(db, user_id, page, limit)
    return JobListResponse(
        jobs=[JobSummary.from_job(j) for j in jobs],
        total=total,
        page=page,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# US3 — GET /jobs/{job_id}/download
# ---------------------------------------------------------------------------


@router.get("/{job_id}/download")
def download_job(
    job_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = download_service.get_job_for_download(db, job_id, user_id)
    logger.info(
        "Download served",
        extra={
            "job_id": str(job_id),
            "user_id": str(user_id),
            "event": "download_served",
        },
    )
    return FileResponse(
        path=job.result_path,
        media_type="application/zip",
        filename=f"frames_{job_id}.zip",
        headers={"Content-Disposition": f'attachment; filename="frames_{job_id}.zip"'},
    )
