"""horario tramo history indexes

Revision ID: 20260520_0002
Revises: 20260513_0001
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa

revision = "20260520_0002"
down_revision = "20260513_0001"
branch_labels = None
depends_on = None


def _indexes(table_name: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if index_name not in _indexes(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    _create_index_if_missing("ix_horario_tramo_timestamp", "horario_tramo", ["timestamp"])
    _create_index_if_missing(
        "ix_horario_tramo_tramo_timestamp",
        "horario_tramo",
        ["tramo_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_horario_tramo_tramo_timestamp", table_name="horario_tramo")
    op.drop_index("ix_horario_tramo_timestamp", table_name="horario_tramo")
