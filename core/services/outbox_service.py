from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.models.enums import OutboxStatus, ProcessingStatus
from core.models.job import Job
from core.models.outbox import OutboxMessage
from core.queue.messages import (
    ENCODING_EXCHANGE,
    ENCODING_ROUTING_KEY,
    EncodingJobMessage,
)
from core.queue.publisher import JobQueuePublisher


def create_outbox_messages(db: Session, jobs: list[Job]) -> list[UUID]:
    outbox_messages: list[OutboxMessage] = []
    for job in jobs:
        outbox_messages.append(
            OutboxMessage(
                job_id=job.id,
                video_id=job.video_id,
                rendition_id=job.rendition_id,
                exchange=ENCODING_EXCHANGE,
                routing_key=ENCODING_ROUTING_KEY,
                status=OutboxStatus.pending,
            ),
        )

    db.add_all(outbox_messages)
    db.flush()
    return [message.id for message in outbox_messages]


def publish_pending_outbox_messages(
    db: Session,
    publisher: JobQueuePublisher,
    limit: int = 100,
    outbox_message_ids: list[UUID] | None = None,
) -> int:
    if outbox_message_ids == []:
        return 0

    query = (
        db.query(OutboxMessage)
        .join(Job, OutboxMessage.job_id == Job.id)
        .filter(OutboxMessage.status == OutboxStatus.pending)
        .filter(Job.status == ProcessingStatus.pending)
        .filter(
            or_(
                Job.next_run_at.is_(None),
                Job.next_run_at <= datetime.now(timezone.utc),
            )
        )
        .order_by(OutboxMessage.created_at)
        .with_for_update(skip_locked=True, of=OutboxMessage)
    )

    if outbox_message_ids is not None:
        query = query.filter(OutboxMessage.id.in_(outbox_message_ids))
    else:
        query = query.limit(limit)

    outbox_messages = query.all()

    if not outbox_messages:
        return 0

    try:
        with publisher.session() as publish_session:
            published_count = 0
            for outbox_message in outbox_messages:
                try:
                    publish_session.publish_encoding_job(
                        message=EncodingJobMessage(
                            job_id=outbox_message.job_id,
                            video_id=outbox_message.video_id,
                            rendition_id=outbox_message.rendition_id,
                        ),
                        exchange=outbox_message.exchange,
                        routing_key=outbox_message.routing_key,
                    )
                except Exception as exc:
                    outbox_message.attempt_count += 1
                    outbox_message.last_error = str(exc)
                    continue

                outbox_message.status = OutboxStatus.published
                outbox_message.published_at = datetime.now(timezone.utc)
                outbox_message.last_error = None
                published_count += 1
    except Exception as exc:
        for outbox_message in outbox_messages:
            outbox_message.attempt_count += 1
            outbox_message.last_error = str(exc)
        published_count = 0

    db.commit()
    return published_count
