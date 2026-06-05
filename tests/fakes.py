from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from core.encoding.ffmpeg import HlsEncoder
from core.encoding.probe import VideoProber
from core.encoding import VideoSourceMetadata
from core.storage import ObjectStorageError
from core.storage.s3 import (
    CompletedUploadPart,
    MultipartUploadPart,
    MultipartUploadSession,
    ObjectMetadata,
)
from pika.adapters.blocking_connection import BlockingChannel
from worker.processor import EncodingProcessorResult


class FakeObjectStorage:
    bucket = "test-bucket"
    fail_create = False

    def __init__(self) -> None:
        self.completed_uploads = []
        self.aborted_uploads = []
        self.deleted_objects = []
        self.metadata_by_key = {}
        self.completed_content_length = 12_345
        self.completed_content_type = "video/mp4"
        self.fail_complete = False
        self.fail_delete = False
        self.fail_abort = False
        self.fail_upload_file = False
        self.fail_upload_bytes = False
        self.fail_download_file = False
        self.downloads = []
        self.uploaded_files = []
        self.uploaded_bytes = []
        self.download_body = b"input"

    def create_multipart_upload(
        self,
        key: str,
        content_type: str,
        part_count: int,
    ) -> MultipartUploadSession:
        if self.fail_create:
            raise ObjectStorageError("storage unavailable")

        return MultipartUploadSession(
            bucket=self.bucket,
            key=key,
            upload_id="test-upload-id",
            parts=[
                MultipartUploadPart(
                    part_number=part_number,
                    upload_url=f"http://storage.test/{key}?partNumber={part_number}",
                )
                for part_number in range(1, part_count + 1)
            ],
        )

    def refresh_multipart_upload_urls(
        self,
        key: str,
        upload_id: str,
        part_count: int,
    ) -> MultipartUploadSession:
        return MultipartUploadSession(
            bucket=self.bucket,
            key=key,
            upload_id=upload_id,
            parts=[
                MultipartUploadPart(
                    part_number=part_number,
                    upload_url=f"http://storage.test/{key}?refreshPartNumber={part_number}",
                )
                for part_number in range(1, part_count + 1)
            ],
        )

    def complete_multipart_upload(
        self,
        key: str,
        upload_id: str,
        parts: list[CompletedUploadPart],
    ) -> None:
        if self.fail_complete:
            raise ObjectStorageError("complete failed")

        self.completed_uploads.append(
            {"key": key, "upload_id": upload_id, "parts": parts}
        )
        self.metadata_by_key[key] = ObjectMetadata(
            content_length=self.completed_content_length,
            content_type=self.completed_content_type,
        )

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        if self.fail_abort:
            raise ObjectStorageError("abort failed")

        self.aborted_uploads.append({"key": key, "upload_id": upload_id})

    def object_exists(self, key: str) -> bool:
        return key in self.metadata_by_key

    def get_object_metadata(self, key: str) -> ObjectMetadata | None:
        return self.metadata_by_key.get(key)

    def upload_file(
        self,
        local_path: str,
        key: str,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        if self.fail_upload_file:
            raise ObjectStorageError("upload failed")

        body = Path(local_path).read_bytes()
        self.uploaded_files.append(
            {
                "local_path": local_path,
                "key": key,
                "content_type": content_type,
                "cache_control": cache_control,
                "body": body,
            }
        )
        self.metadata_by_key[key] = ObjectMetadata(
            content_length=len(body),
            content_type=content_type,
        )

    def upload_bytes(
        self,
        key: str,
        body: bytes,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        if self.fail_upload_bytes:
            raise ObjectStorageError("storage upload failed")

        self.uploaded_bytes.append(
            {
                "key": key,
                "body": body,
                "content_type": content_type,
                "cache_control": cache_control,
            }
        )
        self.metadata_by_key[key] = ObjectMetadata(
            content_length=len(body),
            content_type=content_type,
        )

    def download_file(self, key: str, local_path: str) -> None:
        if self.fail_download_file:
            raise ObjectStorageError("download failed")

        self.downloads.append({"key": key, "local_path": local_path})
        Path(local_path).write_bytes(self.download_body)

    def download_bytes(self, key: str) -> bytes:
        if self.fail_download_file:
            raise ObjectStorageError("download failed")

        self.downloads.append({"key": key})
        if key in self.metadata_by_key:
            for upload in [*self.uploaded_bytes, *self.uploaded_files]:
                if upload["key"] == key:
                    return upload.get("body", self.download_body)
        return self.download_body

    def delete_object(self, key: str) -> None:
        if self.fail_delete:
            raise ObjectStorageError("delete failed")

        self.deleted_objects.append(key)
        self.metadata_by_key.pop(key, None)

    def generate_presigned_download_url(self, key: str) -> str:
        return f"http://storage.test/download/{key}"

    def generate_playback_url(self, key: str) -> str:
        return f"http://playback.test/{key}"


class FakeJobQueuePublisher:
    def __init__(
        self,
        *,
        fail_publish: bool = False,
        fail_session: bool = False,
    ) -> None:
        self.fail_publish = fail_publish
        self.fail_session = fail_session
        self.published_messages = []
        self.session_count = 0

    def session(self):
        self.session_count += 1
        if self.fail_session:
            raise RuntimeError("rabbitmq connection failed")
        return self

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def publish_encoding_job(self, message, exchange: str, routing_key: str) -> None:
        if self.fail_publish:
            raise RuntimeError("rabbitmq unavailable")
        self.published_messages.append(
            {
                "message": message,
                "exchange": exchange,
                "routing_key": routing_key,
            }
        )


class FakeClosableSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeEncodingProcessor:
    def __init__(
        self,
        *,
        result: EncodingProcessorResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or EncodingProcessorResult(
            output_path="renditions/video/1080p/master.m3u8",
        )
        self.error = error
        self.contexts = []

    def process(self, context):
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.result


class FakeDeliveryChannel:
    def __init__(self) -> None:
        self.acks = []
        self.nacks = []
        self.rejects = []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append({"delivery_tag": delivery_tag, "requeue": requeue})

    def basic_reject(self, delivery_tag, requeue):
        self.rejects.append({"delivery_tag": delivery_tag, "requeue": requeue})


class FakeDeliveryMethod:
    delivery_tag = "delivery-1"


class FakeBlockingChannel(BlockingChannel):
    def __init__(self):
        self.calls = []

    def exchange_declare(self, *args, **kwargs) -> Any:
        self.calls.append(("exchange_declare", kwargs))

    def queue_declare(self, *args, **kwargs) -> Any:
        self.calls.append(("queue_declare", kwargs))

    def queue_bind(self, *args, **kwargs) -> Any:
        self.calls.append(("queue_bind", kwargs))

    def basic_publish(self, *args, **kwargs) -> Any:
        self.calls.append(("basic_publish", kwargs))


class FakeBlockingConnection:
    def __init__(self, channel):
        self._channel = channel
        self.is_open = True
        self.closed = False

    def channel(self):
        return self._channel

    def close(self):
        self.closed = True
        self.is_open = False


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
        self.object_body = b"object-body"

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

    def get_object(self, **kwargs):
        if "get_object" in self.fail_operations:
            raise BotoCoreError()
        self.calls.append(("get_object", kwargs))
        return {"Body": BytesIO(self.object_body)}

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


class FakeOutboxMessagePublisher(FakeJobQueuePublisher):
    def __init__(
        self,
        *,
        fail: bool = False,
        fail_session: bool = False,
    ) -> None:
        super().__init__(fail_publish=fail, fail_session=fail_session)

    @property
    def messages(self):
        return [
            (
                entry["message"],
                entry["exchange"],
                entry["routing_key"],
            )
            for entry in self.published_messages
        ]
