from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol, TYPE_CHECKING

import pika

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel

from core.config import settings
from core.queue.messages import (
    ENCODING_DEAD_LETTER_EXCHANGE,
    ENCODING_DEAD_LETTER_ROUTING_KEY,
    ENCODING_EXCHANGE,
    ENCODING_ROUTING_KEY,
    EncodingJobMessage,
)


class QueuePublishError(RuntimeError):
    pass


class JobQueuePublisher(Protocol):
    def session(self) -> AbstractContextManager["JobQueuePublisher"]: ...

    def publish_encoding_job(
        self,
        message: EncodingJobMessage,
        exchange: str,
        routing_key: str,
    ) -> None: ...


class RabbitMQJobQueuePublisher:
    def __init__(self, rabbitmq_url: str) -> None:
        self._rabbitmq_url = rabbitmq_url

    @contextmanager
    def session(self) -> Iterator["RabbitMQJobQueueSession"]:
        connection: pika.BlockingConnection | None = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(self._rabbitmq_url))
            channel = connection.channel()
            setup_encoding_topology(channel, queue_name=settings.WORKER_QUEUE_NAME)
            yield RabbitMQJobQueueSession(channel)
        except Exception as exc:
            raise QueuePublishError("failed to publish encoding job") from exc
        finally:
            if connection is not None and connection.is_open:
                connection.close()

    def publish_encoding_job(
        self,
        message: EncodingJobMessage,
        exchange: str,
        routing_key: str,
    ) -> None:
        with self.session() as session:
            session.publish_encoding_job(message, exchange, routing_key)


class RabbitMQJobQueueSession:
    def __init__(self, channel: "BlockingChannel"):
        self._channel = channel

    @contextmanager
    def session(self) -> Iterator["RabbitMQJobQueueSession"]:
        yield self

    def publish_encoding_job(
        self,
        message: EncodingJobMessage,
        exchange: str,
        routing_key: str,
    ) -> None:
        self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message.model_dump_json().encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
            mandatory=True,
        )


def setup_encoding_topology(
    channel: "BlockingChannel",
    queue_name: str,
) -> None:
    channel.exchange_declare(
        exchange=ENCODING_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )
    channel.exchange_declare(
        exchange=ENCODING_DEAD_LETTER_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )
    dead_letter_queue_name = f"{queue_name}.dlq"
    channel.queue_declare(queue=dead_letter_queue_name, durable=True)
    channel.queue_bind(
        queue=dead_letter_queue_name,
        exchange=ENCODING_DEAD_LETTER_EXCHANGE,
        routing_key=ENCODING_DEAD_LETTER_ROUTING_KEY,
    )
    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": ENCODING_DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": ENCODING_DEAD_LETTER_ROUTING_KEY,
        },
    )
    channel.queue_bind(
        queue=queue_name,
        exchange=ENCODING_EXCHANGE,
        routing_key=ENCODING_ROUTING_KEY,
    )


def get_job_queue_publisher() -> JobQueuePublisher:
    return RabbitMQJobQueuePublisher(settings.RABBITMQ_URL)
