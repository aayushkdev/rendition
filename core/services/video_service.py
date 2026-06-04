from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from api.schemas.video import (
    RenditionState,
    VideoListItem,
    VideoState,
)
from core.config import settings
from core.encoding import DEFAULT_HLS_RENDITIONS
from core.models.video import Video
from core.models.rendition import Rendition
from core.models.job import Job
from core.models.enums import ProcessingStatus


class VideoNotFoundError(LookupError):
    pass


def _create_renditions_and_jobs(
    db: Session,
    video: Video,
    max_attempts: int,
) -> list[Job]:
    if video.renditions:
        return []

    jobs: list[Job] = []
    for rendition_config in DEFAULT_HLS_RENDITIONS:
        rendition = Rendition(
            video_id=video.id,
            resolution=rendition_config.resolution,
            bitrate=rendition_config.video_bitrate,
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
        db.flush()
        jobs.append(job)

    return jobs


def ingest_video(db: Session, source: str) -> Video:
    video = Video(source=source, status=ProcessingStatus.pending)
    db.add(video)
    db.flush()

    _create_renditions_and_jobs(db, video, max_attempts=settings.WORKER_JOB_RETRY_COUNT)

    db.commit()
    db.refresh(video)
    return video


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


def list_videos(
    db: Session,
    *,
    status: ProcessingStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[VideoListItem]:
    query = db.query(Video)

    if status is not None:
        query = query.filter(Video.status == status)

    videos = (
        query.order_by(Video.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

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
