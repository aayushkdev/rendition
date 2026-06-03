from dataclasses import dataclass
from uuid import UUID

from core.encoding.presets import get_hls_preset


class MasterPlaylistError(ValueError):
    pass


@dataclass(frozen=True)
class MasterPlaylistRendition:
    resolution: str
    output_path: str


def _playlist_uri(video_id: UUID, output_path: str) -> str:
    prefix = f"hls/{video_id}/"
    if not output_path.startswith(prefix):
        raise MasterPlaylistError("rendition output path is outside video HLS prefix")
    return output_path.removeprefix(prefix)


def build_hls_master_playlist(
    video_id: UUID,
    renditions: list[MasterPlaylistRendition],
) -> str:
    if not renditions:
        raise MasterPlaylistError("master playlist requires at least one rendition")

    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    for rendition in renditions:
        preset = get_hls_preset(rendition.resolution)
        lines.extend(
            [
                (
                    "#EXT-X-STREAM-INF:"
                    f"BANDWIDTH={preset.video_bitrate},"
                    f"RESOLUTION={preset.width}x{preset.height}"
                ),
                _playlist_uri(video_id, rendition.output_path),
            ]
        )

    return "\n".join(lines) + "\n"
