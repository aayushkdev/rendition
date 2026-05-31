from __future__ import annotations

from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Integer, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.models.enums import ProcessingStatus

if TYPE_CHECKING:
    from core.models.job import Job
    from core.models.video import Video


class Rendition(Base):
    __tablename__ = "renditions"

    id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )

    resolution: Mapped[str] = mapped_column(String, nullable=False)
    bitrate: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.pending,
    )

    output_path: Mapped[str | None] = mapped_column(String, nullable=True)

    video: Mapped[Video] = relationship("Video", back_populates="renditions")

    jobs: Mapped[list[Job]] = relationship(
        "Job",
        back_populates="rendition",
        cascade="all, delete-orphan",
    )
