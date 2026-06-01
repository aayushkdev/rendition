from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from api.schemas.video import (
    CompletedUploadPart as CompletedUploadPartSchema,
    MultipartUploadPart,
    RenditionState,
    VideoCreateResponse,
    VideoListItem,
    VideoState,
)
from core.config import settings
from core.models.video import Video
from core.models.rendition import Rendition
from core.models.job import Job
from core.models.enums import ProcessingStatus, UploadStatus
from core.models.upload_session import UploadSession
from core.storage import (
    CompletedUploadPart as StorageCompletedUploadPart,
    ObjectStorage,
    ObjectStorageError,
    build_source_key,
)


class VideoUploadError(RuntimeError):
    pass


class VideoUploadConflictError(VideoUploadError):
    pass


class VideoUploadValidationError(VideoUploadError):
    pass


class VideoUploadStorageError(VideoUploadError):
    pass


class VideoNotFoundError(LookupError):
    pass


DEFAULT_RENDITIONS = [
    {"resolution": "1080p", "bitrate": 5_000_000},
    {"resolution": "720p", "bitrate": 2_500_000},
    {"resolution": "480p", "bitrate": 1_000_000},
]


def _create_renditions_and_jobs(db: Session, video: Video, max_attempts: int) -> None:
    if video.renditions:
        return

    for rendition_config in DEFAULT_RENDITIONS:
        rendition = Rendition(
            video_id=video.id,
            resolution=rendition_config["resolution"],
            bitrate=rendition_config["bitrate"],
            status=ProcessingStatus.pending,
        )
        db.add(rendition)
        db.flush()

        job = Job(
            video_id=video.id,
            rendition_id=rendition.id,
            status=ProcessingStatus.pending,
            max_attempts=max_attempts,
        )
        db.add(job)


def _get_active_upload_session(db: Session, video: Video) -> UploadSession:
    if video.status != ProcessingStatus.uploading:
        raise VideoUploadConflictError("video upload is not active")

    upload_session = (
        db.query(UploadSession)
        .filter(
            UploadSession.video_id == video.id,
            UploadSession.status == UploadStatus.active,
        )
        .one_or_none()
    )

    if upload_session is None:
        raise VideoUploadConflictError("video upload is missing multipart state")

    return upload_session


def _get_video_for_upload_completion(db: Session, video_id: UUID) -> Video | None:
    return (
        db.query(Video)
        .filter(Video.id == video_id)
        .with_for_update(of=Video)
        .one_or_none()
    )


def _get_active_upload_session_for_update(db: Session, video: Video) -> UploadSession:
    if video.status != ProcessingStatus.uploading:
        raise VideoUploadConflictError("video upload is not active")

    upload_session = (
        db.query(UploadSession)
        .filter(
            UploadSession.video_id == video.id,
            UploadSession.status == UploadStatus.active,
        )
        .with_for_update(of=UploadSession)
        .one_or_none()
    )

    if upload_session is None:
        raise VideoUploadConflictError("video upload is missing multipart state")

    return upload_session


def _validate_completed_upload_metadata(
    storage: ObjectStorage,
    upload_session: UploadSession,
) -> None:
    metadata = storage.get_object_metadata(upload_session.object_key)

    if metadata is None:
        raise VideoUploadStorageError("completed upload object was not found")

    if metadata.content_length != upload_session.size_bytes:
        raise VideoUploadStorageError("completed upload size mismatch")

    if metadata.content_type != upload_session.content_type:
        raise VideoUploadStorageError("completed upload content type mismatch")


def _delete_invalid_completed_upload(
    storage: ObjectStorage,
    upload_session: UploadSession,
) -> None:
    storage.delete_object(upload_session.object_key)


def _validate_completed_upload_parts(
    upload_session: UploadSession,
    parts: list[CompletedUploadPartSchema],
) -> None:
    expected_part_numbers = list(range(1, upload_session.part_count + 1))
    actual_part_numbers = [part.part_number for part in parts]

    if actual_part_numbers != expected_part_numbers:
        raise VideoUploadValidationError(
            "upload parts must be ordered and complete from 1 to part_count"
        )


def create_video_upload(
    db: Session,
    storage: ObjectStorage,
    filename: str,
    content_type: str,
    size_bytes: int,
    part_count: int,
) -> VideoCreateResponse:
    video = Video(
        source=f"source/pending/{filename}",
        source_bucket=storage.bucket,
        source_filename=filename,
        source_content_type=content_type,
        source_size_bytes=size_bytes,
        status=ProcessingStatus.uploading,
    )
    db.add(video)
    db.flush()

    key = build_source_key(video.id, filename)
    try:
        upload = storage.create_multipart_upload(
            key=key,
            content_type=content_type,
            part_count=part_count,
        )
    except ObjectStorageError as exc:
        db.rollback()
        raise VideoUploadStorageError("storage upload creation failed") from exc

    video.source = key
    upload_session = UploadSession(
        video_id=video.id,
        bucket=upload.bucket,
        object_key=upload.key,
        object_upload_id=upload.upload_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        part_count=part_count,
        status=UploadStatus.active,
    )
    db.add(upload_session)

    db.commit()
    return VideoCreateResponse(
        video_id=video.id,
        bucket=upload.bucket,
        key=upload.key,
        upload_id=upload.upload_id,
        parts=[
            MultipartUploadPart(
                part_number=part.part_number,
                upload_url=part.upload_url,
            )
            for part in upload.parts
        ],
    )


def ingest_video(db: Session, source: str) -> Video:
    video = Video(source=source, status=ProcessingStatus.pending)
    db.add(video)
    db.flush()

    _create_renditions_and_jobs(db, video, max_attempts=settings.WORKER_JOB_RETRY_COUNT)

    db.commit()
    db.refresh(video)
    return video


def complete_video_upload(
    db: Session,
    storage: ObjectStorage,
    video_id: UUID,
    parts: list[CompletedUploadPartSchema],
) -> VideoState | None:
    video = _get_video_for_upload_completion(db, video_id)

    if video is None:
        return None

    upload_session = _get_active_upload_session_for_update(db, video)
    _validate_completed_upload_parts(upload_session, parts)

    try:
        storage.complete_multipart_upload(
            key=upload_session.object_key,
            upload_id=upload_session.object_upload_id,
            parts=[
                StorageCompletedUploadPart(
                    part_number=part.part_number,
                    etag=part.etag,
                )
                for part in parts
            ],
        )
        _validate_completed_upload_metadata(storage, upload_session)
    except ObjectStorageError as exc:
        upload_session.status = UploadStatus.failed
        upload_session.error = "storage upload completion failed"
        db.commit()
        raise VideoUploadStorageError("storage upload completion failed") from exc
    except VideoUploadStorageError as exc:
        try:
            _delete_invalid_completed_upload(storage, upload_session)
        except ObjectStorageError as cleanup_exc:
            upload_session.status = UploadStatus.failed
            upload_session.error = f"{exc}; cleanup failed"
            db.commit()
            raise VideoUploadStorageError(
                "storage upload cleanup failed"
            ) from cleanup_exc

        upload_session.status = UploadStatus.failed
        upload_session.error = str(exc)
        db.commit()
        raise

    video.status = ProcessingStatus.pending
    video.uploaded_at = datetime.now(timezone.utc)
    upload_session.status = UploadStatus.completed
    upload_session.completed_at = datetime.now(timezone.utc)
    _create_renditions_and_jobs(db, video, max_attempts=settings.WORKER_JOB_RETRY_COUNT)
    db.commit()
    db.refresh(video)

    return get_video_state(db, video.id)


def refresh_video_upload(
    db: Session,
    storage: ObjectStorage,
    video_id: UUID,
    part_count: int,
) -> VideoCreateResponse | None:
    video = db.query(Video).filter(Video.id == video_id).one_or_none()

    if video is None:
        return None

    upload_session = _get_active_upload_session(db, video)

    if part_count != upload_session.part_count:
        raise VideoUploadValidationError("refresh part count must match upload session")

    try:
        upload = storage.refresh_multipart_upload_urls(
            key=upload_session.object_key,
            upload_id=upload_session.object_upload_id,
            part_count=part_count,
        )
    except ObjectStorageError as exc:
        raise VideoUploadStorageError("storage upload URL refresh failed") from exc

    return VideoCreateResponse(
        video_id=video.id,
        bucket=upload.bucket,
        key=upload.key,
        upload_id=upload.upload_id,
        parts=[
            MultipartUploadPart(
                part_number=part.part_number,
                upload_url=part.upload_url,
            )
            for part in upload.parts
        ],
    )


def abort_video_upload(
    db: Session,
    storage: ObjectStorage,
    video_id: UUID,
) -> bool | None:
    video = db.query(Video).filter(Video.id == video_id).one_or_none()

    if video is None:
        return None

    upload_session = _get_active_upload_session(db, video)

    try:
        storage.abort_multipart_upload(
            key=upload_session.object_key,
            upload_id=upload_session.object_upload_id,
        )
    except ObjectStorageError as exc:
        upload_session.status = UploadStatus.failed
        upload_session.error = "storage upload abort failed"
        db.commit()
        raise VideoUploadStorageError("storage upload abort failed") from exc

    video.status = ProcessingStatus.failed
    upload_session.status = UploadStatus.aborted
    upload_session.aborted_at = datetime.now(timezone.utc)
    db.commit()
    return True


def get_video_state(db: Session, video_id: UUID) -> VideoState | None:
    video = (
        db.query(Video)
        .options(selectinload(Video.renditions))
        .filter(Video.id == video_id)
        .one_or_none()
    )

    if video is None:
        return None

    return VideoState(
        video_id=video.id,
        status=video.status,
        renditions=[
            RenditionState(
                resolution=rendition.resolution,
                status=rendition.status,
            )
            for rendition in video.renditions
        ],
    )


def list_videos(db: Session) -> list[VideoListItem]:
    videos = db.query(Video).order_by(Video.created_at.desc()).all()

    return [
        VideoListItem(
            video_id=video.id,
            title=video.source_filename or video.source,
            uploaded_at=video.uploaded_at,
            created_at=video.created_at,
            status=video.status,
            size_bytes=video.source_size_bytes,
        )
        for video in videos
    ]
