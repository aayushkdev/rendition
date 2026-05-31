from botocore.exceptions import BotoCoreError

import pytest

from core.storage import CompletedUploadPart, ObjectStorageError
from core.storage.s3 import S3ObjectStorage


class FakeS3Client:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self):
        self.calls = []
        self.fail_presign = False
        self.head_response = {
            "ContentLength": 12345,
            "ContentType": "video/mp4",
        }

    def create_multipart_upload(self, **kwargs):
        self.calls.append(("create_multipart_upload", kwargs))
        return {"UploadId": "upload-123"}

    def generate_presigned_url(self, operation_name, Params, ExpiresIn):
        if self.fail_presign:
            raise BotoCoreError()

        self.calls.append(
            (
                "generate_presigned_url",
                {
                    "operation_name": operation_name,
                    "Params": Params,
                    "ExpiresIn": ExpiresIn,
                },
            )
        )
        return f"http://storage.test/{operation_name}/{Params['Key']}"

    def complete_multipart_upload(self, **kwargs):
        self.calls.append(("complete_multipart_upload", kwargs))

    def abort_multipart_upload(self, **kwargs):
        self.calls.append(("abort_multipart_upload", kwargs))

    def upload_file(self, **kwargs):
        self.calls.append(("upload_file", kwargs))

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))

    def download_file(self, **kwargs):
        self.calls.append(("download_file", kwargs))

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return self.head_response


def make_storage():
    storage = S3ObjectStorage.__new__(S3ObjectStorage)
    storage._bucket = "rendition"
    storage._expires_in = 3600
    storage._client = FakeS3Client()
    storage._presign_client = FakeS3Client()
    return storage


def test_create_multipart_upload_returns_presigned_part_urls():
    storage = make_storage()

    session = storage.create_multipart_upload(
        key="source/video/input.mp4",
        content_type="video/mp4",
        part_count=2,
    )

    assert session.bucket == "rendition"
    assert session.key == "source/video/input.mp4"
    assert session.upload_id == "upload-123"
    assert [part.part_number for part in session.parts] == [1, 2]
    assert storage._client.calls[0] == (
        "create_multipart_upload",
        {
            "Bucket": "rendition",
            "Key": "source/video/input.mp4",
            "ContentType": "video/mp4",
        },
    )


def test_refresh_multipart_upload_wraps_presign_failures():
    storage = make_storage()
    storage._presign_client.fail_presign = True

    with pytest.raises(ObjectStorageError, match="failed to create upload URLs"):
        storage.refresh_multipart_upload_urls(
            key="source/video/input.mp4",
            upload_id="upload-123",
            part_count=1,
        )


def test_complete_multipart_upload_sorts_parts():
    storage = make_storage()

    storage.complete_multipart_upload(
        key="source/video/input.mp4",
        upload_id="upload-123",
        parts=[
            CompletedUploadPart(part_number=2, etag="etag-2"),
            CompletedUploadPart(part_number=1, etag="etag-1"),
        ],
    )

    assert storage._client.calls == [
        (
            "complete_multipart_upload",
            {
                "Bucket": "rendition",
                "Key": "source/video/input.mp4",
                "UploadId": "upload-123",
                "MultipartUpload": {
                    "Parts": [
                        {"PartNumber": 1, "ETag": "etag-1"},
                        {"PartNumber": 2, "ETag": "etag-2"},
                    ]
                },
            },
        )
    ]


def test_abort_multipart_upload_calls_s3():
    storage = make_storage()

    storage.abort_multipart_upload("source/video/input.mp4", "upload-123")

    assert storage._client.calls == [
        (
            "abort_multipart_upload",
            {
                "Bucket": "rendition",
                "Key": "source/video/input.mp4",
                "UploadId": "upload-123",
            },
        )
    ]


def test_upload_and_download_object_helpers_call_s3():
    storage = make_storage()

    storage.upload_file(
        "/tmp/input.mp4",
        "source/video/input.mp4",
        "video/mp4",
        cache_control="private, max-age=0",
    )
    storage.upload_bytes(
        "hls/video/master.m3u8",
        b"#EXTM3U",
        "application/vnd.apple.mpegurl",
        cache_control="public, max-age=30",
    )
    storage.download_file("source/video/input.mp4", "/tmp/input.mp4")

    assert storage._client.calls == [
        (
            "upload_file",
            {
                "Filename": "/tmp/input.mp4",
                "Bucket": "rendition",
                "Key": "source/video/input.mp4",
                "ExtraArgs": {
                    "ContentType": "video/mp4",
                    "CacheControl": "private, max-age=0",
                },
            },
        ),
        (
            "put_object",
            {
                "Bucket": "rendition",
                "Key": "hls/video/master.m3u8",
                "Body": b"#EXTM3U",
                "ContentType": "application/vnd.apple.mpegurl",
                "CacheControl": "public, max-age=30",
            },
        ),
        (
            "download_file",
            {
                "Bucket": "rendition",
                "Key": "source/video/input.mp4",
                "Filename": "/tmp/input.mp4",
            },
        ),
    ]


def test_delete_object_calls_s3():
    storage = make_storage()

    storage.delete_object("source/video/input.mp4")

    assert storage._client.calls == [
        (
            "delete_object",
            {
                "Bucket": "rendition",
                "Key": "source/video/input.mp4",
            },
        )
    ]


def test_playback_url_uses_presigned_download_url():
    storage = make_storage()

    url = storage.generate_playback_url("hls/video/master.m3u8")

    assert url == "http://storage.test/get_object/hls/video/master.m3u8"
    assert storage._presign_client.calls == [
        (
            "generate_presigned_url",
            {
                "operation_name": "get_object",
                "Params": {"Bucket": "rendition", "Key": "hls/video/master.m3u8"},
                "ExpiresIn": 3600,
            },
        )
    ]


def test_get_object_metadata_returns_head_object_metadata():
    storage = make_storage()

    metadata = storage.get_object_metadata("source/video/input.mp4")

    assert metadata is not None
    assert metadata.content_length == 12345
    assert metadata.content_type == "video/mp4"
