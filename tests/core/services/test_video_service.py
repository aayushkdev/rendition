from core.models.enums import ProcessingStatus
from core.models.job import Job
from core.models.rendition import Rendition
from core.models.video import Video
from core.services.video_service import (
    DEFAULT_RENDITIONS,
    get_video_state,
    ingest_video,
)


def test_ingest_video_creates_video_renditions_and_jobs(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")

    assert video.source == "s3://input/video.mp4"
    assert video.status == ProcessingStatus.pending

    assert db_session.query(Video).count() == 1
    assert db_session.query(Rendition).count() == len(DEFAULT_RENDITIONS)
    assert db_session.query(Job).count() == len(DEFAULT_RENDITIONS)

    renditions = db_session.query(Rendition).order_by(Rendition.bitrate.desc()).all()
    assert [rendition.resolution for rendition in renditions] == [
        "1080p",
        "720p",
        "480p",
    ]
    assert all(rendition.status == ProcessingStatus.pending for rendition in renditions)


def test_get_video_state_returns_video_with_renditions(db_session):
    video = ingest_video(db_session, "s3://input/video.mp4")

    state = get_video_state(db_session, video.id)

    assert state.id == video.id
    assert len(state.renditions) == len(DEFAULT_RENDITIONS)
