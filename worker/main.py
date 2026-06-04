import logging
import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pika
from pika import exceptions as pika_exceptions
from pydantic import ValidationError

from core.config import settings
from core.db.session import SessionLocal
from core.queue.messages import EncodingJobMessage
from core.queue.publisher import setup_encoding_topology
from worker.processor import (
    EncodingProcessor,
    SessionScope,
    FfmpegEncodingProcessor,
    WorkerMessageAction,
    process_encoding_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("rendition.worker")


@contextmanager
def session_scope() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def connect_with_retry() -> pika.BlockingConnection:
    parameters = pika.URLParameters(settings.RABBITMQ_URL)
    last_error: Exception | None = None

    for attempt in range(1, settings.RABBITMQ_CONNECT_RETRY_COUNT + 1):
        try:
            return pika.BlockingConnection(parameters)
        except pika_exceptions.AMQPConnectionError as exc:
            last_error = exc
            sleep_seconds = min(attempt, 10)
            logger.warning(
                "rabbitmq unavailable; retrying",
                extra={"attempt": attempt, "sleep_seconds": sleep_seconds},
            )
            time.sleep(sleep_seconds)

    raise RuntimeError("failed to connect to RabbitMQ") from last_error


def handle_delivery(
    channel,
    method,
    body: bytes,
    session_scope: SessionScope,
    processor: EncodingProcessor,
) -> None:
    try:
        message = EncodingJobMessage.model_validate_json(body)
    except ValidationError:
        logger.exception("invalid encoding job message")
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        return

    try:
        action = process_encoding_message(
            session_scope=session_scope,
            message=message,
            processor=processor,
        )
    except Exception:
        logger.exception(
            "encoding job processing crashed",
            extra={"job_id": str(message.job_id)},
        )
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return

    if action == WorkerMessageAction.ack:
        channel.basic_ack(delivery_tag=method.delivery_tag)
    elif action == WorkerMessageAction.requeue:
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    else:
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)


def main() -> None:
    stopping = False
    processor = FfmpegEncodingProcessor()

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    connection = connect_with_retry()
    channel = connection.channel()
    setup_encoding_topology(channel, queue_name=settings.WORKER_QUEUE_NAME)
    channel.basic_qos(prefetch_count=settings.WORKER_PREFETCH_COUNT)

    channel.basic_consume(
        queue=settings.WORKER_QUEUE_NAME,
        on_message_callback=lambda channel, method, _properties, body: handle_delivery(
            channel=channel,
            method=method,
            body=body,
            session_scope=session_scope,
            processor=processor,
        ),
        auto_ack=False,
    )

    logger.info(
        "worker ready",
        extra={
            "queue": settings.WORKER_QUEUE_NAME,
            "prefetch_count": settings.WORKER_PREFETCH_COUNT,
        },
    )
    try:
        while not stopping:
            connection.process_data_events(time_limit=1)
    finally:
        connection.close()
        logger.info("worker stopped")


if __name__ == "__main__":
    main()
