from __future__ import annotations

from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.models.enums import ProcessingStatus

if TYPE_CHECKING:
    from core.models.rendition import Rendition


class Job(Base):
    __tablename__ = "jobs"

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

    rendition: Mapped[Rendition] = relationship("Rendition", back_populates="jobs")
