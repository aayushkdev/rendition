from dataclasses import dataclass


class EncodingPresetError(ValueError):
    pass


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
}

DEFAULT_HLS_RENDITIONS = list(HLS_PRESETS.values())


def get_hls_preset(resolution: str) -> EncodingPreset:
    try:
        return HLS_PRESETS[resolution]
    except KeyError as exc:
        raise EncodingPresetError(f"unsupported HLS resolution: {resolution}") from exc
