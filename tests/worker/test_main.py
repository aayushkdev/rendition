from contextlib import contextmanager

import pytest
import pika
from pika import exceptions as pika_exceptions

from core.queue.messages import EncodingJobMessage
from core.services.video_service import ingest_video
from tests.fakes import FakeDeliveryChannel, FakeDeliveryMethod, FakeEncodingProcessor
from worker.main import connect_with_retry, handle_delivery


def test_handle_delivery_acks_success(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    channel = FakeDeliveryChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=FakeDeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=FakeEncodingProcessor(),
    )

    assert channel.acks == ["delivery-1"]
    assert channel.nacks == []
    assert channel.rejects == []


def test_handle_delivery_acks_scheduled_retry_failure(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    channel = FakeDeliveryChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=FakeDeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=FakeEncodingProcessor(error=RuntimeError("ffmpeg failed")),
    )

    assert channel.acks == ["delivery-1"]
    assert channel.nacks == []
    assert channel.rejects == []


def test_handle_delivery_rejects_terminal_failure(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    job.attempt_count = job.max_attempts - 1
    db_session.commit()
    channel = FakeDeliveryChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=FakeDeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=FakeEncodingProcessor(error=RuntimeError("ffmpeg failed")),
    )

    assert channel.acks == []
    assert channel.nacks == []
    assert channel.rejects == [{"delivery_tag": "delivery-1", "requeue": False}]


def test_handle_delivery_rejects_invalid_json(db_session):
    channel = FakeDeliveryChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=FakeDeliveryMethod(),
        body=b"{",
        session_scope=session_scope,
        processor=FakeEncodingProcessor(),
    )

    assert channel.acks == []
    assert channel.nacks == []
    assert channel.rejects == [{"delivery_tag": "delivery-1", "requeue": False}]


def test_handle_delivery_nacks_unexpected_processor_crash(db_session, monkeypatch):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    channel = FakeDeliveryChannel()

    @contextmanager
    def session_scope():
        yield db_session

    def crash(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("worker.main.process_encoding_message", crash)

    handle_delivery(
        channel=channel,
        method=FakeDeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=FakeEncodingProcessor(),
    )

    assert channel.acks == []
    assert channel.nacks == [{"delivery_tag": "delivery-1", "requeue": True}]
    assert channel.rejects == []


def test_connect_with_retry_returns_after_transient_failures(monkeypatch):
    connection = object()
    attempts = []

    def blocking_connection(_parameters):
        attempts.append("attempt")
        if len(attempts) < 3:
            raise pika_exceptions.AMQPConnectionError("rabbitmq unavailable")
        return connection

    sleeps = []
    monkeypatch.setattr("worker.main.pika.BlockingConnection", blocking_connection)
    monkeypatch.setattr(
        "worker.main.time.sleep", lambda seconds: sleeps.append(seconds)
    )
    monkeypatch.setattr("worker.main.settings.RABBITMQ_CONNECT_RETRY_COUNT", 3)

    assert connect_with_retry() is connection
    assert len(attempts) == 3
    assert sleeps == [1, 2]


def test_connect_with_retry_fails_after_max_attempts(monkeypatch):
    attempts = []

    def blocking_connection(_parameters):
        attempts.append("attempt")
        raise pika_exceptions.AMQPConnectionError("rabbitmq unavailable")

    sleeps = []
    monkeypatch.setattr("worker.main.pika.BlockingConnection", blocking_connection)
    monkeypatch.setattr(
        "worker.main.time.sleep", lambda seconds: sleeps.append(seconds)
    )
    monkeypatch.setattr("worker.main.settings.RABBITMQ_CONNECT_RETRY_COUNT", 2)

    with pytest.raises(RuntimeError, match="failed to connect to RabbitMQ"):
        connect_with_retry()

    assert len(attempts) == 2
    assert sleeps == [1, 2]
