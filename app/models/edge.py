import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    to_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    from_node: Mapped["Node"] = relationship("Node", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node: Mapped["Node"] = relationship("Node", foreign_keys=[to_node_id], back_populates="incoming_edges")
