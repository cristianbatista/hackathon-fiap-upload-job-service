"""Integration test for queue message after POST /jobs.

Requires a live RabbitMQ instance. Skip if RABBITMQ_URL not set or unreachable.
Run via: pytest tests/integration/ -m integration
"""

import io
import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "")
ALGORITHM = "HS256"
TEST_SECRET = "test-secret-key-for-upload-service"


def make_token(user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    return jwt.encode({"sub": str(uid)}, TEST_SECRET, algorithm=ALGORITHM)


@pytest.mark.skipif(
    not RABBITMQ_URL,
    reason="RABBITMQ_URL not set — skipping live queue integration test",
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_job_publishes_message_to_queue():
    """After POST /jobs succeeds, a message with correct job_id appears in the queue."""
    import aio_pika

    from src.main import app

    user_id = uuid.uuid4()
    token = make_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    fake_job_id = uuid.uuid4()
    fake_job = MagicMock()
    fake_job.id = fake_job_id
    fake_job.status.value = "PENDING"

    # Purge queue before test
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("video.processing", durable=True)
        await queue.purge()

    with (
        patch("src.core.auth.settings") as mock_settings,
        patch(
            "src.services.upload_service.create_job",
            new_callable=AsyncMock,
            return_value=fake_job,
        ),
    ):
        mock_settings.jwt_secret = TEST_SECRET
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/jobs",
            files=[("file", ("test.mp4", io.BytesIO(b"video"), "video/mp4"))],
            headers=headers,
        )

    assert response.status_code == 202
    returned_job_id = response.json()["job_id"]

    # Consume one message from the queue and verify payload
    connection2 = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection2:
        channel2 = await connection2.channel()
        queue2 = await channel2.declare_queue("video.processing", durable=True)
        msg = await queue2.get(timeout=5, fail=False)
        assert msg is not None, "No message found in queue after POST /jobs"
        payload = json.loads(msg.body)
        assert payload["job_id"] == returned_job_id
        await msg.ack()
