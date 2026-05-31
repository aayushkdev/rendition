from uuid import UUID


def _validate_key_part(value: str, field_name: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must be a single object key segment")
    return value


def build_source_key(video_id: UUID, filename: str) -> str:
    filename = _validate_key_part(filename, "filename")
    return f"source/{video_id}/{filename}"


def build_hls_master_key(video_id: UUID) -> str:
    return f"hls/{video_id}/master.m3u8"


def build_hls_playlist_key(video_id: UUID, resolution: str) -> str:
    resolution = _validate_key_part(resolution, "resolution")
    return f"hls/{video_id}/{resolution}/index.m3u8"


def build_hls_segment_key(video_id: UUID, resolution: str, segment_name: str) -> str:
    resolution = _validate_key_part(resolution, "resolution")
    segment_name = _validate_key_part(segment_name, "segment_name")
    return f"hls/{video_id}/{resolution}/segments/{segment_name}"
