import logging
import signal
import time

import pika

from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("rendition.worker")

EXCHANGE = "rendition"
QUEUE = "jobs.encode"
ROUTING_KEY = "job.encode"


def connect_with_retry() -> pika.BlockingConnection:
    parameters = pika.URLParameters(settings.RABBITMQ_URL)
    last_error: Exception | None = None

    for attempt in range(1, settings.RABBITMQ_CONNECT_RETRY_COUNT + 1):
        try:
            return pika.BlockingConnection(parameters)
        except pika.exceptions.AMQPConnectionError as exc:
            last_error = exc
            sleep_seconds = min(attempt, 10)
            logger.warning(
                "rabbitmq unavailable; retrying",
                extra={"attempt": attempt, "sleep_seconds": sleep_seconds},
            )
            time.sleep(sleep_seconds)

    raise RuntimeError("failed to connect to RabbitMQ") from last_error


def setup_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)


def main() -> None:
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    connection = connect_with_retry()
    channel = connection.channel()
    setup_topology(channel)

    logger.info("worker ready; encoding processor not enabled yet")
    try:
        while not stopping:
            connection.process_data_events(time_limit=1)
    finally:
        connection.close()
        logger.info("worker stopped")


if __name__ == "__main__":
    main()
