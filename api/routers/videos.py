from uuid import UUID
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from core.db.session import get_db
from api.schemas.video import (
    VideoCreateRequest,
    VideoCreateResponse,
    VideoState,
    VideoUploadCompleteRequest,
    VideoUploadRefreshRequest,
)
from core.services.video_service import (
    VideoUploadConflictError,
    VideoUploadStorageError,
    abort_video_upload,
    complete_video_upload,
    create_video_upload,
    get_video_state,
    refresh_video_upload,
)
from core.storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "", response_model=VideoCreateResponse, status_code=status.HTTP_201_CREATED
)
def create_video(
    payload: VideoCreateRequest,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
):
    try:
        return create_video_upload(
            db=db,
            storage=storage,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            part_count=payload.part_count,
        )
    except VideoUploadStorageError as exc:
        raise HTTPException(status_code=502, detail="Storage unavailable") from exc


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
    storage: ObjectStorage = Depends(get_object_storage),
):
    try:
        state = complete_video_upload(db, storage, video_id, payload.parts)
    except VideoUploadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoUploadStorageError as exc:
        raise HTTPException(status_code=502, detail="Storage unavailable") from exc

    if state is None:
        raise HTTPException(status_code=404, detail="Video not found")

    return state


@router.post("/{video_id}/upload/refresh", response_model=VideoCreateResponse)
def refresh_upload(
    video_id: UUID,
    payload: VideoUploadRefreshRequest,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
):
    try:
        upload = refresh_video_upload(db, storage, video_id, payload.part_count)
    except VideoUploadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoUploadStorageError as exc:
        raise HTTPException(status_code=502, detail="Storage unavailable") from exc

    if upload is None:
        raise HTTPException(status_code=404, detail="Video not found")

    return upload


@router.delete("/{video_id}/upload", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(
    video_id: UUID,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
):
    try:
        aborted = abort_video_upload(db, storage, video_id)
    except VideoUploadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoUploadStorageError as exc:
        raise HTTPException(status_code=502, detail="Storage unavailable") from exc

    if aborted is None:
        raise HTTPException(status_code=404, detail="Video not found")
