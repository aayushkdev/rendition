from uuid import UUID

from pydantic import BaseModel


class EncodingJobMessage(BaseModel):
    job_id: UUID
    video_id: UUID
    rendition_id: UUID
