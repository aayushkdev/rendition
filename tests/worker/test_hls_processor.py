from pathlib import Path
from uuid import UUID

import pytest

from core.encoding.ffmpeg import HlsEncoder
from core.encoding.probe import VideoProber
from core.encoding import VideoSourceMetadata
from core.services.job_service import EncodingJobContext
from core.storage.s3 import CompletedUploadPart, MultipartUploadSession, ObjectMetadata
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

    def create_multipart_upload(
        self,
        key: str,
        content_type: str,
        part_count: int,
    ) -> MultipartUploadSession:
        raise NotImplementedError

    def refresh_multipart_upload_urls(
        self,
        key: str,
        upload_id: str,
        part_count: int,
    ) -> MultipartUploadSession:
        raise NotImplementedError

    def complete_multipart_upload(
        self,
        key: str,
        upload_id: str,
        parts: list[CompletedUploadPart],
    ) -> None:
        raise NotImplementedError

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        raise NotImplementedError

    def object_exists(self, key: str) -> bool:
        raise NotImplementedError

    def get_object_metadata(self, key: str) -> ObjectMetadata | None:
        raise NotImplementedError

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

    def upload_bytes(
        self,
        key: str,
        body: bytes,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        raise NotImplementedError

    def delete_object(self, key: str) -> None:
        raise NotImplementedError

    def generate_presigned_download_url(self, key: str) -> str:
        raise NotImplementedError

    def generate_playback_url(self, key: str) -> str:
        raise NotImplementedError


class FakeHlsEncoder(HlsEncoder):
    def __init__(self, create_segments: bool = True):
        self.create_segments = create_segments
        self.calls = []

    def encode(self, input_path: Path, output_dir: Path, resolution: str) -> None:
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


class FakeVideoProber(VideoProber):
    def __init__(
        self,
        metadata: VideoSourceMetadata = VideoSourceMetadata(
            width=1280,
            height=720,
            bitrate=3_000_000,
            duration_seconds=42.5,
        ),
    ):
        self.metadata = metadata
        self.calls = []

    def probe(self, input_path: Path) -> VideoSourceMetadata:
        self.calls.append(input_path)
        return self.metadata


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
        prober=FakeVideoProber(),
        temp_root=tmp_path,
    )

    result = processor.process(encoding_context())

    assert result.output_path == (
        "hls/11111111-1111-1111-1111-111111111111/720p/index.m3u8"
    )
    assert result.source_metadata == VideoSourceMetadata(
        width=1280,
        height=720,
        bitrate=3_000_000,
        duration_seconds=42.5,
    )
    assert result.skipped_reason is None
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
        prober=FakeVideoProber(),
        temp_root=tmp_path,
    )

    with pytest.raises(RuntimeError, match="did not create any segments"):
        processor.process(encoding_context())

    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_skips_inapplicable_rendition(tmp_path):
    storage = RecordingStorage()
    encoder = FakeHlsEncoder()
    metadata = VideoSourceMetadata(
        width=854,
        height=480,
        bitrate=1_000_000,
        duration_seconds=30.0,
    )
    processor = FfmpegEncodingProcessor(
        storage=storage,
        encoder=encoder,
        prober=FakeVideoProber(metadata),
        temp_root=tmp_path,
    )

    result = processor.process(encoding_context())

    assert result.output_path is None
    assert result.source_metadata == metadata
    assert result.skipped_reason == "720p is not applicable for 854x480 source"
    assert encoder.calls == []
    assert storage.uploads == []
    assert list(tmp_path.iterdir()) == []
