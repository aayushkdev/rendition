from typing import Protocol

import pika

from core.config import settings
from core.queue.messages import (
    ENCODING_EXCHANGE,
    ENCODING_ROUTING_KEY,
    EncodingJobMessage,
)


class QueuePublishError(RuntimeError):
    pass


class JobQueuePublisher(Protocol):
    def publish_encoding_job(
        self,
        message: EncodingJobMessage,
        exchange: str,
        routing_key: str,
    ) -> None: ...


class RabbitMQJobQueuePublisher:
    def __init__(self, rabbitmq_url: str) -> None:
        self._rabbitmq_url = rabbitmq_url

    def publish_encoding_job(
        self,
        message: EncodingJobMessage,
        exchange: str,
        routing_key: str,
    ) -> None:
        connection: pika.BlockingConnection | None = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(self._rabbitmq_url))
            channel = connection.channel()
            setup_encoding_topology(channel)
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=message.model_dump_json().encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
                mandatory=True,
            )
        except Exception as exc:
            raise QueuePublishError("failed to publish encoding job") from exc
        finally:
            if connection is not None and connection.is_open:
                connection.close()


def setup_encoding_topology(
    channel: pika.adapters.blocking_connection.BlockingChannel,
) -> None:
    channel.exchange_declare(
        exchange=ENCODING_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )
    channel.queue_declare(queue="jobs.encode", durable=True)
    channel.queue_bind(
        queue="jobs.encode",
        exchange=ENCODING_EXCHANGE,
        routing_key=ENCODING_ROUTING_KEY,
    )


def get_job_queue_publisher() -> JobQueuePublisher:
    return RabbitMQJobQueuePublisher(settings.RABBITMQ_URL)
