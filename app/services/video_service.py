from uuid import UUID
from sqlalchemy.orm import Session
from app.models.video import Video
from app.models.rendition import Rendition
from app.models.job import Job
from app.models.enums import ProcessingStatus
from app.schemas.video import VideoState, RenditionState

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


def get_video_state(db: Session, video_id: UUID) -> VideoState:

    video = db.query(Video).filter(Video.id == video_id).first()

    if video is None:
        return None

    return VideoState(
        video_id=str(video.id),
        status=video.status,
        renditions=[
            RenditionState(
                resolution=r.resolution,
                status=r.status,
            )
            for r in video.renditions
        ],
    )
