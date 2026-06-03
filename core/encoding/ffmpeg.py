import subprocess
from pathlib import Path

from core.encoding.presets import EncodingPreset, get_hls_preset


class FfmpegError(RuntimeError):
    pass


def build_hls_ffmpeg_command(
    input_path: Path,
    preset: EncodingPreset,
) -> list[str]:
    scale_filter = (
        f"scale=w={preset.width}:h={preset.height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={preset.width}:{preset.height}:(ow-iw)/2:(oh-ih)/2"
    )

    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        scale_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        preset.ffmpeg_video_bitrate,
        "-maxrate",
        preset.ffmpeg_video_bitrate,
        "-bufsize",
        preset.ffmpeg_video_bitrate,
        "-c:a",
        "aac",
        "-b:a",
        preset.audio_bitrate,
        "-f",
        "hls",
        "-hls_time",
        "6",
        "-hls_playlist_type",
        "vod",
        "-hls_segment_filename",
        "segments/segment_%05d.ts",
        "index.m3u8",
    ]


class HlsEncoder:
    def encode(
        self,
        input_path: Path,
        output_dir: Path,
        resolution: str,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "segments").mkdir(parents=True, exist_ok=True)
        command = build_hls_ffmpeg_command(
            input_path=input_path,
            preset=get_hls_preset(resolution),
        )

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                cwd=output_dir,
                text=True,
            )
        except OSError as exc:
            raise FfmpegError("failed to start ffmpeg") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or "ffmpeg failed"
            raise FfmpegError(message)

        if not (output_dir / "index.m3u8").is_file():
            raise FfmpegError("ffmpeg did not create HLS playlist")
