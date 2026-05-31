from uuid import UUID

from core.storage import (
    build_hls_master_key,
    build_hls_playlist_key,
    build_hls_segment_key,
    build_source_key,
)

VIDEO_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_build_source_key():
    assert build_source_key(VIDEO_ID, "input.mp4") == (
        "source/11111111-1111-1111-1111-111111111111/input.mp4"
    )


def test_build_hls_keys():
    assert (
        build_hls_master_key(VIDEO_ID)
        == "hls/11111111-1111-1111-1111-111111111111/master.m3u8"
    )
    assert build_hls_playlist_key(VIDEO_ID, "720p") == (
        "hls/11111111-1111-1111-1111-111111111111/720p/index.m3u8"
    )
    assert build_hls_segment_key(VIDEO_ID, "720p", "segment-00001.ts") == (
        "hls/11111111-1111-1111-1111-111111111111/720p/segments/segment-00001.ts"
    )


def test_key_builders_reject_path_segments():
    for key_builder, args in [
        (build_source_key, (VIDEO_ID, "../input.mp4")),
        (build_hls_playlist_key, (VIDEO_ID, "../720p")),
        (build_hls_segment_key, (VIDEO_ID, "720p", "../segment.ts")),
    ]:
        try:
            key_builder(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("expected key builder to reject path segment")
