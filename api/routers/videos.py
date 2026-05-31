from uuid import UUID
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from core.db.session import get_db
from api.schemas.video import (
    VideoCreateRequest,
    VideoCreateResponse,
    VideoState,
    VideoUploadCompleteRequest,
)
from core.services.video_service import (
    complete_video_upload,
    create_video_upload,
    get_video_state,
)
from core.storage import S3ObjectStorage, get_object_storage

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "", response_model=VideoCreateResponse, status_code=status.HTTP_201_CREATED
)
def create_video(
    payload: VideoCreateRequest,
    db: Session = Depends(get_db),
    storage: S3ObjectStorage = Depends(get_object_storage),
):
    return create_video_upload(
        db=db,
        storage=storage,
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        part_count=payload.part_count,
    )


@router.get("/{video_id}", response_model=VideoState)
def get_video(video_id: UUID, db: Session = Depends(get_db)):
    state = get_video_state(db, video_id)

    if state is None:
        raise HTTPException(status_code=404, detail="Video not found")

    return state


@router.post("/{video_id}/upload/complete", response_model=VideoState)
def complete_upload(
    video_id: UUID,
    payload: VideoUploadCompleteRequest,
    db: Session = Depends(get_db),
    storage: S3ObjectStorage = Depends(get_object_storage),
):
    state = complete_video_upload(db, storage, video_id, payload.parts)

    if state is None:
        raise HTTPException(status_code=404, detail="Video not found")

    return state
