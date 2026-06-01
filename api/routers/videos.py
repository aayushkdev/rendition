from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from core.db.session import get_db
from api.schemas.video import (
    UploadConfigResponse,
    VideoCreateRequest,
    VideoCreateResponse,
    VideoListItem,
    VideoState,
    VideoUploadCompleteRequest,
    VideoUploadRefreshRequest,
)
from core.config import settings
from core.queue import JobQueuePublisher, get_job_queue_publisher
from core.services.outbox_service import publish_pending_outbox_messages
from core.services.upload_service import (
    abort_video_upload,
    complete_video_upload,
    create_video_upload,
    refresh_video_upload,
)
from core.services.video_service import VideoNotFoundError, get_video_state, list_videos
from core.storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/upload/config", response_model=UploadConfigResponse)
def get_upload_config():
    return UploadConfigResponse(
        max_size_bytes=settings.UPLOAD_MAX_SIZE_BYTES,
        max_part_count=settings.UPLOAD_MAX_PART_COUNT,
        part_size_bytes=settings.UPLOAD_PART_SIZE_BYTES,
        allowed_content_types=sorted(settings.upload_allowed_content_types),
    )


@router.get("", response_model=list[VideoListItem])
def get_videos(db: Session = Depends(get_db)):
    return list_videos(db)


@router.post(
    "", response_model=VideoCreateResponse, status_code=status.HTTP_201_CREATED
)
def create_video(
    payload: VideoCreateRequest,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
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
        raise VideoNotFoundError("Video not found")

    return state


@router.post("/{video_id}/upload/complete", response_model=VideoState)
def complete_upload(
    video_id: UUID,
    payload: VideoUploadCompleteRequest,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
    publisher: JobQueuePublisher = Depends(get_job_queue_publisher),
):
    result = complete_video_upload(db, storage, video_id, payload.parts)

    if result is None:
        raise VideoNotFoundError("Video not found")

    publish_pending_outbox_messages(
        db=db,
        publisher=publisher,
        outbox_message_ids=result.outbox_message_ids,
    )
    return result.state


@router.post("/{video_id}/upload/refresh", response_model=VideoCreateResponse)
def refresh_upload(
    video_id: UUID,
    payload: VideoUploadRefreshRequest,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
):
    upload = refresh_video_upload(db, storage, video_id, payload.part_count)

    if upload is None:
        raise VideoNotFoundError("Video not found")

    return upload


@router.delete("/{video_id}/upload", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(
    video_id: UUID,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
):
    aborted = abort_video_upload(db, storage, video_id)

    if aborted is None:
        raise VideoNotFoundError("Video not found")
