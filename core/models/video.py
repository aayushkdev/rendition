from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import BigInteger, DateTime, Enum, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from core.db.base import Base
from core.models.enums import ProcessingStatus

if TYPE_CHECKING:
    from core.models.rendition import Rendition
    from core.models.upload_session import UploadSession


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (Index("ix_videos_status", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source: Mapped[str] = mapped_column(String, nullable=False)
    source_bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    source_content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    source_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    playback_path: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.pending,
    )

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

    uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    renditions: Mapped[list[Rendition]] = relationship(
        "Rendition",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="Rendition.bitrate.desc()",
    )

    upload_sessions: Mapped[list[UploadSession]] = relationship(
        "UploadSession",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="UploadSession.created_at.desc()",
    )
