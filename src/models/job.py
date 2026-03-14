import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.job_status import JobStatus


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"), nullable=False, default=JobStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __init__(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_size_bytes: int,
        status: JobStatus = JobStatus.PENDING,
        error_message: str | None = None,
        result_path: str | None = None,
        id: uuid.UUID | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        self.id = id or uuid.uuid4()
        self.user_id = user_id
        self.filename = filename
        self.file_size_bytes = file_size_bytes
        self.status = status
        self.error_message = error_message
        self.result_path = result_path
        self.created_at = now
        self.updated_at = now
