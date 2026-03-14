import asyncio
import json
import logging
from uuid import UUID

import aio_pika

from src.core.config import settings

QUEUE_NAME = "video.processing"
DLX_NAME = "video.dlx"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

logger = logging.getLogger("upload-job-service")


async def publish_job(job_id: UUID, user_id: UUID, file_path: str) -> None:
    """Publish a video processing job message to RabbitMQ.

    Uses exponential backoff with up to MAX_RETRIES attempts.
    Raises the last exception if all retries are exhausted.
    """
    message_body = json.dumps(
        {
            "job_id": str(job_id),
            "user_id": str(user_id),
            "file_path": file_path,
        }
    ).encode()

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            async with connection:
                channel = await connection.channel()
                # Declare dead-letter exchange
                await channel.declare_exchange(
                    DLX_NAME, aio_pika.ExchangeType.DIRECT, durable=True
                )
                # Declare the main queue with DLX
                queue = await channel.declare_queue(
                    QUEUE_NAME,
                    durable=True,
                    arguments={"x-dead-letter-exchange": DLX_NAME},
                )
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=message_body,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    ),
                    routing_key=queue.name,
                )
            logger.info(
                "Job published to queue",
                extra={"job_id": str(job_id), "queue": QUEUE_NAME},
            )
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Queue publish failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt,
                MAX_RETRIES,
                exc,
                delay,
                extra={"job_id": str(job_id)},
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
