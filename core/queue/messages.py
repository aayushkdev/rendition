from uuid import UUID

from pydantic import BaseModel

ENCODING_EXCHANGE = "rendition"
ENCODING_ROUTING_KEY = "job.encode"
ENCODING_DEAD_LETTER_EXCHANGE = "rendition.dlx"
ENCODING_DEAD_LETTER_ROUTING_KEY = "job.encode.dead"


class EncodingJobMessage(BaseModel):
    job_id: UUID
    video_id: UUID
    rendition_id: UUID
