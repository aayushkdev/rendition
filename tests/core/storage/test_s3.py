from botocore.exceptions import BotoCoreError, ClientError

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
        self.fail_operations = set()
        self.raise_no_such_key = False
        self.raise_404 = False
        self.head_response = {
            "ContentLength": 12345,
            "ContentType": "video/mp4",
        }

    def create_multipart_upload(self, **kwargs):
        if "create_multipart_upload" in self.fail_operations:
            raise BotoCoreError()
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
        if "complete_multipart_upload" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("complete_multipart_upload", kwargs))

    def abort_multipart_upload(self, **kwargs):
        if "abort_multipart_upload" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("abort_multipart_upload", kwargs))

    def upload_file(self, **kwargs):
        if "upload_file" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("upload_file", kwargs))

    def put_object(self, **kwargs):
        if "put_object" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("put_object", kwargs))

    def download_file(self, **kwargs):
        if "download_file" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("download_file", kwargs))

    def delete_object(self, **kwargs):
        if "delete_object" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("delete_object", kwargs))

    def head_object(self, **kwargs):
        if "head_object" in self.fail_operations:
            raise BotoCoreError()
        if self.raise_no_such_key:
            raise self.exceptions.NoSuchKey()
        if self.raise_404:
            raise ClientError(
                {
                    "Error": {"Code": "404", "Message": "Not Found"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "HeadObject",
            )
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
            CompletedUploadPart(
                part_number=2,
                etag="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ),
            CompletedUploadPart(
                part_number=1,
                etag="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ),
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
                        {
                            "PartNumber": 1,
                            "ETag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        },
                        {
                            "PartNumber": 2,
                            "ETag": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        },
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


def test_create_multipart_upload_wraps_boto_failures():
    storage = make_storage()
    storage._client.fail_operations.add("create_multipart_upload")

    with pytest.raises(ObjectStorageError, match="failed to create multipart upload"):
        storage.create_multipart_upload(
            key="source/video/input.mp4",
            content_type="video/mp4",
            part_count=1,
        )


def test_complete_multipart_upload_wraps_boto_failures():
    storage = make_storage()
    storage._client.fail_operations.add("complete_multipart_upload")

    with pytest.raises(ObjectStorageError, match="failed to complete multipart upload"):
        storage.complete_multipart_upload(
            key="source/video/input.mp4",
            upload_id="upload-123",
            parts=[
                CompletedUploadPart(
                    part_number=1,
                    etag="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                )
            ],
        )


def test_abort_multipart_upload_wraps_boto_failures():
    storage = make_storage()
    storage._client.fail_operations.add("abort_multipart_upload")

    with pytest.raises(ObjectStorageError, match="failed to abort multipart upload"):
        storage.abort_multipart_upload("source/video/input.mp4", "upload-123")


@pytest.mark.parametrize(
    ("operation", "call", "message"),
    [
        (
            "upload_file",
            lambda storage: storage.upload_file(
                "/tmp/input.mp4",
                "source/video/input.mp4",
                "video/mp4",
            ),
            "failed to upload object",
        ),
        (
            "put_object",
            lambda storage: storage.upload_bytes(
                "hls/video/master.m3u8",
                b"#EXTM3U",
                "application/vnd.apple.mpegurl",
            ),
            "failed to upload object",
        ),
        (
            "download_file",
            lambda storage: storage.download_file(
                "source/video/input.mp4",
                "/tmp/input.mp4",
            ),
            "failed to download object",
        ),
        (
            "delete_object",
            lambda storage: storage.delete_object("source/video/input.mp4"),
            "failed to delete object",
        ),
    ],
)
def test_object_transfer_helpers_wrap_boto_failures(operation, call, message):
    storage = make_storage()
    storage._client.fail_operations.add(operation)

    with pytest.raises(ObjectStorageError, match=message):
        call(storage)


def test_generate_presigned_download_url_wraps_boto_failures():
    storage = make_storage()
    storage._presign_client.fail_presign = True

    with pytest.raises(ObjectStorageError, match="failed to create download URL"):
        storage.generate_presigned_download_url("hls/video/master.m3u8")


def test_get_object_metadata_returns_none_for_missing_objects():
    storage = make_storage()
    storage._client.raise_no_such_key = True

    assert storage.get_object_metadata("missing.mp4") is None


def test_get_object_metadata_returns_none_for_404_client_error():
    storage = make_storage()
    storage._client.raise_404 = True

    assert storage.get_object_metadata("missing.mp4") is None


def test_get_object_metadata_wraps_boto_failures():
    storage = make_storage()
    storage._client.fail_operations.add("head_object")

    with pytest.raises(ObjectStorageError, match="failed to check object existence"):
        storage.get_object_metadata("source/video/input.mp4")
