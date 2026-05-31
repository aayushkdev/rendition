from dataclasses import dataclass

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

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


class S3ObjectStorage:
    def __init__(
        self,
        endpoint_url: str,
        public_endpoint_url: str | None,
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
            public_endpoint_url or endpoint_url,
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
        response = self._client.create_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            ContentType=content_type,
        )
        upload_id = response["UploadId"]

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

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            return False
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise
        return True


def get_object_storage() -> S3ObjectStorage:
    return S3ObjectStorage(
        endpoint_url=settings.STORAGE_ENDPOINT,
        public_endpoint_url=settings.STORAGE_PUBLIC_ENDPOINT,
        access_key_id=settings.STORAGE_ACCESS_KEY_ID,
        secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
        region_name=settings.STORAGE_REGION,
        bucket=settings.STORAGE_BUCKET,
        presigned_url_expires_seconds=settings.STORAGE_PRESIGNED_URL_EXPIRES_SECONDS,
    )
