import uuid

from sqlalchemy.orm import Session

from src.models.job import Job


def list_jobs(
    db: Session,
    user_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Job], int]:
    """Return paginated jobs for a specific user, ordered by created_at descending."""
    base_query = db.query(Job).filter(Job.user_id == user_id)
    total: int = base_query.count()
    offset = (page - 1) * limit
    jobs: list[Job] = (
        base_query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    )
    return jobs, total
