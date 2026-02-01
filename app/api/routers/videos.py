from fastapi import APIRouter, status
from uuid import uuid4

from app.schemas.video import (
    VideoCreateRequest,
    VideoCreateResponse,
)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "",
    response_model=VideoCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_video(payload: VideoCreateRequest):
    print(payload)
    return VideoCreateResponse(video_id=str(uuid4()))
