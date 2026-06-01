from core.models.outbox import OutboxMessage
from core.queue.messages import ENCODING_EXCHANGE, ENCODING_ROUTING_KEY
from core.services.outbox_service import publish_pending_outbox_messages
from core.services.video_service import ingest_video


class RecordingPublisher:
    def __init__(self, fail: bool = False, fail_session: bool = False):
        self.fail = fail
        self.fail_session = fail_session
        self.messages = []
        self.session_count = 0

    def session(self):
        self.session_count += 1
        if self.fail_session:
            raise RuntimeError("rabbitmq connection failed")
        return self

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def publish_encoding_job(self, message, exchange: str, routing_key: str) -> None:
        if self.fail:
            raise RuntimeError("rabbitmq unavailable")
        self.messages.append((message, exchange, routing_key))


def test_publish_pending_outbox_messages_marks_rows_published(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    jobs = [rendition.jobs[0] for rendition in video.renditions[:2]]
    outbox_messages = [
        OutboxMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
            exchange=ENCODING_EXCHANGE,
            routing_key=ENCODING_ROUTING_KEY,
            status="pending",
        )
        for job in jobs
    ]
    db_session.add_all(outbox_messages)
    db_session.commit()

    publisher = RecordingPublisher()
    published_count = publish_pending_outbox_messages(db_session, publisher)

    for outbox_message in outbox_messages:
        db_session.refresh(outbox_message)
        assert outbox_message.status == "published"
        assert outbox_message.published_at is not None
        assert outbox_message.last_error is None
    assert published_count == 2
    assert publisher.session_count == 1
    assert len(publisher.messages) == 2
    assert {message[0].job_id for message in publisher.messages} == {
        job.id for job in jobs
    }


def test_publish_pending_outbox_messages_keeps_failed_rows_pending(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    outbox_message = OutboxMessage(
        job_id=job.id,
        video_id=job.video_id,
        rendition_id=job.rendition_id,
        exchange=ENCODING_EXCHANGE,
        routing_key=ENCODING_ROUTING_KEY,
        status="pending",
    )
    db_session.add(outbox_message)
    db_session.commit()

    published_count = publish_pending_outbox_messages(
        db_session,
        RecordingPublisher(fail=True),
    )

    db_session.refresh(outbox_message)
    assert published_count == 0
    assert outbox_message.status == "pending"
    assert outbox_message.published_at is None
    assert outbox_message.attempt_count == 1
    assert outbox_message.last_error == "rabbitmq unavailable"


def test_publish_pending_outbox_messages_records_session_failures(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    outbox_message = OutboxMessage(
        job_id=job.id,
        video_id=job.video_id,
        rendition_id=job.rendition_id,
        exchange=ENCODING_EXCHANGE,
        routing_key=ENCODING_ROUTING_KEY,
        status="pending",
    )
    db_session.add(outbox_message)
    db_session.commit()

    publisher = RecordingPublisher(fail_session=True)
    published_count = publish_pending_outbox_messages(db_session, publisher)

    db_session.refresh(outbox_message)
    assert published_count == 0
    assert publisher.session_count == 1
    assert outbox_message.status == "pending"
    assert outbox_message.attempt_count == 1
    assert outbox_message.last_error == "rabbitmq connection failed"


def test_publish_pending_outbox_messages_skips_empty_batches(db_session):
    publisher = RecordingPublisher()

    published_count = publish_pending_outbox_messages(db_session, publisher)

    assert published_count == 0
    assert publisher.session_count == 0
