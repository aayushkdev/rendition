from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.models.enums import ProcessingStatus
from sqlalchemy.sql import func

if TYPE_CHECKING:
    from core.models.rendition import Rendition
    from core.models.outbox import OutboxMessage


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("rendition_id", name="uq_jobs_rendition_id"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_status_started_at", "status", "started_at"),
        Index("ix_jobs_video_id", "video_id"),
        Index("ix_jobs_rendition_id", "rendition_id"),
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

    rendition_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("renditions.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.pending,
    )

    error: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

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

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rendition: Mapped[Rendition] = relationship("Rendition", back_populates="jobs")
    outbox_message: Mapped[OutboxMessage | None] = relationship(
        "OutboxMessage",
        back_populates="job",
        cascade="all, delete-orphan",
    )
