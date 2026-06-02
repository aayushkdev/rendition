from enum import Enum
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from sqlalchemy.orm import Session

from core.queue.messages import EncodingJobMessage
from core.services.job_service import (
    EncodingJobContext,
    EncodingJobError,
    claim_encoding_job,
    mark_encoding_job_failed,
    mark_encoding_job_succeeded,
)


class WorkerMessageAction(str, Enum):
    ack = "ack"
    requeue = "requeue"
    reject = "reject"


class EncodingProcessor(Protocol):
    def process(self, context: EncodingJobContext) -> str | None: ...


class FfmpegEncodingProcessor:
    def process(self, context: EncodingJobContext) -> str | None:
        raise NotImplementedError("ffmpeg processing is not implemented yet")


SessionScope = Callable[[], AbstractContextManager[Session]]


def process_encoding_message(
    session_scope: SessionScope,
    message: EncodingJobMessage,
    processor: EncodingProcessor,
) -> WorkerMessageAction:
    try:
        with session_scope() as db:
            context = claim_encoding_job(
                db=db,
                job_id=message.job_id,
                video_id=message.video_id,
                rendition_id=message.rendition_id,
            )
    except EncodingJobError:
        return WorkerMessageAction.reject

    if context is None:
        return WorkerMessageAction.ack

    try:
        output_path = processor.process(context)
    except Exception as exc:
        with session_scope() as db:
            should_retry = mark_encoding_job_failed(db, context.job_id, str(exc))
        if should_retry:
            return WorkerMessageAction.requeue
        return WorkerMessageAction.ack

    with session_scope() as db:
        mark_encoding_job_succeeded(db, context.job_id, output_path=output_path)
    return WorkerMessageAction.ack
