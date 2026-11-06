"""create pedidos table

Revision ID: 0001_create_pedidos
Revises:
Create Date: 2026-11-06 16:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_create_pedidos"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pedidos",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("producto_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("producto_nombre", sa.String(length=150), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_pedidos_created_at_id",
        "pedidos",
        ["created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_pedidos_producto_id",
        "pedidos",
        ["producto_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pedidos_producto_id", table_name="pedidos")
    op.drop_index("ix_pedidos_created_at_id", table_name="pedidos")
    op.drop_table("pedidos")
