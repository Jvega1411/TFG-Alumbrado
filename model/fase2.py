from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, UniqueConstraint

from model.database import Base, UTCDateTime


class Ciclo(Base):
    __tablename__ = "ciclo"
    __table_args__ = (
        Index("ix_ciclo_timestamp", "timestamp"),
        UniqueConstraint("timestamp", name="uq_ciclo_timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(UTCDateTime, nullable=False)
    fins_ok = Column(Boolean, nullable=False)
    fins_error = Column(String(512), nullable=True)
    secciones_status = Column(String(16), nullable=True)
    secciones_error = Column(String(512), nullable=True)
    modo_status = Column(String(16), nullable=True)
    modo_error = Column(String(512), nullable=True)
    fotocelula_status = Column(String(16), nullable=True)
    fotocelula_error = Column(String(512), nullable=True)
    reloj_status = Column(String(16), nullable=True)
    reloj_error = Column(String(512), nullable=True)
    horarios_status = Column(String(16), nullable=True)
    horarios_error = Column(String(512), nullable=True)
    diagnostico_status = Column(String(16), nullable=True)
    diagnostico_error = Column(String(512), nullable=True)
    modfunalu = Column(Integer, nullable=True)
    fotocelula_entrada = Column(Boolean, nullable=True)
    fotocelula_mem_fun = Column(Boolean, nullable=True)
    fotocelula_mem_act = Column(Boolean, nullable=True)
    plc_seg = Column(Integer, nullable=True)
    plc_min = Column(Integer, nullable=True)
    plc_hora = Column(Integer, nullable=True)
    plc_dia = Column(Integer, nullable=True)
    plc_mes = Column(Integer, nullable=True)
    plc_anio = Column(Integer, nullable=True)
    plc_diasem = Column(Integer, nullable=True)
    cycle_time_error = Column(Boolean, nullable=True)
    low_battery = Column(Boolean, nullable=True)
    io_verify_error = Column(Boolean, nullable=True)


class SeccionEstado(Base):
    __tablename__ = "seccion_estado"
    __table_args__ = (
        Index("ix_seccion_estado_ciclo_id", "ciclo_id"),
        Index("ix_seccion_estado_timestamp", "timestamp"),
        Index("ix_seccion_estado_seccion_timestamp", "seccion_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    timestamp = Column(UTCDateTime, nullable=False)
    seccion_id = Column(Integer, nullable=False)
    automatico = Column(Boolean, nullable=False)
    manual = Column(Boolean, nullable=False)
    horario_activo = Column(Boolean, nullable=False)


class HorarioTramo(Base):
    __tablename__ = "horario_tramo"
    __table_args__ = (
        Index("ix_horario_tramo_ciclo_id", "ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    timestamp = Column(UTCDateTime, nullable=False)
    tramo_id = Column(Integer, nullable=False)
    inicio_raw = Column(Integer, nullable=True)
    fin_raw = Column(Integer, nullable=True)
