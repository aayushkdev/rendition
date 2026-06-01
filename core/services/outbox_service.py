from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.models.outbox import OutboxMessage
from core.queue.messages import EncodingJobMessage
from core.queue.publisher import JobQueuePublisher

OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_PUBLISHED = "published"


def publish_pending_outbox_messages(
    db: Session,
    publisher: JobQueuePublisher,
    limit: int = 100,
) -> int:
    outbox_messages = (
        db.query(OutboxMessage)
        .filter(OutboxMessage.status == OUTBOX_STATUS_PENDING)
        .order_by(OutboxMessage.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True, of=OutboxMessage)
        .all()
    )

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

                outbox_message.status = OUTBOX_STATUS_PUBLISHED
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
