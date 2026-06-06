from uuid import UUID

import pytest

from core.encoding import VideoSourceMetadata
from core.services.job_service import EncodingJobContext
from tests.fakes import FakeHlsEncoder, FakeObjectStorage, FakeVideoProber
from worker.processor import EncodingJobOwnershipLost, FfmpegEncodingProcessor

VIDEO_ID = UUID("11111111-1111-1111-1111-111111111111")
JOB_ID = UUID("22222222-2222-2222-2222-222222222222")
RENDITION_ID = UUID("33333333-3333-3333-3333-333333333333")


def encoding_context(
    *,
    resolution: str = "720p",
    bitrate: int = 2_800_000,
) -> EncodingJobContext:
    return EncodingJobContext(
        job_id=JOB_ID,
        video_id=VIDEO_ID,
        rendition_id=RENDITION_ID,
        source="source/video/original.mp4",
        source_bucket="test-bucket",
        source_filename="original.mp4",
        resolution=resolution,
        bitrate=bitrate,
        attempt_count=1,
        max_attempts=3,
        worker_id="test-worker",
    )


def test_ffmpeg_processor_uploads_segments_then_playlist(tmp_path):
    storage = FakeObjectStorage()
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
    assert [upload["key"] for upload in storage.uploaded_files] == [
        "hls/11111111-1111-1111-1111-111111111111/720p/segments/segment_00000.ts",
        "hls/11111111-1111-1111-1111-111111111111/720p/segments/segment_00001.ts",
        "hls/11111111-1111-1111-1111-111111111111/720p/index.m3u8",
    ]
    assert storage.uploaded_files[0]["content_type"] == "video/mp2t"
    assert storage.uploaded_files[-1]["content_type"] == "application/vnd.apple.mpegurl"
    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_rejects_empty_hls_output(tmp_path):
    processor = FfmpegEncodingProcessor(
        storage=FakeObjectStorage(),
        encoder=FakeHlsEncoder(create_segments=False),
        prober=FakeVideoProber(),
        temp_root=tmp_path,
    )

    with pytest.raises(RuntimeError, match="did not create any segments"):
        processor.process(encoding_context())

    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_skips_inapplicable_rendition(tmp_path):
    storage = FakeObjectStorage()
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
    assert storage.uploaded_files == []
    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_encodes_fallback_rendition_for_tiny_source(tmp_path):
    storage = FakeObjectStorage()
    encoder = FakeHlsEncoder()
    metadata = VideoSourceMetadata(
        width=192,
        height=144,
        bitrate=80_000,
        duration_seconds=30.0,
    )
    processor = FfmpegEncodingProcessor(
        storage=storage,
        encoder=encoder,
        prober=FakeVideoProber(metadata),
        temp_root=tmp_path,
    )

    result = processor.process(encoding_context(resolution="144p", bitrate=150_000))

    assert result.output_path == (
        "hls/11111111-1111-1111-1111-111111111111/144p/index.m3u8"
    )
    assert result.skipped_reason is None
    assert encoder.calls[0]["resolution"] == "144p"
    assert storage.uploaded_files
    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_encodes_fallback_for_low_bitrate_432p_source(tmp_path):
    storage = FakeObjectStorage()
    encoder = FakeHlsEncoder()
    metadata = VideoSourceMetadata(
        width=768,
        height=432,
        bitrate=47_000,
        duration_seconds=615.4,
    )
    processor = FfmpegEncodingProcessor(
        storage=storage,
        encoder=encoder,
        prober=FakeVideoProber(metadata),
        temp_root=tmp_path,
    )

    result = processor.process(encoding_context(resolution="144p", bitrate=150_000))

    assert result.output_path == (
        "hls/11111111-1111-1111-1111-111111111111/144p/index.m3u8"
    )
    assert result.skipped_reason is None
    assert encoder.calls[0]["resolution"] == "144p"
    assert storage.uploaded_files
    assert list(tmp_path.iterdir()) == []


def test_ffmpeg_processor_does_not_upload_after_cancellation(tmp_path):
    storage = FakeObjectStorage()
    encoder = FakeHlsEncoder()
    processor = FfmpegEncodingProcessor(
        storage=storage,
        encoder=encoder,
        prober=FakeVideoProber(),
        temp_root=tmp_path,
    )

    def is_cancelled():
        return bool(encoder.calls)

    with pytest.raises(EncodingJobOwnershipLost):
        processor.process(encoding_context(), is_cancelled=is_cancelled)

    assert encoder.calls
    assert storage.uploaded_files == []
    assert list(tmp_path.iterdir()) == []
