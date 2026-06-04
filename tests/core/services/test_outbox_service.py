from core.models.outbox import OutboxMessage
from core.models.enums import OutboxStatus
from core.queue.messages import ENCODING_EXCHANGE, ENCODING_ROUTING_KEY
from core.services.outbox_service import publish_pending_outbox_messages
from core.services.video_service import ingest_video
from tests.fakes import FakeOutboxMessagePublisher


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
            status=OutboxStatus.pending,
        )
        for job in jobs
    ]
    db_session.add_all(outbox_messages)
    db_session.commit()

    publisher = FakeOutboxMessagePublisher()
    published_count = publish_pending_outbox_messages(db_session, publisher)

    for outbox_message in outbox_messages:
        db_session.refresh(outbox_message)
        assert outbox_message.status == OutboxStatus.published
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
        status=OutboxStatus.pending,
    )
    db_session.add(outbox_message)
    db_session.commit()

    published_count = publish_pending_outbox_messages(
        db_session,
        FakeOutboxMessagePublisher(fail=True),
    )

    db_session.refresh(outbox_message)
    assert published_count == 0
    assert outbox_message.status == OutboxStatus.pending
    assert outbox_message.published_at is None
    assert outbox_message.attempt_count == 1
    assert outbox_message.last_error == "rabbitmq unavailable"


def test_publish_pending_outbox_messages_can_publish_specific_rows(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    jobs = [rendition.jobs[0] for rendition in video.renditions[:2]]
    outbox_messages = [
        OutboxMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
            exchange=ENCODING_EXCHANGE,
            routing_key=ENCODING_ROUTING_KEY,
            status=OutboxStatus.pending,
        )
        for job in jobs
    ]
    db_session.add_all(outbox_messages)
    db_session.commit()

    publisher = FakeOutboxMessagePublisher()
    published_count = publish_pending_outbox_messages(
        db_session,
        publisher,
        outbox_message_ids=[outbox_messages[0].id],
    )

    for outbox_message in outbox_messages:
        db_session.refresh(outbox_message)
    assert published_count == 1
    assert outbox_messages[0].status == OutboxStatus.published
    assert outbox_messages[1].status == OutboxStatus.pending
    assert len(publisher.messages) == 1
    assert publisher.messages[0][0].job_id == jobs[0].id


def test_publish_pending_outbox_messages_records_session_failures(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    outbox_message = OutboxMessage(
        job_id=job.id,
        video_id=job.video_id,
        rendition_id=job.rendition_id,
        exchange=ENCODING_EXCHANGE,
        routing_key=ENCODING_ROUTING_KEY,
        status=OutboxStatus.pending,
    )
    db_session.add(outbox_message)
    db_session.commit()

    publisher = FakeOutboxMessagePublisher(fail_session=True)
    published_count = publish_pending_outbox_messages(db_session, publisher)

    db_session.refresh(outbox_message)
    assert published_count == 0
    assert publisher.session_count == 1
    assert outbox_message.status == OutboxStatus.pending
    assert outbox_message.attempt_count == 1
    assert outbox_message.last_error == "rabbitmq connection failed"


def test_publish_pending_outbox_messages_skips_empty_batches(db_session):
    publisher = FakeOutboxMessagePublisher()

    published_count = publish_pending_outbox_messages(db_session, publisher)

    assert published_count == 0
    assert publisher.session_count == 0
