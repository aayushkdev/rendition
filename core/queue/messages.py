from uuid import UUID

from pydantic import BaseModel

ENCODING_EXCHANGE = "rendition"
ENCODING_ROUTING_KEY = "job.encode"


class EncodingJobMessage(BaseModel):
    job_id: UUID
    video_id: UUID
    rendition_id: UUID
