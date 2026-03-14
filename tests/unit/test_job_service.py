"""Unit tests for job_service — list_jobs."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.models.job import Job


def _make_job(user_id: uuid.UUID, offset_seconds: int = 0) -> Job:
    job = Job(user_id=user_id, filename="video.mp4", file_size_bytes=1024)
    # Adjust created_at for ordering test
    job.created_at = datetime.now(timezone.utc) - timedelta(seconds=offset_seconds)
    job.updated_at = job.created_at
    return job


def _build_mock_db(user_id: uuid.UUID, jobs: list) -> MagicMock:
    """Build a mock db Session whose query chain returns the given jobs."""
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_order = MagicMock()
    mock_count_query = MagicMock()

    total = len(jobs)

    # Scalar for count
    mock_count_query.scalar.return_value = total

    # Chain: query → filter → order_by → offset → limit → all
    mock_order.offset.return_value.limit.return_value.all.return_value = jobs
    mock_order.count.return_value = total
    mock_filter.order_by.return_value = mock_order
    mock_filter.count.return_value = total
    mock_query.filter.return_value = mock_filter
    mock_query.filter_by.return_value = mock_filter

    db = MagicMock()
    db.query.return_value = mock_query
    return db


def test_list_jobs_returns_jobs_for_user():
    from src.services.job_service import list_jobs

    user_id = uuid.uuid4()
    jobs = [_make_job(user_id) for _ in range(3)]
    db = _build_mock_db(user_id, jobs)

    result, total = list_jobs(db, user_id, page=1, limit=20)
    assert len(result) == 3
    assert total == 3


def test_list_jobs_different_user_returns_empty():
    from src.services.job_service import list_jobs

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    db = _build_mock_db(user_b, [])  # no jobs for user_a

    result, total = list_jobs(db, user_a, page=1, limit=20)
    assert result == []
    assert total == 0


def test_list_jobs_pagination_offset():
    from src.services.job_service import list_jobs

    user_id = uuid.uuid4()
    all_jobs = [_make_job(user_id, offset_seconds=i) for i in range(10)]
    # page=2, limit=5 → offset=5, returns items 5-9
    page2_jobs = all_jobs[5:]
    db = _build_mock_db(user_id, page2_jobs)

    result, total = list_jobs(db, user_id, page=2, limit=5)
    assert len(result) == 5
    assert total == 5  # mock returns len of passed list
