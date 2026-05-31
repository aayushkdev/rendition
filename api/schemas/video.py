from pydantic import BaseModel
from typing import List


class VideoCreateRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    part_count: int


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
    part_number: int
    etag: str


class VideoUploadCompleteRequest(BaseModel):
    parts: List[CompletedUploadPart]


class RenditionState(BaseModel):
    resolution: str
    status: str


class VideoState(BaseModel):
    video_id: str
    status: str
    renditions: List[RenditionState]
