from contextlib import contextmanager

from core.models.enums import ProcessingStatus
from core.queue.messages import EncodingJobMessage
from core.services.video_service import ingest_video
from worker.processor import (
    EncodingProcessorResult,
    WorkerMessageAction,
    process_encoding_message,
)


class SuccessfulProcessor:
    def process(self, _job):
        return EncodingProcessorResult(
            output_path="renditions/video/1080p/master.m3u8",
        )


class FailingProcessor:
    def process(self, _job):
        raise RuntimeError("ffmpeg failed")


def test_process_encoding_message_acks_success(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]

    @contextmanager
    def session_scope():
        yield db_session

    action = process_encoding_message(
        session_scope=session_scope,
        message=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        ),
        processor=SuccessfulProcessor(),
    )

    db_session.refresh(job)
    assert action == WorkerMessageAction.ack
    assert job.status == ProcessingStatus.done


def test_process_encoding_message_requeues_retryable_failure(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]

    @contextmanager
    def session_scope():
        yield db_session

    action = process_encoding_message(
        session_scope=session_scope,
        message=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        ),
        processor=FailingProcessor(),
    )

    db_session.refresh(job)
    assert action == WorkerMessageAction.requeue
    assert job.status == ProcessingStatus.pending
    assert job.attempt_count == 1


def test_process_encoding_message_acks_terminal_failure(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    job.attempt_count = job.max_attempts - 1
    db_session.commit()

    @contextmanager
    def session_scope():
        yield db_session

    action = process_encoding_message(
        session_scope=session_scope,
        message=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=job.rendition_id,
        ),
        processor=FailingProcessor(),
    )

    db_session.refresh(job)
    assert action == WorkerMessageAction.ack
    assert job.status == ProcessingStatus.failed


def test_process_encoding_message_rejects_mismatched_job(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]

    @contextmanager
    def session_scope():
        yield db_session

    action = process_encoding_message(
        session_scope=session_scope,
        message=EncodingJobMessage(
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=video.renditions[1].id,
        ),
        processor=SuccessfulProcessor(),
    )

    assert action == WorkerMessageAction.reject
