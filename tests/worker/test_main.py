from contextlib import contextmanager

import pytest
import pika

from core.queue.messages import EncodingJobMessage
from core.services.video_service import ingest_video
from worker.main import connect_with_retry, handle_delivery
from worker.processor import EncodingProcessorResult


class RecordingChannel:
    def __init__(self):
        self.acks = []
        self.nacks = []
        self.rejects = []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append({"delivery_tag": delivery_tag, "requeue": requeue})

    def basic_reject(self, delivery_tag, requeue):
        self.rejects.append({"delivery_tag": delivery_tag, "requeue": requeue})


class DeliveryMethod:
    delivery_tag = "delivery-1"


class SuccessfulProcessor:
    def process(self, _context):
        return EncodingProcessorResult(
            output_path="renditions/video/1080p/master.m3u8",
        )


class FailingProcessor:
    def process(self, _context):
        raise RuntimeError("ffmpeg failed")


def test_handle_delivery_acks_success(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    channel = RecordingChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=DeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=SuccessfulProcessor(),
    )

    assert channel.acks == ["delivery-1"]
    assert channel.nacks == []
    assert channel.rejects == []


def test_handle_delivery_nacks_retryable_failure(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    channel = RecordingChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=DeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=FailingProcessor(),
    )

    assert channel.acks == []
    assert channel.nacks == [{"delivery_tag": "delivery-1", "requeue": True}]
    assert channel.rejects == []


def test_handle_delivery_rejects_invalid_json(db_session):
    channel = RecordingChannel()

    @contextmanager
    def session_scope():
        yield db_session

    handle_delivery(
        channel=channel,
        method=DeliveryMethod(),
        body=b"{",
        session_scope=session_scope,
        processor=SuccessfulProcessor(),
    )

    assert channel.acks == []
    assert channel.nacks == []
    assert channel.rejects == [{"delivery_tag": "delivery-1", "requeue": False}]


def test_handle_delivery_nacks_unexpected_processor_crash(db_session, monkeypatch):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    channel = RecordingChannel()

    @contextmanager
    def session_scope():
        yield db_session

    def crash(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("worker.main.process_encoding_message", crash)

    handle_delivery(
        channel=channel,
        method=DeliveryMethod(),
        body=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        )
        .model_dump_json()
        .encode("utf-8"),
        session_scope=session_scope,
        processor=SuccessfulProcessor(),
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
            raise pika.exceptions.AMQPConnectionError("rabbitmq unavailable")
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
        raise pika.exceptions.AMQPConnectionError("rabbitmq unavailable")

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
