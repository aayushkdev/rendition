from pathlib import Path

import pytest

from core.encoding import (
    EncodingPresetError,
    HlsEncoder,
    VideoProbeError,
    VideoSourceMetadata,
    build_hls_ffmpeg_command,
    get_hls_preset,
    is_hls_preset_applicable,
    parse_ffprobe_output,
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


def test_hls_preset_applicability_uses_dimensions_and_soft_bitrate():
    assert is_hls_preset_applicable(
        get_hls_preset("720p"),
        VideoSourceMetadata(
            width=1280,
            height=720,
            bitrate=2_300_000,
            duration_seconds=30.0,
        ),
    )
    assert not is_hls_preset_applicable(
        get_hls_preset("720p"),
        VideoSourceMetadata(
            width=854,
            height=480,
            bitrate=3_000_000,
            duration_seconds=30.0,
        ),
    )
    assert not is_hls_preset_applicable(
        get_hls_preset("720p"),
        VideoSourceMetadata(
            width=1280,
            height=720,
            bitrate=2_000_000,
            duration_seconds=30.0,
        ),
    )


def test_parse_ffprobe_output_uses_stream_and_format_metadata():
    metadata = parse_ffprobe_output("""
        {
          "streams": [
            {"width": 1920, "height": 1080, "duration": "60.25"}
          ],
          "format": {"bit_rate": "4500000", "duration": "60.30"}
        }
        """)

    assert metadata == VideoSourceMetadata(
        width=1920,
        height=1080,
        bitrate=4_500_000,
        duration_seconds=60.25,
    )


def test_parse_ffprobe_output_rejects_missing_dimensions():
    with pytest.raises(VideoProbeError, match="source dimensions"):
        parse_ffprobe_output('{"streams": [{"width": 1920}], "format": {}}')


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
