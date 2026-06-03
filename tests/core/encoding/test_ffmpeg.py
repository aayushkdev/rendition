from pathlib import Path

import pytest

from core.encoding import (
    EncodingPresetError,
    HlsEncoder,
    build_hls_ffmpeg_command,
    get_hls_preset,
)
from core.encoding.ffmpeg import FfmpegError


def test_get_hls_preset_returns_known_resolution():
    preset = get_hls_preset("720p")

    assert preset.width == 1280
    assert preset.height == 720
    assert preset.video_bitrate == 2_800_000
    assert preset.ffmpeg_video_bitrate == "2800k"


def test_get_hls_preset_rejects_unknown_resolution():
    with pytest.raises(EncodingPresetError):
        get_hls_preset("144p")


def test_build_hls_ffmpeg_command_contains_expected_hls_options():
    command = build_hls_ffmpeg_command(
        input_path=Path("/tmp/input.mp4"),
        preset=get_hls_preset("480p"),
    )

    assert command[0] == "ffmpeg"
    assert "-hls_playlist_type" in command
    assert "vod" in command
    assert "-hls_segment_filename" in command
    assert "segments/segment_%05d.ts" in command
    assert "index.m3u8" in command
    assert (
        "scale=w=854:h=480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2"
        in command
    )


def test_hls_encoder_raises_when_playlist_missing(monkeypatch, tmp_path):
    class CompletedProcess:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(
        "core.encoding.ffmpeg.subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess(),
    )

    encoder = HlsEncoder()

    with pytest.raises(FfmpegError, match="did not create HLS playlist"):
        encoder.encode(
            input_path=tmp_path / "input.mp4",
            output_dir=tmp_path / "output",
            resolution="720p",
        )
