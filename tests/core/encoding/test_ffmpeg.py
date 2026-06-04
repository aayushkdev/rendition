from pathlib import Path
from uuid import UUID

import pytest

from core.encoding import (
    EncodingPresetError,
    HlsEncoder,
    VideoProbeError,
    VideoProber,
    VideoSourceMetadata,
    build_hls_ffmpeg_command,
    build_hls_master_playlist,
    get_hls_preset,
    is_hls_preset_applicable,
    MasterPlaylistRendition,
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


def test_video_prober_runs_ffprobe_and_parses_output(monkeypatch, tmp_path):
    class CompletedProcess:
        returncode = 0
        stdout = """
        {
          "streams": [
            {"width": 1280, "height": 720, "bit_rate": "2500000"}
          ],
          "format": {"duration": "42.5"}
        }
        """
        stderr = ""

    calls = []

    def run(command, capture_output, check, text):
        calls.append(
            {
                "command": command,
                "capture_output": capture_output,
                "check": check,
                "text": text,
            }
        )
        return CompletedProcess()

    monkeypatch.setattr("core.encoding.probe.subprocess.run", run)

    metadata = VideoProber().probe(tmp_path / "input.mp4")

    assert metadata == VideoSourceMetadata(
        width=1280,
        height=720,
        bitrate=2_500_000,
        duration_seconds=42.5,
    )
    assert calls[0]["command"][0] == "ffprobe"
    assert str(tmp_path / "input.mp4") in calls[0]["command"]
    assert calls[0]["capture_output"] is True
    assert calls[0]["check"] is False
    assert calls[0]["text"] is True


def test_video_prober_raises_on_ffprobe_failure(monkeypatch, tmp_path):
    class CompletedProcess:
        returncode = 1
        stdout = ""
        stderr = "invalid input"

    monkeypatch.setattr(
        "core.encoding.probe.subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess(),
    )

    with pytest.raises(VideoProbeError, match="invalid input"):
        VideoProber().probe(tmp_path / "input.mp4")


def test_video_prober_wraps_startup_failures(monkeypatch, tmp_path):
    def fail_start(*_args, **_kwargs):
        raise OSError("ffprobe missing")

    monkeypatch.setattr("core.encoding.probe.subprocess.run", fail_start)

    with pytest.raises(VideoProbeError, match="failed to start ffprobe"):
        VideoProber().probe(tmp_path / "input.mp4")


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


def test_build_hls_master_playlist_lists_completed_renditions():
    playlist = build_hls_master_playlist(
        video_id=UUID("11111111-1111-1111-1111-111111111111"),
        renditions=[
            MasterPlaylistRendition(
                resolution="720p",
                output_path=(
                    "hls/11111111-1111-1111-1111-111111111111/720p/index.m3u8"
                ),
            ),
            MasterPlaylistRendition(
                resolution="480p",
                output_path=(
                    "hls/11111111-1111-1111-1111-111111111111/480p/index.m3u8"
                ),
            ),
        ],
    )

    assert playlist == (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1280x720\n"
        "720p/index.m3u8\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=1200000,RESOLUTION=854x480\n"
        "480p/index.m3u8\n"
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


def test_hls_encoder_wraps_ffmpeg_startup_failure(monkeypatch, tmp_path):
    def fail_start(*_args, **_kwargs):
        raise OSError("ffmpeg missing")

    monkeypatch.setattr("core.encoding.ffmpeg.subprocess.run", fail_start)

    with pytest.raises(FfmpegError, match="failed to start ffmpeg"):
        HlsEncoder().encode(
            input_path=tmp_path / "input.mp4",
            output_dir=tmp_path / "output",
            resolution="720p",
        )


def test_hls_encoder_raises_on_ffmpeg_nonzero_return(monkeypatch, tmp_path):
    class CompletedProcess:
        returncode = 1
        stderr = "invalid codec"

    monkeypatch.setattr(
        "core.encoding.ffmpeg.subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess(),
    )

    with pytest.raises(FfmpegError, match="invalid codec"):
        HlsEncoder().encode(
            input_path=tmp_path / "input.mp4",
            output_dir=tmp_path / "output",
            resolution="720p",
        )
