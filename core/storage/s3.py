from dataclasses import dataclass
from typing import Protocol

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from core.config import settings


@dataclass(frozen=True)
class MultipartUploadPart:
    part_number: int
    upload_url: str


@dataclass(frozen=True)
class MultipartUploadSession:
    bucket: str
    key: str
    upload_id: str
    parts: list[MultipartUploadPart]


@dataclass(frozen=True)
class CompletedUploadPart:
    part_number: int
    etag: str


@dataclass(frozen=True)
class ObjectMetadata:
    content_length: int
    content_type: str | None


class ObjectStorageError(RuntimeError):
    pass


class ObjectStorage(Protocol):
    @property
    def bucket(self) -> str: ...

    def create_multipart_upload(
        self,
        key: str,
        content_type: str,
        part_count: int,
    ) -> MultipartUploadSession: ...

    def refresh_multipart_upload_urls(
        self,
        key: str,
        upload_id: str,
        part_count: int,
    ) -> MultipartUploadSession: ...

    def complete_multipart_upload(
        self,
        key: str,
        upload_id: str,
        parts: list[CompletedUploadPart],
    ) -> None: ...

    def abort_multipart_upload(self, key: str, upload_id: str) -> None: ...

    def object_exists(self, key: str) -> bool: ...

    def get_object_metadata(self, key: str) -> ObjectMetadata | None: ...

    def upload_file(
        self,
        local_path: str,
        key: str,
        content_type: str,
        cache_control: str | None = None,
    ) -> None: ...

    def upload_bytes(
        self,
        key: str,
        body: bytes,
        content_type: str,
        cache_control: str | None = None,
    ) -> None: ...

    def download_file(self, key: str, local_path: str) -> None: ...

    def delete_object(self, key: str) -> None: ...

    def generate_presigned_download_url(self, key: str) -> str: ...

    def generate_playback_url(self, key: str) -> str: ...


class S3ObjectStorage:
    def __init__(
        self,
        endpoint_url: str,
        presign_endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        region_name: str,
        bucket: str,
        presigned_url_expires_seconds: int,
    ) -> None:
        self._bucket = bucket
        self._expires_in = presigned_url_expires_seconds
        self._client = self._build_client(
            endpoint_url,
            access_key_id,
            secret_access_key,
            region_name,
        )
        self._presign_client = self._build_client(
            presign_endpoint_url or endpoint_url,
            access_key_id,
            secret_access_key,
            region_name,
        )

    @staticmethod
    def _build_client(
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str,
    ):
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=Config(signature_version="s3v4"),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def create_multipart_upload(
        self,
        key: str,
        content_type: str,
        part_count: int,
    ) -> MultipartUploadSession:
        try:
            response = self._client.create_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to create multipart upload") from exc

        upload_id = response["UploadId"]

        return self.refresh_multipart_upload_urls(
            key=key,
            upload_id=upload_id,
            part_count=part_count,
        )

    def refresh_multipart_upload_urls(
        self,
        key: str,
        upload_id: str,
        part_count: int,
    ) -> MultipartUploadSession:
        try:
            parts = [
                MultipartUploadPart(
                    part_number=part_number,
                    upload_url=self._presign_client.generate_presigned_url(
                        "upload_part",
                        Params={
                            "Bucket": self._bucket,
                            "Key": key,
                            "UploadId": upload_id,
                            "PartNumber": part_number,
                        },
                        ExpiresIn=self._expires_in,
                    ),
                )
                for part_number in range(1, part_count + 1)
            ]
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to create upload URLs") from exc

        return MultipartUploadSession(
            bucket=self._bucket,
            key=key,
            upload_id=upload_id,
            parts=parts,
        )

    def complete_multipart_upload(
        self,
        key: str,
        upload_id: str,
        parts: list[CompletedUploadPart],
    ) -> None:
        try:
            self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": part.part_number, "ETag": part.etag}
                        for part in sorted(parts, key=lambda part: part.part_number)
                    ]
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to complete multipart upload") from exc

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        try:
            self._client.abort_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to abort multipart upload") from exc

    def object_exists(self, key: str) -> bool:
        return self.get_object_metadata(key) is not None

    def get_object_metadata(self, key: str) -> ObjectMetadata | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            return None
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return None
            raise ObjectStorageError("failed to check object existence") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError("failed to check object existence") from exc
        return ObjectMetadata(
            content_length=response["ContentLength"],
            content_type=response.get("ContentType"),
        )

    def upload_file(
        self,
        local_path: str,
        key: str,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        extra_args = {"ContentType": content_type}
        if cache_control is not None:
            extra_args["CacheControl"] = cache_control

        try:
            self._client.upload_file(
                Filename=local_path,
                Bucket=self._bucket,
                Key=key,
                ExtraArgs=extra_args,
            )
        except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
            raise ObjectStorageError("failed to upload object") from exc

    def upload_bytes(
        self,
        key: str,
        body: bytes,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        put_args = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
        }
        if cache_control is not None:
            put_args["CacheControl"] = cache_control

        try:
            self._client.put_object(**put_args)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to upload object") from exc

    def download_file(self, key: str, local_path: str) -> None:
        try:
            self._client.download_file(
                Bucket=self._bucket,
                Key=key,
                Filename=local_path,
            )
        except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
            raise ObjectStorageError("failed to download object") from exc

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to delete object") from exc

    def generate_presigned_download_url(self, key: str) -> str:
        try:
            return self._presign_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=self._expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("failed to create download URL") from exc

    def generate_playback_url(self, key: str) -> str:
        return self.generate_presigned_download_url(key)


def get_object_storage() -> S3ObjectStorage:
    return S3ObjectStorage(
        endpoint_url=settings.STORAGE_ENDPOINT,
        presign_endpoint_url=settings.STORAGE_PRESIGN_ENDPOINT,
        access_key_id=settings.STORAGE_ACCESS_KEY_ID,
        secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
        region_name=settings.STORAGE_REGION,
        bucket=settings.STORAGE_BUCKET,
        presigned_url_expires_seconds=settings.STORAGE_PRESIGNED_URL_EXPIRES_SECONDS,
    )
