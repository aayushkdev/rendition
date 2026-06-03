import pytest

from core.encoding import VideoSourceMetadata
from core.models.enums import ProcessingStatus
from core.services.job_service import (
    EncodingJobMessageMismatchError,
    claim_encoding_job,
    derive_video_status,
    mark_encoding_job_failed,
    mark_encoding_job_skipped,
    mark_encoding_job_succeeded,
)
from core.services.video_service import ingest_video


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


def test_mark_encoding_job_succeeded_stores_source_metadata(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    claim_encoding_job(db_session, job.id, job.video_id, job.rendition_id)

    mark_encoding_job_succeeded(
        db=db_session,
        job_id=job.id,
        output_path="renditions/video/1080p/master.m3u8",
        source_metadata=VideoSourceMetadata(
            width=1920,
            height=1080,
            bitrate=4_000_000,
            duration_seconds=72.5,
        ),
    )

    db_session.refresh(video)
    assert video.source_width == 1920
    assert video.source_height == 1080
    assert video.source_bitrate == 4_000_000
    assert video.source_duration_seconds == 72.5


def test_mark_encoding_job_skipped_updates_rendition_and_source_metadata(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")
    job = video.renditions[0].jobs[0]
    claim_encoding_job(db_session, job.id, job.video_id, job.rendition_id)

    mark_encoding_job_skipped(
        db=db_session,
        job_id=job.id,
        reason="1080p is not applicable for 1280x720 source",
        source_metadata=VideoSourceMetadata(
            width=1280,
            height=720,
            bitrate=2_500_000,
            duration_seconds=44.0,
        ),
    )

    db_session.refresh(job)
    assert job.status == ProcessingStatus.done
    assert job.error == "1080p is not applicable for 1280x720 source"
    assert job.rendition.status == ProcessingStatus.skipped
    assert job.rendition.output_path is None
    assert job.rendition.video.source_width == 1280
    assert job.rendition.video.source_height == 720
    assert job.rendition.video.source_bitrate == 2_500_000
    assert job.rendition.video.source_duration_seconds == 44.0


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


def test_terminal_success_generates_master_playlist(db_session):
    storage = RecordingStorage()
    video = ingest_video(db_session, "s3://input/video.mp4")

    for rendition in video.renditions:
        claim_encoding_job(
            db_session,
            rendition.jobs[0].id,
            rendition.jobs[0].video_id,
            rendition.jobs[0].rendition_id,
        )
        mark_encoding_job_succeeded(
            db_session,
            rendition.jobs[0].id,
            output_path=f"hls/{video.id}/{rendition.resolution}/index.m3u8",
            storage=storage,
        )

    db_session.refresh(video)
    assert video.status == ProcessingStatus.done
    assert video.playback_path == f"hls/{video.id}/master.m3u8"
    assert len(storage.uploads) == 1
    assert storage.uploads[0]["key"] == f"hls/{video.id}/master.m3u8"
    assert storage.uploads[0]["content_type"] == "application/vnd.apple.mpegurl"
    assert b"#EXTM3U\n" in storage.uploads[0]["body"]
    assert b"1080p/index.m3u8\n" in storage.uploads[0]["body"]


def test_terminal_partial_generates_master_playlist_for_successful_renditions(
    db_session,
):
    storage = RecordingStorage()
    video = ingest_video(db_session, "s3://input/video.mp4")
    done_rendition = video.renditions[0]
    failing_rendition = video.renditions[1]
    skipped_rendition = video.renditions[2]

    claim_encoding_job(
        db_session,
        done_rendition.jobs[0].id,
        done_rendition.jobs[0].video_id,
        done_rendition.jobs[0].rendition_id,
    )
    mark_encoding_job_succeeded(
        db_session,
        done_rendition.jobs[0].id,
        output_path=f"hls/{video.id}/{done_rendition.resolution}/index.m3u8",
        storage=storage,
    )
    claim_encoding_job(
        db_session,
        skipped_rendition.jobs[0].id,
        skipped_rendition.jobs[0].video_id,
        skipped_rendition.jobs[0].rendition_id,
    )
    mark_encoding_job_skipped(
        db_session,
        skipped_rendition.jobs[0].id,
        "rendition not applicable",
        storage=storage,
    )
    claim_encoding_job(
        db_session,
        failing_rendition.jobs[0].id,
        failing_rendition.jobs[0].video_id,
        failing_rendition.jobs[0].rendition_id,
    )
    failing_rendition.jobs[0].attempt_count = failing_rendition.jobs[0].max_attempts
    db_session.commit()

    should_retry = mark_encoding_job_failed(
        db_session,
        failing_rendition.jobs[0].id,
        "ffmpeg failed",
        storage=storage,
    )

    db_session.refresh(video)
    assert should_retry is False
    assert video.status == ProcessingStatus.partial
    assert video.playback_path == f"hls/{video.id}/master.m3u8"
    assert len(storage.uploads) == 1
    assert (
        f"{done_rendition.resolution}/index.m3u8\n".encode()
        in storage.uploads[0]["body"]
    )
    assert (
        f"{failing_rendition.resolution}/index.m3u8\n".encode()
        not in storage.uploads[0]["body"]
    )


def test_all_skipped_renditions_do_not_create_playback_path(db_session):
    storage = RecordingStorage()
    video = ingest_video(db_session, "s3://input/video.mp4")

    for rendition in video.renditions:
        claim_encoding_job(
            db_session,
            rendition.jobs[0].id,
            rendition.jobs[0].video_id,
            rendition.jobs[0].rendition_id,
        )
        mark_encoding_job_skipped(
            db_session,
            rendition.jobs[0].id,
            "rendition not applicable",
            storage=storage,
        )

    db_session.refresh(video)
    assert video.status == ProcessingStatus.failed
    assert video.playback_path is None
    assert storage.uploads == []


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
    assert (
        derive_video_status(
            [
                RenditionStatus(ProcessingStatus.done),
                RenditionStatus(ProcessingStatus.skipped),
            ]
        )
        == ProcessingStatus.done
    )
