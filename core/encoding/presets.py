from dataclasses import dataclass

from core.encoding.probe import VideoSourceMetadata


class EncodingPresetError(ValueError):
    pass


FALLBACK_HLS_RESOLUTION = "144p"


@dataclass(frozen=True)
class EncodingPreset:
    resolution: str
    width: int
    height: int
    video_bitrate: int
    audio_bitrate: str = "128k"

    @property
    def ffmpeg_video_bitrate(self) -> str:
        return f"{self.video_bitrate // 1000}k"


HLS_PRESETS: dict[str, EncodingPreset] = {
    "1080p": EncodingPreset(
        resolution="1080p",
        width=1920,
        height=1080,
        video_bitrate=5_000_000,
    ),
    "720p": EncodingPreset(
        resolution="720p",
        width=1280,
        height=720,
        video_bitrate=2_800_000,
    ),
    "480p": EncodingPreset(
        resolution="480p",
        width=854,
        height=480,
        video_bitrate=1_200_000,
    ),
    "360p": EncodingPreset(
        resolution="360p",
        width=640,
        height=360,
        video_bitrate=800_000,
        audio_bitrate="96k",
    ),
    "240p": EncodingPreset(
        resolution="240p",
        width=426,
        height=240,
        video_bitrate=400_000,
        audio_bitrate="64k",
    ),
    "144p": EncodingPreset(
        resolution="144p",
        width=256,
        height=144,
        video_bitrate=150_000,
        audio_bitrate="48k",
    ),
}

DEFAULT_HLS_RENDITIONS = list(HLS_PRESETS.values())


def is_hls_preset_applicable(
    preset: EncodingPreset,
    metadata: VideoSourceMetadata,
    bitrate_headroom: float = 1.25,
) -> bool:
    if preset.resolution == FALLBACK_HLS_RESOLUTION:
        return True

    if preset.width > metadata.width or preset.height > metadata.height:
        return False

    if metadata.bitrate is None:
        return True

    return preset.video_bitrate <= metadata.bitrate * bitrate_headroom


def get_hls_preset(resolution: str) -> EncodingPreset:
    return HLS_PRESETS.get(resolution, HLS_PRESETS[FALLBACK_HLS_RESOLUTION])
