import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DriftLog(Base):
    __tablename__ = "drift_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    visual_diff_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    healed: Mapped[bool] = mapped_column(Boolean, default=False)
    healed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    node: Mapped["Node"] = relationship("Node", back_populates="drift_logs")
