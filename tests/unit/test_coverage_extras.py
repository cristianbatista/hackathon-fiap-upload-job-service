"""Extra coverage tests for logging, queue, auth, health, and main."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_json_formatter_basic_format():
    import json

    from src.core.logging import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["message"] == "hello world"
    assert data["service"] == "upload-job-service"
    assert "timestamp" in data
    assert "trace_id" in data


def test_json_formatter_with_job_id():
    import json

    from src.core.logging import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="processing",
        args=(),
        exc_info=None,
    )
    record.job_id = "abc-123"
    record.trace_id = "trace-xyz"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["job_id"] == "abc-123"
    assert data["trace_id"] == "trace-xyz"


def test_json_formatter_with_exception():
    import json

    from src.core.logging import JSONFormatter

    formatter = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="error",
        args=(),
        exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert "exception" in data


def test_get_logger_returns_logger():
    from src.core.logging import get_logger

    logger = get_logger("test-service")
    assert isinstance(logger, logging.Logger)
    # Second call reuses same logger (no duplicate handlers)
    logger2 = get_logger("test-service")
    assert logger is logger2


def test_setup_logging_sets_level():
    from src.core.logging import setup_logging

    setup_logging("WARNING")
    root = logging.getLogger()
    assert root.level == logging.WARNING


# ---------------------------------------------------------------------------
# Auth — additional branches
# ---------------------------------------------------------------------------


def test_decode_access_token_success():
    from src.core.auth import decode_access_token

    user_id = uuid.uuid4()
    token = jwt.encode({"sub": str(user_id)}, "test-secret-key", algorithm="HS256")

    with patch("src.core.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key"
        result = decode_access_token(token)

    assert result == user_id


def test_decode_access_token_expired():
    from fastapi import HTTPException
    from jose import jwt as jose_jwt

    from src.core.auth import decode_access_token

    user_id = uuid.uuid4()
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    token = jose_jwt.encode(
        {"sub": str(user_id), "exp": past},
        "test-secret-key",
        algorithm="HS256",
    )

    with patch("src.core.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_decode_access_token_missing_sub():
    from fastapi import HTTPException

    from src.core.auth import decode_access_token

    token = jwt.encode({}, "test-secret-key", algorithm="HS256")

    with patch("src.core.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_decode_access_token_invalid_uuid_sub():
    from fastapi import HTTPException

    from src.core.auth import decode_access_token

    token = jwt.encode({"sub": "not-a-uuid"}, "test-secret-key", algorithm="HS256")

    with patch("src.core.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_ok():
    from src.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "upload-job-service"}


# ---------------------------------------------------------------------------
# Queue — publish_job (mocked aio_pika)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_job_success():
    from src.core.queue import publish_job

    job_id = uuid.uuid4()
    user_id = uuid.uuid4()
    file_path = "/storage/test/input/video.mp4"

    mock_channel = AsyncMock()
    mock_queue = AsyncMock()
    mock_queue.name = "video.processing"
    mock_channel.declare_queue.return_value = mock_queue
    mock_channel.declare_exchange.return_value = AsyncMock()
    mock_channel.default_exchange = AsyncMock()

    mock_connection = AsyncMock()
    mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_connection.__aexit__ = AsyncMock(return_value=False)
    mock_connection.channel = AsyncMock(return_value=mock_channel)

    with (
        patch("src.core.queue.settings") as mock_settings,
        patch("aio_pika.connect_robust", return_value=mock_connection),
    ):
        mock_settings.rabbitmq_url = "amqp://guest:guest@localhost:5672/"
        await publish_job(job_id, user_id, file_path)

    mock_channel.default_exchange.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_job_retries_on_failure():
    from src.core.queue import publish_job

    job_id = uuid.uuid4()
    user_id = uuid.uuid4()
    file_path = "/storage/test/input/video.mp4"

    with (
        patch("src.core.queue.settings") as mock_settings,
        patch("aio_pika.connect_robust", side_effect=ConnectionError("refused")),
        patch("asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(ConnectionError),
    ):
        mock_settings.rabbitmq_url = "amqp://guest:guest@localhost:5672/"
        await publish_job(job_id, user_id, file_path)


# ---------------------------------------------------------------------------
# Main app — unhandled exception handler
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_500():
    from src.main import app

    @app.get("/test-crash")
    async def crash():
        raise RuntimeError("unexpected")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-crash")
    assert response.status_code == 500
