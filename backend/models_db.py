"""Modelos ORM: docentes, sesiones, inscripciones, predicciones y notificaciones.

La clave de aislamiento es `Inscripcion.docente_id`: cada endpoint filtra por
el docente de la sesión, así que un profesor nunca ve cursos de otro.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Docente(Base):
    __tablename__ = "docentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # DOC-01
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Sesion(Base):
    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (
        UniqueConstraint("estudiante_id", "asignatura", "curso", name="uq_inscripcion"),
        Index("ix_inscripcion_docente", "docente_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[str] = mapped_column(String(32), index=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id", ondelete="CASCADE"), index=True)
    asignatura: Mapped[str] = mapped_column(String(120), index=True)
    curso: Mapped[str] = mapped_column(String(32), index=True)
    datos: Mapped[dict] = mapped_column(JSON)  # solo columnas académicas permitidas
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Prediccion(Base):
    __tablename__ = "predicciones"
    __table_args__ = (UniqueConstraint("inscripcion_id", "momento", name="uq_prediccion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inscripcion_id: Mapped[int] = mapped_column(
        ForeignKey("inscripciones.id", ondelete="CASCADE"), index=True
    )
    momento: Mapped[str] = mapped_column(String(32), index=True)
    probabilidad: Mapped[float] = mapped_column(Float)
    prioridad: Mapped[str] = mapped_column(String(8))
    modelo: Mapped[str] = mapped_column(String(80))
    factores: Mapped[list] = mapped_column(JSON, default=list)
    resumen_titulo: Mapped[str] = mapped_column(String(200), default="")
    resumen_texto: Mapped[str] = mapped_column(String(2000), default="")
    resumen_accion: Mapped[str] = mapped_column(String(1000), default="")
    resumen_fuente: Mapped[str] = mapped_column(String(16), default="plantilla")
    resumen_firma: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notificacion(Base):
    __tablename__ = "notificaciones"
    __table_args__ = (UniqueConstraint("inscripcion_id", "momento", name="uq_notificacion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id", ondelete="CASCADE"), index=True)
    inscripcion_id: Mapped[int] = mapped_column(
        ForeignKey("inscripciones.id", ondelete="CASCADE"), index=True
    )
    prediccion_id: Mapped[int | None] = mapped_column(
        ForeignKey("predicciones.id", ondelete="SET NULL"), nullable=True
    )
    momento: Mapped[str] = mapped_column(String(32), index=True)
    prioridad: Mapped[str] = mapped_column(String(8))
    probabilidad: Mapped[float] = mapped_column(Float)
    titulo: Mapped[str] = mapped_column(String(200))
    mensaje: Mapped[str] = mapped_column(String(500))
    activa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    leida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    atendida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Auditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    docente_id: Mapped[int | None] = mapped_column(
        ForeignKey("docentes.id", ondelete="SET NULL"), nullable=True
    )
    accion: Mapped[str] = mapped_column(String(64), index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    detalle: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
