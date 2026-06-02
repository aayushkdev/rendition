import pytest

from core.models.enums import ProcessingStatus
from core.services.job_service import (
    EncodingJobMessageMismatchError,
    claim_encoding_job,
    derive_video_status,
    mark_encoding_job_failed,
    mark_encoding_job_succeeded,
)
from core.services.video_service import ingest_video


def test_claim_encoding_job_marks_job_running(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]

    context = claim_encoding_job(
        db=db_session,
        job_id=job.id,
        video_id=job.video_id,
        rendition_id=job.rendition_id,
    )

    db_session.refresh(job)
    assert context is not None
    assert context.job_id == job.id
    assert context.resolution == job.rendition.resolution
    assert job.status == ProcessingStatus.running
    assert job.rendition.status == ProcessingStatus.running
    assert job.rendition.video.status == ProcessingStatus.running
    assert job.attempt_count == 1
    assert job.started_at is not None


def test_claim_encoding_job_rejects_mismatched_message(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]

    with pytest.raises(EncodingJobMessageMismatchError):
        claim_encoding_job(
            db=db_session,
            job_id=job.id,
            video_id=job.video_id,
            rendition_id=video.renditions[1].id,
        )


def test_claim_encoding_job_skips_running_job(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    job.status = ProcessingStatus.running
    job.rendition.status = ProcessingStatus.running
    job.rendition.video.status = ProcessingStatus.running
    db_session.commit()

    context = claim_encoding_job(
        db=db_session,
        job_id=job.id,
        video_id=job.video_id,
        rendition_id=job.rendition_id,
    )

    db_session.refresh(job)
    assert context is None
    assert job.status == ProcessingStatus.running
    assert job.attempt_count == 0


def test_mark_encoding_job_succeeded_updates_rendition(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    claim_encoding_job(db_session, job.id, job.video_id, job.rendition_id)

    mark_encoding_job_succeeded(
        db=db_session,
        job_id=job.id,
        output_path="renditions/video/1080p/master.m3u8",
    )

    db_session.refresh(job)
    assert job.status == ProcessingStatus.done
    assert job.finished_at is not None
    assert job.rendition.status == ProcessingStatus.done
    assert job.rendition.output_path == "renditions/video/1080p/master.m3u8"
    assert job.rendition.video.status == ProcessingStatus.partial


def test_mark_encoding_job_failed_returns_retry_decision(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    claim_encoding_job(db_session, job.id, job.video_id, job.rendition_id)

    should_retry = mark_encoding_job_failed(db_session, job.id, "ffmpeg failed")

    db_session.refresh(job)
    assert should_retry is True
    assert job.status == ProcessingStatus.pending
    assert job.rendition.status == ProcessingStatus.pending
    assert job.error == "ffmpeg failed"


def test_mark_encoding_job_failed_marks_terminal_after_max_attempts(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    job.attempt_count = job.max_attempts
    db_session.commit()

    should_retry = mark_encoding_job_failed(db_session, job.id, "ffmpeg failed")

    db_session.refresh(job)
    assert should_retry is False
    assert job.status == ProcessingStatus.failed
    assert job.rendition.status == ProcessingStatus.failed
    assert job.rendition.video.status == ProcessingStatus.failed


def test_successful_rendition_does_not_hide_existing_failed_rendition(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    succeeding_job = video.renditions[0].jobs[0]
    failed_rendition = video.renditions[1]
    failed_rendition.status = ProcessingStatus.failed
    failed_rendition.jobs[0].status = ProcessingStatus.failed
    video.status = ProcessingStatus.failed
    db_session.commit()
    claim_encoding_job(
        db_session,
        succeeding_job.id,
        succeeding_job.video_id,
        succeeding_job.rendition_id,
    )

    mark_encoding_job_succeeded(db_session, succeeding_job.id)

    db_session.refresh(video)
    assert succeeding_job.rendition.status == ProcessingStatus.done
    assert failed_rendition.status == ProcessingStatus.failed
    assert video.status == ProcessingStatus.partial


def test_failed_rendition_keeps_completed_renditions_partially_available(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    done_rendition = video.renditions[0]
    failing_job = video.renditions[1].jobs[0]
    done_rendition.status = ProcessingStatus.done
    done_rendition.jobs[0].status = ProcessingStatus.done
    failing_job.attempt_count = failing_job.max_attempts
    db_session.commit()

    should_retry = mark_encoding_job_failed(db_session, failing_job.id, "ffmpeg failed")

    db_session.refresh(video)
    assert should_retry is False
    assert video.status == ProcessingStatus.partial


def test_derive_video_status_from_renditions():
    class RenditionStatus:
        def __init__(self, status):
            self.status = status

    assert (
        derive_video_status(
            [
                RenditionStatus(ProcessingStatus.done),
                RenditionStatus(ProcessingStatus.done),
            ]
        )
        == ProcessingStatus.done
    )
    assert (
        derive_video_status(
            [
                RenditionStatus(ProcessingStatus.done),
                RenditionStatus(ProcessingStatus.failed),
            ]
        )
        == ProcessingStatus.partial
    )
    assert (
        derive_video_status(
            [
                RenditionStatus(ProcessingStatus.pending),
                RenditionStatus(ProcessingStatus.failed),
            ]
        )
        == ProcessingStatus.failed
    )
