from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from core.models.enums import ProcessingStatus
from core.models.job import Job
from core.models.rendition import Rendition


class EncodingJobError(RuntimeError):
    pass


class EncodingJobNotFoundError(EncodingJobError):
    pass


class EncodingJobMessageMismatchError(EncodingJobError):
    pass


@dataclass(frozen=True)
class EncodingJobContext:
    job_id: UUID
    video_id: UUID
    rendition_id: UUID
    source: str
    source_bucket: str | None
    source_filename: str | None
    resolution: str
    bitrate: int
    attempt_count: int
    max_attempts: int


def _get_job_for_update(db: Session, job_id: UUID) -> Job | None:
    return (
        db.query(Job)
        .options(joinedload(Job.rendition).joinedload(Rendition.video))
        .filter(Job.id == job_id)
        .with_for_update(of=Job)
        .one_or_none()
    )


def derive_video_status(renditions: list[Rendition]) -> ProcessingStatus:
    statuses = [rendition.status for rendition in renditions]

    if not statuses:
        return ProcessingStatus.pending

    if all(status == ProcessingStatus.done for status in statuses):
        return ProcessingStatus.done

    if any(status == ProcessingStatus.failed for status in statuses):
        if any(status == ProcessingStatus.done for status in statuses):
            return ProcessingStatus.partial
        return ProcessingStatus.failed

    if any(status == ProcessingStatus.running for status in statuses):
        return ProcessingStatus.running

    if any(status == ProcessingStatus.done for status in statuses):
        return ProcessingStatus.partial

    return ProcessingStatus.pending


def _validate_job_message(
    job: Job,
    video_id: UUID,
    rendition_id: UUID,
) -> None:
    if job.video_id != video_id or job.rendition_id != rendition_id:
        raise EncodingJobMessageMismatchError("encoding job message does not match job")


def _is_claimable(job: Job) -> bool:
    return job.status == ProcessingStatus.pending


def _has_exhausted_attempts(job: Job) -> bool:
    return job.attempt_count >= job.max_attempts


def _mark_job_attempts_exhausted(job: Job) -> None:
    job.status = ProcessingStatus.failed
    job.rendition.status = ProcessingStatus.failed
    job.rendition.video.status = derive_video_status(job.rendition.video.renditions)
    job.finished_at = datetime.now(timezone.utc)
    job.error = "encoding job exceeded maximum attempts"


def _mark_job_running(job: Job) -> None:
    now = datetime.now(timezone.utc)
    job.status = ProcessingStatus.running
    job.attempt_count += 1
    job.started_at = now
    job.finished_at = None
    job.error = None
    job.rendition.status = ProcessingStatus.running
    job.rendition.error = None
    job.rendition.video.status = derive_video_status(job.rendition.video.renditions)


def _build_encoding_context(job: Job) -> EncodingJobContext:
    return EncodingJobContext(
        job_id=job.id,
        video_id=job.video_id,
        rendition_id=job.rendition_id,
        source=job.rendition.video.source,
        source_bucket=job.rendition.video.source_bucket,
        source_filename=job.rendition.video.source_filename,
        resolution=job.rendition.resolution,
        bitrate=job.rendition.bitrate,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
    )


def claim_encoding_job(
    db: Session,
    job_id: UUID,
    video_id: UUID,
    rendition_id: UUID,
) -> EncodingJobContext | None:
    job = _get_job_for_update(db, job_id)

    if job is None:
        raise EncodingJobNotFoundError("encoding job not found")

    _validate_job_message(job, video_id, rendition_id)

    if not _is_claimable(job):
        db.commit()
        return None

    if _has_exhausted_attempts(job):
        _mark_job_attempts_exhausted(job)
        db.commit()
        return None

    _mark_job_running(job)
    context = _build_encoding_context(job)
    db.commit()
    return context


def mark_encoding_job_succeeded(
    db: Session,
    job_id: UUID,
    output_path: str | None = None,
) -> None:
    job = _get_job_for_update(db, job_id)

    if job is None:
        raise EncodingJobNotFoundError("encoding job not found")

    now = datetime.now(timezone.utc)
    job.status = ProcessingStatus.done
    job.finished_at = now
    job.error = None
    job.rendition.status = ProcessingStatus.done
    job.rendition.completed_at = now
    job.rendition.error = None
    if output_path is not None:
        job.rendition.output_path = output_path

    job.rendition.video.status = derive_video_status(job.rendition.video.renditions)

    db.commit()


def mark_encoding_job_failed(
    db: Session,
    job_id: UUID,
    error: str,
) -> bool:
    job = _get_job_for_update(db, job_id)

    if job is None:
        raise EncodingJobNotFoundError("encoding job not found")

    should_retry = job.attempt_count < job.max_attempts
    job.error = error
    job.finished_at = datetime.now(timezone.utc)
    job.status = ProcessingStatus.pending if should_retry else ProcessingStatus.failed
    job.rendition.status = (
        ProcessingStatus.pending if should_retry else ProcessingStatus.failed
    )
    job.rendition.error = error

    job.rendition.video.status = derive_video_status(job.rendition.video.renditions)

    db.commit()
    return should_retry
