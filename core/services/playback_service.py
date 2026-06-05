from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from core.config import settings
from core.encoding import MasterPlaylistRendition, build_hls_master_playlist
from core.models.enums import ProcessingStatus
from core.models.video import Video
from core.storage import (
    ObjectStorage,
    ObjectStorageError,
    build_hls_master_key,
    build_hls_playlist_key,
    build_hls_segment_key,
    get_object_storage,
)

HLS_MASTER_CONTENT_TYPE = "application/vnd.apple.mpegurl"
HLS_MASTER_CACHE_CONTROL = "max-age=60"


@dataclass(frozen=True)
class PlaybackRenditionState:
    resolution: str
    status: ProcessingStatus


@dataclass(frozen=True)
class StreamingInfo:
    type: str
    master_playlist_url: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class VideoPlayback:
    video_id: UUID
    status: ProcessingStatus
    playable: bool
    streaming: StreamingInfo
    renditions: list[PlaybackRenditionState]


class VideoPlaybackNotReadyError(RuntimeError):
    pass


class VideoPlaybackStorageError(RuntimeError):
    pass


def _has_active_renditions(video: Video) -> bool:
    return any(
        rendition.status in {ProcessingStatus.pending, ProcessingStatus.running}
        for rendition in video.renditions
    )


def _completed_renditions(video: Video) -> list[MasterPlaylistRendition]:
    return [
        MasterPlaylistRendition(
            resolution=rendition.resolution,
            output_path=rendition.output_path,
        )
        for rendition in video.renditions
        if rendition.status == ProcessingStatus.done
        and rendition.output_path is not None
    ]


def publish_master_playlist_if_ready(
    video: Video,
    storage: ObjectStorage | None = None,
) -> str | None:
    if _has_active_renditions(video):
        return None

    completed_renditions = _completed_renditions(video)
    if not completed_renditions:
        video.playback_path = None
        return None

    playback_path = build_hls_master_key(video.id)
    playlist = build_hls_master_playlist(video.id, completed_renditions)
    object_storage = storage or get_object_storage()
    object_storage.upload_bytes(
        key=playback_path,
        body=playlist.encode("utf-8"),
        content_type=HLS_MASTER_CONTENT_TYPE,
        cache_control=HLS_MASTER_CACHE_CONTROL,
    )
    video.playback_path = playback_path
    return playback_path


def _get_video_with_renditions(db: Session, video_id: UUID) -> Video | None:
    return (
        db.query(Video)
        .options(selectinload(Video.renditions))
        .filter(Video.id == video_id)
        .one_or_none()
    )


def _validate_playable_video(video: Video) -> None:
    if video.status != ProcessingStatus.done:
        raise VideoPlaybackNotReadyError("Video is not ready for playback")

    if video.playback_path is None:
        raise VideoPlaybackNotReadyError("Video playback playlist is not available")

    if not _completed_renditions(video):
        raise VideoPlaybackNotReadyError("Video has no completed renditions")


def get_video_playback(
    db: Session,
    storage: ObjectStorage,
    video_id: UUID,
    master_playlist_url: str,
) -> VideoPlayback | None:
    video = _get_video_with_renditions(db, video_id)
    if video is None:
        return None

    _validate_playable_video(video)

    try:
        storage.generate_playback_url(video.playback_path or "")
    except ObjectStorageError as exc:
        raise VideoPlaybackStorageError("Storage unavailable") from exc

    return VideoPlayback(
        video_id=video.id,
        status=video.status,
        playable=True,
        streaming=StreamingInfo(
            type="hls",
            master_playlist_url=master_playlist_url,
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=settings.STORAGE_PRESIGNED_URL_EXPIRES_SECONDS),
        ),
        renditions=[
            PlaybackRenditionState(
                resolution=rendition.resolution,
                status=rendition.status,
            )
            for rendition in video.renditions
        ],
    )


def build_playback_master_playlist(
    db: Session,
    video_id: UUID,
    variant_url_for_resolution: Callable[[str], str],
) -> str | None:
    video = _get_video_with_renditions(db, video_id)
    if video is None:
        return None

    _validate_playable_video(video)

    playlist = build_hls_master_playlist(video.id, _completed_renditions(video))
    rewritten_lines: list[str] = []
    for line in playlist.splitlines():
        if line and not line.startswith("#"):
            resolution = line.split("/", 1)[0]
            rewritten_lines.append(str(variant_url_for_resolution(resolution)))
            continue
        rewritten_lines.append(line)

    return "\n".join(rewritten_lines) + "\n"


def build_playback_variant_playlist(
    db: Session,
    storage: ObjectStorage,
    video_id: UUID,
    resolution: str,
) -> str | None:
    video = _get_video_with_renditions(db, video_id)
    if video is None:
        return None

    _validate_playable_video(video)

    playlist_key = build_hls_playlist_key(video_id, resolution)
    if not any(
        rendition.resolution == resolution
        and rendition.status == ProcessingStatus.done
        and rendition.output_path == playlist_key
        for rendition in video.renditions
    ):
        raise VideoPlaybackNotReadyError("Rendition is not ready for playback")

    try:
        playlist = storage.download_bytes(playlist_key).decode("utf-8")
    except (ObjectStorageError, UnicodeDecodeError) as exc:
        raise VideoPlaybackStorageError("Storage unavailable") from exc

    rewritten_lines: list[str] = []
    for line in playlist.splitlines():
        if not line or line.startswith("#"):
            rewritten_lines.append(line)
            continue

        if "://" in line:
            rewritten_lines.append(line)
            continue

        segment_name = line.removeprefix("segments/")
        segment_key = build_hls_segment_key(video_id, resolution, segment_name)
        try:
            rewritten_lines.append(storage.generate_playback_url(segment_key))
        except ObjectStorageError as exc:
            raise VideoPlaybackStorageError("Storage unavailable") from exc

    return "\n".join(rewritten_lines) + "\n"
