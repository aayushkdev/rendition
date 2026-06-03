from uuid import UUID

import pytest

from core.services.job_service import EncodingJobContext
from worker.processor import FfmpegEncodingProcessor

VIDEO_ID = UUID("11111111-1111-1111-1111-111111111111")
JOB_ID = UUID("22222222-2222-2222-2222-222222222222")
RENDITION_ID = UUID("33333333-3333-3333-3333-333333333333")


class RecordingStorage:
    bucket = "test-bucket"

    def __init__(self):
        self.downloads = []
        self.uploads = []

    def download_file(self, key: str, local_path: str) -> None:
        self.downloads.append({"key": key, "local_path": local_path})
        with open(local_path, "wb") as file:
            file.write(b"input")

    def upload_file(
        self,
        local_path: str,
        key: str,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        with open(local_path, "rb") as file:
            body = file.read()

        self.uploads.append(
            {
                "key": key,
                "content_type": content_type,
                "cache_control": cache_control,
                "body": body,
            }
        )


class FakeHlsEncoder:
    def __init__(self, create_segments: bool = True):
        self.create_segments = create_segments
        self.calls = []

    def encode(self, input_path, output_dir, resolution: str) -> None:
        self.calls.append(
            {
                "input_path": input_path,
                "output_dir": output_dir,
                "resolution": resolution,
            }
        )
        (output_dir / "segments").mkdir(parents=True)
        (output_dir / "index.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
        if self.create_segments:
            (output_dir / "segments" / "segment_00000.ts").write_bytes(b"segment-0")
            (output_dir / "segments" / "segment_00001.ts").write_bytes(b"segment-1")


def encoding_context() -> EncodingJobContext:
    return EncodingJobContext(
        job_id=JOB_ID,
        video_id=VIDEO_ID,
        rendition_id=RENDITION_ID,
        source="source/video/original.mp4",
        source_bucket="test-bucket",
        source_filename="original.mp4",
        resolution="720p",
        bitrate=2_800_000,
        attempt_count=1,
        max_attempts=3,
    )


def test_ffmpeg_processor_uploads_segments_then_playlist(tmp_path):
    storage = RecordingStorage()
    encoder = FakeHlsEncoder()
    processor = FfmpegEncodingProcessor(
        storage=storage,
        encoder=encoder,
        temp_root=tmp_path,
    )

    playlist_key = processor.process(encoding_context())

    assert playlist_key == ("hls/11111111-1111-1111-1111-111111111111/720p/index.m3u8")
    assert storage.downloads[0]["key"] == "source/video/original.mp4"
    assert encoder.calls[0]["resolution"] == "720p"
    assert [upload["key"] for upload in storage.uploads] == [
        "hls/11111111-1111-1111-1111-111111111111/720p/segments/segment_00000.ts",
        "hls/11111111-1111-1111-1111-111111111111/720p/segments/segment_00001.ts",
        "hls/11111111-1111-1111-1111-111111111111/720p/index.m3u8",
    ]
    assert storage.uploads[0]["content_type"] == "video/mp2t"
    assert storage.uploads[-1]["content_type"] == "application/vnd.apple.mpegurl"
    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_rejects_empty_hls_output(tmp_path):
    processor = FfmpegEncodingProcessor(
        storage=RecordingStorage(),
        encoder=FakeHlsEncoder(create_segments=False),
        temp_root=tmp_path,
    )

    with pytest.raises(RuntimeError, match="did not create any segments"):
        processor.process(encoding_context())

    assert list(tmp_path.iterdir()) == []
