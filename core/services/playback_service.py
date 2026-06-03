from core.encoding import MasterPlaylistRendition, build_hls_master_playlist
from core.models.enums import ProcessingStatus
from core.models.video import Video
from core.storage import ObjectStorage, build_hls_master_key, get_object_storage

HLS_MASTER_CONTENT_TYPE = "application/vnd.apple.mpegurl"
HLS_MASTER_CACHE_CONTROL = "max-age=60"


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
