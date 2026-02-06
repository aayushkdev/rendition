from uuid import UUID
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.video import VideoCreateRequest, VideoCreateResponse, VideoState
from app.services.video_service import ingest_video, get_video_state

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "", response_model=VideoCreateResponse, status_code=status.HTTP_201_CREATED
)
def create_video(payload: VideoCreateRequest, db: Session = Depends(get_db)):
    video = ingest_video(db, payload.source)
    return VideoCreateResponse(video_id=str(video.id))


@router.get("/{video_id}", response_model=VideoState)
def get_video(video_id: UUID, db: Session = Depends(get_db)):
    state = get_video_state(db, video_id)

    if state is None:
        raise HTTPException(status_code=404, detail="Video not found")

    return state
