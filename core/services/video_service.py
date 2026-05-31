from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from api.schemas.video import (
    CompletedUploadPart as CompletedUploadPartSchema,
    MultipartUploadPart,
    RenditionState,
    VideoCreateResponse,
    VideoState,
)
from core.models.video import Video
from core.models.rendition import Rendition
from core.models.job import Job
from core.models.enums import ProcessingStatus
from core.storage import (
    CompletedUploadPart as StorageCompletedUploadPart,
    ObjectStorage,
    ObjectStorageError,
)


class VideoUploadError(RuntimeError):
    pass


class VideoUploadConflictError(VideoUploadError):
    pass


class VideoUploadStorageError(VideoUploadError):
    pass


DEFAULT_RENDITIONS = [
    {"resolution": "1080p", "bitrate": 5_000_000},
    {"resolution": "720p", "bitrate": 2_500_000},
    {"resolution": "480p", "bitrate": 1_000_000},
]


def _build_source_key(video_id: UUID, filename: str) -> str:
    return f"source/{video_id}/{filename}"


def _create_renditions_and_jobs(db: Session, video: Video) -> None:
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
        )
        db.add(job)


def _require_active_upload(video: Video) -> tuple[str, str]:
    if video.status != ProcessingStatus.uploading:
        raise VideoUploadConflictError("video upload is not active")

    if not video.source or not video.multipart_upload_id:
        raise VideoUploadConflictError("video upload is missing multipart state")

    return video.source, video.multipart_upload_id


def create_video_upload(
    db: Session,
    storage: ObjectStorage,
    filename: str,
    content_type: str,
    size_bytes: int,
    part_count: int,
) -> VideoCreateResponse:
    video = Video(
        source="",
        source_bucket=storage.bucket,
        source_filename=filename,
        source_content_type=content_type,
        source_size_bytes=size_bytes,
        status=ProcessingStatus.uploading,
    )
    db.add(video)
    db.flush()

    key = _build_source_key(video.id, filename)
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
    video.multipart_upload_id = upload.upload_id

    db.commit()
    return VideoCreateResponse(
        video_id=str(video.id),
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

    _create_renditions_and_jobs(db, video)

    db.commit()
    db.refresh(video)
    return video


def complete_video_upload(
    db: Session,
    storage: ObjectStorage,
    video_id: UUID,
    parts: list[CompletedUploadPartSchema],
) -> VideoState | None:
    video = (
        db.query(Video)
        .options(selectinload(Video.renditions))
        .filter(Video.id == video_id)
        .one_or_none()
    )

    if video is None:
        return None

    key, upload_id = _require_active_upload(video)

    try:
        storage.complete_multipart_upload(
            key=key,
            upload_id=upload_id,
            parts=[
                StorageCompletedUploadPart(
                    part_number=part.part_number,
                    etag=part.etag,
                )
                for part in parts
            ],
        )
        if not storage.object_exists(key):
            raise VideoUploadStorageError("completed upload object was not found")
    except ObjectStorageError as exc:
        raise VideoUploadStorageError("storage upload completion failed") from exc

    video.status = ProcessingStatus.pending
    video.uploaded_at = datetime.now(timezone.utc)
    _create_renditions_and_jobs(db, video)
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

    key, upload_id = _require_active_upload(video)

    try:
        upload = storage.refresh_multipart_upload_urls(
            key=key,
            upload_id=upload_id,
            part_count=part_count,
        )
    except ObjectStorageError as exc:
        raise VideoUploadStorageError("storage upload URL refresh failed") from exc

    return VideoCreateResponse(
        video_id=str(video.id),
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

    key, upload_id = _require_active_upload(video)

    try:
        storage.abort_multipart_upload(
            key=key,
            upload_id=upload_id,
        )
    except ObjectStorageError as exc:
        raise VideoUploadStorageError("storage upload abort failed") from exc

    video.status = ProcessingStatus.failed
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
        video_id=str(video.id),
        status=video.status.value,
        renditions=[
            RenditionState(
                resolution=rendition.resolution,
                status=rendition.status.value,
            )
            for rendition in video.renditions
        ],
    )
