from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase


class BaseEstados(DeclarativeBase):
    pass


class BaseHist(DeclarativeBase):
    pass


class EstadoActual(BaseEstados):
    __tablename__ = "estado_actual"

    seccion_id = Column(Integer, primary_key=True)
    automatico = Column(Boolean, nullable=False)
    manual = Column(Boolean, nullable=False)
    horario_activo = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    fins_ok = Column(Boolean, nullable=False)


class EstadoSistema(BaseEstados):
    __tablename__ = "estado_sistema"

    id = Column(Integer, primary_key=True, default=1)
    modfunalu = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    fins_ok = Column(Boolean, nullable=False)
    error_msg = Column(String, nullable=True)


class HistorialSecciones(BaseHist):
    __tablename__ = "historial_secciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    seccion_id = Column(Integer, nullable=False)
    automatico = Column(Boolean, nullable=False)
    manual = Column(Boolean, nullable=False)
    horario_activo = Column(Boolean, nullable=False)


class HistorialSistema(BaseHist):
    __tablename__ = "historial_sistema"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    modfunalu = Column(Integer, nullable=True)
    fins_ok = Column(Boolean, nullable=False)
    error_msg = Column(String, nullable=True)
