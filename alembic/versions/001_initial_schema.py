"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("login_url", sa.Text(), nullable=True),
        sa.Column("credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("html_snapshot", sa.Text(), nullable=True),
        sa.Column("elements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["from_node_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["to_node_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "drift_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("visual_diff_score", sa.Float(), nullable=True),
        sa.Column("semantic_diff", sa.Text(), nullable=True),
        sa.Column("healed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("healed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("drift_logs")
    op.drop_table("edges")
    op.drop_table("nodes")
    op.drop_table("products")
