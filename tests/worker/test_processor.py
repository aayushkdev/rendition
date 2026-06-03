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


class RecordingStorage:
    def __init__(self):
        self.uploads = []

    def upload_bytes(
        self,
        key: str,
        body: bytes,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        self.uploads.append(
            {
                "key": key,
                "body": body,
                "content_type": content_type,
                "cache_control": cache_control,
            }
        )


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


def test_process_encoding_message_generates_master_playlist_on_final_rendition(
    db_session,
):
    storage = RecordingStorage()
    video = ingest_video(db_session, "s3://input/video.mp4")

    for rendition in video.renditions[:-1]:
        rendition.status = ProcessingStatus.done
        rendition.output_path = f"hls/{video.id}/{rendition.resolution}/index.m3u8"
        rendition.jobs[0].status = ProcessingStatus.done

    final_job = video.renditions[-1].jobs[0]
    db_session.commit()

    class FinalProcessor:
        def process(self, _job):
            return EncodingProcessorResult(
                output_path=(
                    f"hls/{video.id}/{final_job.rendition.resolution}/index.m3u8"
                ),
            )

    @contextmanager
    def session_scope():
        yield db_session

    action = process_encoding_message(
        session_scope=session_scope,
        message=EncodingJobMessage(
            job_id=final_job.id,
            video_id=final_job.video_id,
            rendition_id=final_job.rendition_id,
        ),
        processor=FinalProcessor(),
        storage=storage,
    )

    db_session.refresh(video)
    assert action == WorkerMessageAction.ack
    assert video.status == ProcessingStatus.done
    assert video.playback_path == f"hls/{video.id}/master.m3u8"
    assert len(storage.uploads) == 1
    assert storage.uploads[0]["key"] == f"hls/{video.id}/master.m3u8"


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
