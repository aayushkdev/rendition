from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.video import VideoCreateRequest, VideoCreateResponse
from app.services.video_service import create_video_service

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
def create_video(
    payload: VideoCreateRequest,
    db: Session = Depends(get_db),
):
    video = create_video_service(db, payload.source)
    return VideoCreateResponse(video_id=str(video.id))
