from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint

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
    reset_temporizado_status = Column(String(16), nullable=True)
    reset_temporizado_error = Column(String(512), nullable=True)
    hmi_original_status = Column(String(16), nullable=True)
    hmi_original_error = Column(String(512), nullable=True)
    reloj_ar_status = Column(String(16), nullable=True)
    reloj_ar_error = Column(String(512), nullable=True)
    salidas_wr_status = Column(String(16), nullable=True)
    salidas_wr_error = Column(String(512), nullable=True)

    modfunalu = Column(Integer, nullable=True)
    modo_label = Column(String(32), nullable=True)

    # Redundant current fields kept on ciclo for compact historial/API views.
    fotocelula_entrada = Column(Boolean, nullable=True)
    fotocelula_mem_fun = Column(Boolean, nullable=True)
    fotocelula_mem_act = Column(Boolean, nullable=True)

    plc_reloj_raw_words = Column(Text, nullable=True)
    plc_reloj_encoding = Column(String(16), nullable=True)
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
    automatico_calculado = Column(Boolean, nullable=False)
    manual_activo = Column(Boolean, nullable=False)
    salida_interna = Column(Boolean, nullable=False)
    salida_wr = Column(Boolean, nullable=True)


class HorarioTramo(Base):
    __tablename__ = "horario_tramo"
    __table_args__ = (
        Index("ix_horario_tramo_ciclo_id", "ciclo_id"),
        Index("ix_horario_tramo_timestamp", "timestamp"),
        Index("ix_horario_tramo_tramo_timestamp", "tramo_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    timestamp = Column(UTCDateTime, nullable=False)
    tramo_id = Column(Integer, nullable=False)
    inicio_raw = Column(Integer, nullable=True)
    fin_raw = Column(Integer, nullable=True)
    inicio_raw_words = Column(Text, nullable=True)
    fin_raw_words = Column(Text, nullable=True)
    source_json = Column(Text, nullable=True)
    inicio_hora = Column(Integer, nullable=True)
    inicio_minuto = Column(Integer, nullable=True)
    fin_hora = Column(Integer, nullable=True)
    fin_minuto = Column(Integer, nullable=True)


class FotocelulaState(Base):
    __tablename__ = "fotocelula_state"
    __table_args__ = (
        Index("ix_fotocelula_state_ciclo_id", "ciclo_id"),
        UniqueConstraint("ciclo_id", name="uq_fotocelula_state_ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    entrada_raw = Column(Boolean, nullable=False)
    mem_fun = Column(Boolean, nullable=False)
    filtrada_activa = Column(Boolean, nullable=False)
    temporizador_activacion_s = Column(Integer, nullable=False)
    temporizador_desactivacion_s = Column(Integer, nullable=False)
    retardo_activacion_s = Column(Integer, nullable=False)
    retardo_desactivacion_s = Column(Integer, nullable=False)


class ResetTemporizadoState(Base):
    __tablename__ = "reset_temporizado_state"
    __table_args__ = (
        Index("ix_reset_temporizado_state_ciclo_id", "ciclo_id"),
        UniqueConstraint("ciclo_id", name="uq_reset_temporizado_state_ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    w1_raw = Column(Integer, nullable=False)
    dm_raw_words = Column(Text, nullable=False)
    horario_global_activo = Column(Boolean, nullable=False)
    reset_activo = Column(Boolean, nullable=False)
    retardo_segundo_apagado_s = Column(Integer, nullable=False)
    temporizador_segundo_apagado_s = Column(Integer, nullable=False)
    contador_apagados = Column(Integer, nullable=False)
    max_reintentos = Column(Integer, nullable=False)


class HmiOriginalState(Base):
    __tablename__ = "hmi_original_state"
    __table_args__ = (
        Index("ix_hmi_original_state_ciclo_id", "ciclo_id"),
        UniqueConstraint("ciclo_id", name="uq_hmi_original_state_ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    indice_seccion = Column(Integer, nullable=False)
    indice_anterior = Column(Integer, nullable=False)
    h10_raw = Column(Integer, nullable=False)
    automatico_seccion_seleccionada = Column(Boolean, nullable=False)
    manual_seccion_seleccionada = Column(Boolean, nullable=False)
    orden_transferencia_comun = Column(Boolean, nullable=False)
    indicacion_activacion_alumbrado_seccion = Column(Boolean, nullable=False)


class RelojArState(Base):
    __tablename__ = "reloj_ar_state"
    __table_args__ = (
        Index("ix_reloj_ar_state_ciclo_id", "ciclo_id"),
        UniqueConstraint("ciclo_id", name="uq_reloj_ar_state_ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    raw_a351 = Column(Integer, nullable=False)
    raw_a352 = Column(Integer, nullable=False)
    raw_a353 = Column(Integer, nullable=False)
    ar_minuto = Column(Integer, nullable=False)
    ar_segundo = Column(Integer, nullable=False)
    ar_dia = Column(Integer, nullable=False)
    ar_hora = Column(Integer, nullable=False)
    ar_anio = Column(Integer, nullable=False)
    ar_mes = Column(Integer, nullable=False)
    encoding = Column(String(32), nullable=False)


class SalidasWrState(Base):
    __tablename__ = "salidas_wr_state"
    __table_args__ = (
        Index("ix_salidas_wr_state_ciclo_id", "ciclo_id"),
        UniqueConstraint("ciclo_id", name="uq_salidas_wr_state_ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    raw_words = Column(Text, nullable=False)
    cercha_salidas = Column(Text, nullable=False)
    physical_io_mapping_status = Column(String(64), nullable=False)
