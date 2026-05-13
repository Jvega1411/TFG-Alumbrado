"""fase2 schema

Revision ID: 20260513_0001
Revises:
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260513_0001"
down_revision = None
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if index_name not in _indexes(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _add_columns_if_missing(table_name: str, columns: list[sa.Column]) -> None:
    existing = _columns(table_name)
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _create_ciclo() -> None:
    op.create_table(
        "ciclo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fins_ok", sa.Boolean(), nullable=False),
        sa.Column("fins_error", sa.String(length=512), nullable=True),
        sa.Column("secciones_status", sa.String(length=16), nullable=True),
        sa.Column("secciones_error", sa.String(length=512), nullable=True),
        sa.Column("modo_status", sa.String(length=16), nullable=True),
        sa.Column("modo_error", sa.String(length=512), nullable=True),
        sa.Column("fotocelula_status", sa.String(length=16), nullable=True),
        sa.Column("fotocelula_error", sa.String(length=512), nullable=True),
        sa.Column("reloj_status", sa.String(length=16), nullable=True),
        sa.Column("reloj_error", sa.String(length=512), nullable=True),
        sa.Column("horarios_status", sa.String(length=16), nullable=True),
        sa.Column("horarios_error", sa.String(length=512), nullable=True),
        sa.Column("diagnostico_status", sa.String(length=16), nullable=True),
        sa.Column("diagnostico_error", sa.String(length=512), nullable=True),
        sa.Column("modfunalu", sa.Integer(), nullable=True),
        sa.Column("fotocelula_entrada", sa.Boolean(), nullable=True),
        sa.Column("fotocelula_mem_fun", sa.Boolean(), nullable=True),
        sa.Column("fotocelula_mem_act", sa.Boolean(), nullable=True),
        sa.Column("plc_seg", sa.Integer(), nullable=True),
        sa.Column("plc_min", sa.Integer(), nullable=True),
        sa.Column("plc_hora", sa.Integer(), nullable=True),
        sa.Column("plc_dia", sa.Integer(), nullable=True),
        sa.Column("plc_mes", sa.Integer(), nullable=True),
        sa.Column("plc_anio", sa.Integer(), nullable=True),
        sa.Column("plc_diasem", sa.Integer(), nullable=True),
        sa.Column("cycle_time_error", sa.Boolean(), nullable=True),
        sa.Column("low_battery", sa.Boolean(), nullable=True),
        sa.Column("io_verify_error", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("timestamp", name="uq_ciclo_timestamp"),
    )
    op.create_index("ix_ciclo_timestamp", "ciclo", ["timestamp"])


def _create_seccion_estado() -> None:
    op.create_table(
        "seccion_estado",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ciclo_id", sa.Integer(), sa.ForeignKey("ciclo.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seccion_id", sa.Integer(), nullable=False),
        sa.Column("automatico", sa.Boolean(), nullable=False),
        sa.Column("manual", sa.Boolean(), nullable=False),
        sa.Column("horario_activo", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_seccion_estado_ciclo_id", "seccion_estado", ["ciclo_id"])
    op.create_index("ix_seccion_estado_timestamp", "seccion_estado", ["timestamp"])
    op.create_index(
        "ix_seccion_estado_seccion_timestamp",
        "seccion_estado",
        ["seccion_id", "timestamp"],
    )


def _create_horario_tramo() -> None:
    op.create_table(
        "horario_tramo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ciclo_id", sa.Integer(), sa.ForeignKey("ciclo.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tramo_id", sa.Integer(), nullable=False),
        sa.Column("inicio_raw", sa.Integer(), nullable=True),
        sa.Column("fin_raw", sa.Integer(), nullable=True),
    )
    op.create_index("ix_horario_tramo_ciclo_id", "horario_tramo", ["ciclo_id"])


def _upgrade_existing_ciclo() -> None:
    _add_columns_if_missing(
        "ciclo",
        [
            sa.Column("secciones_status", sa.String(length=16), nullable=True),
            sa.Column("secciones_error", sa.String(length=512), nullable=True),
            sa.Column("modo_status", sa.String(length=16), nullable=True),
            sa.Column("modo_error", sa.String(length=512), nullable=True),
            sa.Column("fotocelula_status", sa.String(length=16), nullable=True),
            sa.Column("fotocelula_error", sa.String(length=512), nullable=True),
            sa.Column("reloj_status", sa.String(length=16), nullable=True),
            sa.Column("reloj_error", sa.String(length=512), nullable=True),
            sa.Column("horarios_status", sa.String(length=16), nullable=True),
            sa.Column("horarios_error", sa.String(length=512), nullable=True),
            sa.Column("diagnostico_status", sa.String(length=16), nullable=True),
            sa.Column("diagnostico_error", sa.String(length=512), nullable=True),
        ],
    )
    _create_index_if_missing("ix_ciclo_timestamp", "ciclo", ["timestamp"])


def _upgrade_existing_horario_tramo() -> None:
    if "timestamp" not in _columns("horario_tramo"):
        op.add_column("horario_tramo", sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True))
        op.execute(
            """
            UPDATE horario_tramo
            SET timestamp = (
                SELECT ciclo.timestamp
                FROM ciclo
                WHERE ciclo.id = horario_tramo.ciclo_id
            )
            WHERE timestamp IS NULL
            """
        )
        with op.batch_alter_table("horario_tramo") as batch_op:
            batch_op.alter_column(
                "timestamp",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
            )
    _create_index_if_missing("ix_horario_tramo_ciclo_id", "horario_tramo", ["ciclo_id"])


def upgrade() -> None:
    tables = _tables()
    if "ciclo" not in tables:
        _create_ciclo()
    else:
        _upgrade_existing_ciclo()

    tables = _tables()
    if "seccion_estado" not in tables:
        _create_seccion_estado()

    tables = _tables()
    if "horario_tramo" not in tables:
        _create_horario_tramo()
    else:
        _upgrade_existing_horario_tramo()


def downgrade() -> None:
    raise RuntimeError("Downgrade destructivo no implementado; hacer backup y migracion manual si se requiere.")
