import uuid
from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db.base import Base
from core.models.enums import ProcessingStatus


class Video(Base):
    __tablename__ = "videos"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source = Column(String, nullable=False)
    source_bucket = Column(String, nullable=True)
    source_filename = Column(String, nullable=True)
    source_content_type = Column(String, nullable=True)
    source_size_bytes = Column(Integer, nullable=True)
    multipart_upload_id = Column(String, nullable=True)

    status = Column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.pending,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    uploaded_at = Column(DateTime(timezone=True), nullable=True)

    renditions = relationship(
        "Rendition",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="Rendition.bitrate.desc()",
    )
