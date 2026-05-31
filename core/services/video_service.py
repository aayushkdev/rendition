from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from api.schemas.video import RenditionState, VideoState
from core.models.video import Video
from core.models.rendition import Rendition
from core.models.job import Job
from core.models.enums import ProcessingStatus

DEFAULT_RENDITIONS = [
    {"resolution": "1080p", "bitrate": 5_000_000},
    {"resolution": "720p", "bitrate": 2_500_000},
    {"resolution": "480p", "bitrate": 1_000_000},
]


def ingest_video(db: Session, source: str) -> Video:
    video = Video(
        source=source,
        status=ProcessingStatus.pending,
    )
    db.add(video)
    db.flush()

    for r in DEFAULT_RENDITIONS:
        rendition = Rendition(
            video_id=video.id,
            resolution=r["resolution"],
            bitrate=r["bitrate"],
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
