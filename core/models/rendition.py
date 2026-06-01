from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import (
    DateTime,
    Integer,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.models.enums import ProcessingStatus
from sqlalchemy.sql import func

if TYPE_CHECKING:
    from core.models.job import Job
    from core.models.video import Video


class Rendition(Base):
    __tablename__ = "renditions"
    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "resolution",
            name="uq_renditions_video_id_resolution",
        ),
        Index("ix_renditions_video_id", "video_id"),
        Index("ix_renditions_status", "status"),
    )

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
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    video: Mapped[Video] = relationship("Video", back_populates="renditions")

    jobs: Mapped[list[Job]] = relationship(
        "Job",
        back_populates="rendition",
        cascade="all, delete-orphan",
    )
