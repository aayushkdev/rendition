from sqlalchemy.orm import Session

from core.models.enums import ProcessingStatus
from core.models.rendition import Rendition
from core.models.video import Video
from core.services.playback_service import (
    VideoPlaybackNotReadyError,
    build_playback_master_playlist,
    build_playback_variant_playlist,
    get_video_playback,
)
from core.storage import build_hls_master_key, build_hls_playlist_key
from tests.fakes import FakeObjectStorage


def create_playable_video(db_session: Session, storage: FakeObjectStorage) -> Video:
    video = Video(
        source="video.mp4",
        source_filename="video.mp4",
        status=ProcessingStatus.done,
    )
    db_session.add(video)
    db_session.flush()

    video.playback_path = build_hls_master_key(video.id)
    for resolution in ["720p", "480p"]:
        playlist_key = build_hls_playlist_key(video.id, resolution)
        db_session.add(
            Rendition(
                video_id=video.id,
                resolution=resolution,
                bitrate=1_000_000,
                status=ProcessingStatus.done,
                output_path=playlist_key,
            )
        )
        storage.upload_bytes(
            key=playlist_key,
            body=(
                "#EXTM3U\n"
                "#EXT-X-TARGETDURATION:6\n"
                "#EXTINF:6.0,\n"
                "segments/segment_00000.ts\n"
                "#EXT-X-ENDLIST\n"
            ).encode("utf-8"),
            content_type="application/vnd.apple.mpegurl",
        )

    playback_path = video.playback_path
    assert playback_path is not None
    storage.upload_bytes(
        key=playback_path,
        body=b"#EXTM3U\n",
        content_type="application/vnd.apple.mpegurl",
    )
    db_session.commit()
    return video


def test_get_video_playback_returns_hls_metadata(db_session):
    storage = FakeObjectStorage()
    video = create_playable_video(db_session, storage)

    playback = get_video_playback(
        db=db_session,
        storage=storage,
        video_id=video.id,
        master_playlist_url=f"/api/v1/videos/{video.id}/playback/master.m3u8",
    )

    assert playback is not None
    assert playback.playable is True
    assert playback.status == ProcessingStatus.done
    assert playback.streaming.type == "hls"
    assert playback.streaming.master_playlist_url.endswith("/master.m3u8")
    assert playback.streaming.expires_at is not None


def test_get_video_playback_rejects_unfinished_video(db_session):
    storage = FakeObjectStorage()
    video = Video(
        source="video.mp4",
        source_filename="video.mp4",
        status=ProcessingStatus.running,
    )
    db_session.add(video)
    db_session.commit()

    try:
        get_video_playback(
            db=db_session,
            storage=storage,
            video_id=video.id,
            master_playlist_url=f"/api/v1/videos/{video.id}/playback/master.m3u8",
        )
    except VideoPlaybackNotReadyError as exc:
        assert str(exc) == "Video is not ready for playback"
    else:
        raise AssertionError("expected playback validation to fail")


def test_build_playback_master_playlist_uses_api_variant_urls(db_session):
    storage = FakeObjectStorage()
    video = create_playable_video(db_session, storage)

    playlist = build_playback_master_playlist(
        db=db_session,
        video_id=video.id,
        variant_url_for_resolution=lambda resolution: f"/variant/{resolution}",
    )

    assert playlist is not None
    assert "/variant/720p" in playlist
    assert "/variant/480p" in playlist
    assert "hls/" not in playlist


def test_build_playback_variant_playlist_signs_segment_urls(db_session):
    storage = FakeObjectStorage()
    video = create_playable_video(db_session, storage)

    playlist = build_playback_variant_playlist(
        db=db_session,
        storage=storage,
        video_id=video.id,
        resolution="720p",
    )

    assert playlist is not None
    assert (
        f"http://playback.test/hls/{video.id}/720p/segments/segment_00000.ts"
        in playlist
    )
    assert "\nsegments/segment_00000.ts\n" not in playlist
