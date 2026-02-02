import uuid
from sqlalchemy import Column, Integer, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import ProcessingStatus


class Rendition(Base):
    __tablename__ = "renditions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    video_id = Column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )

    resolution = Column(String, nullable=False)
    bitrate = Column(Integer, nullable=False)

    status = Column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.pending,
    )

    output_path = Column(String, nullable=True)

    video = relationship("Video", back_populates="renditions")

    jobs = relationship(
        "Job",
        back_populates="rendition",
        cascade="all, delete-orphan",
    )
