from contextlib import contextmanager

from core.models.enums import ProcessingStatus
from core.queue.messages import EncodingJobMessage
from core.services.video_service import ingest_video
from tests.fakes import FakeEncodingProcessor, FakeObjectStorage
from worker.processor import EncodingProcessorResult
from worker.processor import (
    WorkerMessageAction,
    process_encoding_message,
)


def fake_final_encoding_result(video_id, resolution: str) -> EncodingProcessorResult:
    return EncodingProcessorResult(
        output_path=f"hls/{video_id}/{resolution}/index.m3u8",
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
        processor=FakeEncodingProcessor(),
    )

    db_session.refresh(job)
    assert action == WorkerMessageAction.ack
    assert job.status == ProcessingStatus.done


def test_process_encoding_message_generates_master_playlist_on_final_rendition(
    db_session,
):
    storage = FakeObjectStorage()
    video = ingest_video(db_session, "s3://input/video.mp4")

    for rendition in video.renditions[:-1]:
        rendition.status = ProcessingStatus.done
        rendition.output_path = f"hls/{video.id}/{rendition.resolution}/index.m3u8"
        rendition.jobs[0].status = ProcessingStatus.done

    final_job = video.renditions[-1].jobs[0]
    db_session.commit()

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
        processor=FakeEncodingProcessor(
            result=fake_final_encoding_result(video.id, final_job.rendition.resolution)
        ),
        storage=storage,
    )

    db_session.refresh(video)
    assert action == WorkerMessageAction.ack
    assert video.status == ProcessingStatus.done
    assert video.playback_path == f"hls/{video.id}/master.m3u8"
    assert len(storage.uploaded_bytes) == 1
    assert storage.uploaded_bytes[0]["key"] == f"hls/{video.id}/master.m3u8"


def test_process_encoding_message_acks_scheduled_retry_failure(db_session):
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
        processor=FakeEncodingProcessor(error=RuntimeError("ffmpeg failed")),
    )

    db_session.refresh(job)
    assert action == WorkerMessageAction.ack
    assert job.status == ProcessingStatus.pending
    assert job.attempt_count == 1
    assert job.next_run_at is not None


def test_process_encoding_message_rejects_terminal_failure(db_session):
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
        processor=FakeEncodingProcessor(error=RuntimeError("ffmpeg failed")),
    )

    db_session.refresh(job)
    assert action == WorkerMessageAction.reject
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
        processor=FakeEncodingProcessor(),
    )

    assert action == WorkerMessageAction.reject
