from pydantic import BaseModel
from typing import List


class VideoCreateRequest(BaseModel):
    source: str


class VideoCreateResponse(BaseModel):
    video_id: str


class RenditionState(BaseModel):
    resolution: str
    status: str


class VideoState(BaseModel):
    video_id: str
    status: str
    renditions: List[RenditionState]
