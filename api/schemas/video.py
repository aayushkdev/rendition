from pydantic import BaseModel, Field, field_validator
from typing import List

from core.config import settings


class VideoCreateRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    part_count: int = Field(ge=1)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("filename must not contain path separators")
        return value

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        if value not in settings.upload_allowed_content_types:
            raise ValueError("unsupported video content type")
        return value

    @field_validator("size_bytes")
    @classmethod
    def validate_size_bytes(cls, value: int) -> int:
        if value > settings.UPLOAD_MAX_SIZE_BYTES:
            raise ValueError("file exceeds maximum upload size")
        return value

    @field_validator("part_count")
    @classmethod
    def validate_part_count(cls, value: int) -> int:
        if value > settings.UPLOAD_MAX_PART_COUNT:
            raise ValueError("file exceeds maximum upload part count")
        return value


class MultipartUploadPart(BaseModel):
    part_number: int
    upload_url: str


class VideoCreateResponse(BaseModel):
    video_id: str
    bucket: str
    key: str
    upload_id: str
    parts: List[MultipartUploadPart]


class CompletedUploadPart(BaseModel):
    part_number: int = Field(ge=1)
    etag: str = Field(min_length=1)


class VideoUploadCompleteRequest(BaseModel):
    parts: List[CompletedUploadPart] = Field(min_length=1)


class VideoUploadRefreshRequest(BaseModel):
    part_count: int = Field(ge=1)

    @field_validator("part_count")
    @classmethod
    def validate_part_count(cls, value: int) -> int:
        if value > settings.UPLOAD_MAX_PART_COUNT:
            raise ValueError("file exceeds maximum upload part count")
        return value


class RenditionState(BaseModel):
    resolution: str
    status: str


class VideoState(BaseModel):
    video_id: str
    status: str
    renditions: List[RenditionState]
