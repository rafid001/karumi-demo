import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    elements: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["Product"] = relationship("Product", back_populates="nodes")
    outgoing_edges: Mapped[list["Edge"]] = relationship(
        "Edge", foreign_keys="Edge.from_node_id", back_populates="from_node", cascade="all, delete-orphan"
    )
    incoming_edges: Mapped[list["Edge"]] = relationship(
        "Edge", foreign_keys="Edge.to_node_id", back_populates="to_node"
    )
    drift_logs: Mapped[list["DriftLog"]] = relationship("DriftLog", back_populates="node", cascade="all, delete-orphan")
