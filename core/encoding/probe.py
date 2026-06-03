import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VideoProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoSourceMetadata:
    width: int
    height: int
    bitrate: int | None
    duration_seconds: float | None


def _optional_int(value: Any) -> int | None:
    if value in {None, "", "N/A"}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value in {None, "", "N/A"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_ffprobe_output(output: str) -> VideoSourceMetadata:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise VideoProbeError("ffprobe returned invalid JSON") from exc

    streams = payload.get("streams") or []
    if not streams:
        raise VideoProbeError("ffprobe did not find a video stream")

    video_stream = streams[0]
    width = _optional_int(video_stream.get("width"))
    height = _optional_int(video_stream.get("height"))
    if width is None or height is None:
        raise VideoProbeError("ffprobe did not return source dimensions")

    format_info = payload.get("format") or {}
    bitrate = _optional_int(video_stream.get("bit_rate")) or _optional_int(
        format_info.get("bit_rate")
    )
    duration_seconds = _optional_float(video_stream.get("duration")) or _optional_float(
        format_info.get("duration")
    )

    return VideoSourceMetadata(
        width=width,
        height=height,
        bitrate=bitrate,
        duration_seconds=duration_seconds,
    )


class VideoProber:
    def probe(self, input_path: Path) -> VideoSourceMetadata:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,bit_rate,duration",
            "-show_entries",
            "format=bit_rate,duration",
            "-of",
            "json",
            str(input_path),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise VideoProbeError("failed to start ffprobe") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or "ffprobe failed"
            raise VideoProbeError(message)

        return parse_ffprobe_output(completed.stdout)
