import pytest
from uuid import UUID

from core.queue.messages import (
    ENCODING_DEAD_LETTER_EXCHANGE,
    ENCODING_DEAD_LETTER_ROUTING_KEY,
    ENCODING_EXCHANGE,
    ENCODING_ROUTING_KEY,
    EncodingJobMessage,
)
from core.queue.publisher import (
    QueuePublishError,
    RabbitMQJobQueuePublisher,
    RabbitMQJobQueueSession,
    setup_encoding_topology,
)
from tests.fakes import FakeBlockingChannel, FakeBlockingConnection


def test_setup_encoding_topology_declares_exchange_queue_and_binding():
    channel = FakeBlockingChannel()

    setup_encoding_topology(channel, queue_name="jobs.encode")

    assert channel.calls == [
        (
            "exchange_declare",
            {
                "exchange": ENCODING_EXCHANGE,
                "exchange_type": "direct",
                "durable": True,
            },
        ),
        (
            "exchange_declare",
            {
                "exchange": ENCODING_DEAD_LETTER_EXCHANGE,
                "exchange_type": "direct",
                "durable": True,
            },
        ),
        ("queue_declare", {"queue": "jobs.encode.dlq", "durable": True}),
        (
            "queue_bind",
            {
                "queue": "jobs.encode.dlq",
                "exchange": ENCODING_DEAD_LETTER_EXCHANGE,
                "routing_key": ENCODING_DEAD_LETTER_ROUTING_KEY,
            },
        ),
        (
            "queue_declare",
            {
                "queue": "jobs.encode",
                "durable": True,
                "arguments": {
                    "x-dead-letter-exchange": ENCODING_DEAD_LETTER_EXCHANGE,
                    "x-dead-letter-routing-key": ENCODING_DEAD_LETTER_ROUTING_KEY,
                },
            },
        ),
        (
            "queue_bind",
            {
                "queue": "jobs.encode",
                "exchange": ENCODING_EXCHANGE,
                "routing_key": ENCODING_ROUTING_KEY,
            },
        ),
    ]


def test_rabbitmq_publisher_session_sets_up_topology_and_closes(monkeypatch):
    channel = FakeBlockingChannel()
    connection = FakeBlockingConnection(channel)

    monkeypatch.setattr(
        "core.queue.publisher.pika.BlockingConnection",
        lambda _params: connection,
    )

    publisher = RabbitMQJobQueuePublisher("amqp://guest:guest@localhost:5672/%2F")
    with publisher.session() as session:
        assert isinstance(session, RabbitMQJobQueueSession)

    assert connection.closed is True
    assert [call[0] for call in channel.calls] == [
        "exchange_declare",
        "exchange_declare",
        "queue_declare",
        "queue_bind",
        "queue_declare",
        "queue_bind",
    ]


def test_rabbitmq_publisher_session_wraps_connection_failures(monkeypatch):
    def fail_connection(_params):
        raise RuntimeError("rabbitmq down")

    monkeypatch.setattr(
        "core.queue.publisher.pika.BlockingConnection",
        fail_connection,
    )

    publisher = RabbitMQJobQueuePublisher("amqp://guest:guest@localhost:5672/%2F")

    with pytest.raises(QueuePublishError, match="failed to publish encoding job"):
        with publisher.session():
            pass


def test_rabbitmq_queue_session_publishes_persistent_json_message():
    channel = FakeBlockingChannel()
    session = RabbitMQJobQueueSession(channel)
    message = EncodingJobMessage(
        job_id=UUID("11111111-1111-1111-1111-111111111111"),
        video_id=UUID("22222222-2222-2222-2222-222222222222"),
        rendition_id=UUID("33333333-3333-3333-3333-333333333333"),
    )

    session.publish_encoding_job(
        message=message,
        exchange=ENCODING_EXCHANGE,
        routing_key=ENCODING_ROUTING_KEY,
    )

    assert len(channel.calls) == 1
    operation, payload = channel.calls[0]
    assert operation == "basic_publish"
    assert payload["exchange"] == ENCODING_EXCHANGE
    assert payload["routing_key"] == ENCODING_ROUTING_KEY
    assert payload["mandatory"] is True
    assert b"11111111-1111-1111-1111-111111111111" in payload["body"]
    assert payload["properties"].content_type == "application/json"
    assert payload["properties"].delivery_mode == 2
