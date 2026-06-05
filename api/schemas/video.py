from datetime import datetime
from typing import Literal
from uuid import UUID
import re

from pydantic import BaseModel, Field, field_validator
from typing import List

from core.config import settings
from core.models.enums import ProcessingStatus

PART_ETAG_PATTERN = re.compile(r'^(?:"[A-Fa-f0-9]{32}"|[A-Fa-f0-9]{32})$')


class UploadConfigResponse(BaseModel):
    max_size_bytes: int
    max_part_count: int
    part_size_bytes: int
    allowed_content_types: List[str]


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
    video_id: UUID
    bucket: str
    key: str
    upload_id: str
    parts: List[MultipartUploadPart]


class CompletedUploadPart(BaseModel):
    part_number: int = Field(ge=1)
    etag: str = Field(min_length=1, max_length=1024)

    @field_validator("etag")
    @classmethod
    def validate_etag(cls, value: str) -> str:
        if not PART_ETAG_PATTERN.fullmatch(value):
            raise ValueError("etag must be a 32-character hex value")
        return value


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
    status: ProcessingStatus


class VideoState(BaseModel):
    video_id: UUID
    status: ProcessingStatus
    renditions: List[RenditionState]


class VideoListItem(BaseModel):
    video_id: UUID
    title: str
    uploaded_at: datetime | None
    created_at: datetime
    status: ProcessingStatus
    size_bytes: int | None


class PlaybackRenditionState(BaseModel):
    resolution: str
    status: ProcessingStatus


class StreamingInfo(BaseModel):
    type: Literal["hls"]
    master_playlist_url: str
    expires_at: datetime | None = None


class VideoPlaybackResponse(BaseModel):
    video_id: UUID
    status: ProcessingStatus
    playable: bool
    streaming: StreamingInfo
    renditions: List[PlaybackRenditionState]
