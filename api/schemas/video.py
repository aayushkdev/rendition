from pydantic import BaseModel, Field, field_validator
from typing import List


class VideoCreateRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255, pattern=r"^video/")
    size_bytes: int = Field(gt=0)
    part_count: int = Field(ge=1, le=10_000)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("filename must not contain path separators")
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
    part_number: int = Field(ge=1, le=10_000)
    etag: str = Field(min_length=1)


class VideoUploadCompleteRequest(BaseModel):
    parts: List[CompletedUploadPart] = Field(min_length=1)


class VideoUploadRefreshRequest(BaseModel):
    part_count: int = Field(ge=1, le=10_000)


class RenditionState(BaseModel):
    resolution: str
    status: str


class VideoState(BaseModel):
    video_id: str
    status: str
    renditions: List[RenditionState]
