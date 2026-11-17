"""Listados y fichas individuales, siempre limitados al docente autenticado."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from deps import get_current_docente, get_db
from models_db import Inscripcion, Notificacion, Prediccion
from schemas import (
    CursoItem, EstudianteDetalle, EstudianteItem, FactorItem, MOMENTOS_LITERAL,
    PRIORIDAD_LITERAL, ResumenItem,
)
from services.scoring import procesar_inscripcion
from settings import settings

router = APIRouter(prefix="/api", tags=["estudiantes"])


def _escape_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/cursos", response_model=list[CursoItem])
def cursos(docente=Depends(get_current_docente), db: Session = Depends(get_db)):
    filas = db.execute(
        select(Inscripcion.asignatura, Inscripcion.curso, func.count(Inscripcion.id))
        .where(Inscripcion.docente_id == docente.id)
        .group_by(Inscripcion.asignatura, Inscripcion.curso)
        .order_by(Inscripcion.asignatura, Inscripcion.curso)
    ).all()
    return [CursoItem(asignatura=a, curso=c, estudiantes=n) for a, c, n in filas]


@router.get("/estudiantes", response_model=list[EstudianteItem])
def estudiantes(
    momento: MOMENTOS_LITERAL = "T1_corte1",
    asignatura: str | None = Query(default=None, max_length=120),
    curso: str | None = Query(default=None, max_length=32),
    prioridad: PRIORIDAD_LITERAL | None = None,
    q: str | None = Query(default=None, max_length=60),
    solo_alertas: bool = False,
    docente=Depends(get_current_docente),
    db: Session = Depends(get_db),
):
    consulta = (
        select(Inscripcion, Prediccion, Notificacion)
        .join(Prediccion, Prediccion.inscripcion_id == Inscripcion.id)
        .outerjoin(
            Notificacion,
            (Notificacion.inscripcion_id == Inscripcion.id) & (Notificacion.momento == Prediccion.momento),
        )
        .where(Inscripcion.docente_id == docente.id, Prediccion.momento == momento)
    )
    if asignatura:
        consulta = consulta.where(Inscripcion.asignatura == asignatura)
    if curso:
        consulta = consulta.where(Inscripcion.curso == curso)
    if prioridad:
        consulta = consulta.where(Prediccion.prioridad == prioridad)
    if solo_alertas:
        consulta = consulta.where(Notificacion.activa.is_(True))
    if q and q.strip():
        patron = f"%{_escape_like(q.strip())}%"
        consulta = consulta.where(
            Inscripcion.estudiante_id.ilike(patron, escape="\\")
            | Inscripcion.asignatura.ilike(patron, escape="\\")
            | Inscripcion.curso.ilike(patron, escape="\\")
        )
    consulta = consulta.limit(1000)

    filas = db.execute(consulta).all()
    _items = [
        EstudianteItem(
            inscripcion_id=ins.id,
            estudiante_id=ins.estudiante_id,
            asignatura=ins.asignatura,
            curso=ins.curso,
            momento=pred.momento,
            probabilidad=round(pred.probabilidad, 4),
            prioridad=pred.prioridad,
            no_leida=bool(notificacion and notificacion.activa and notificacion.leida_at is None),
        )
        for ins, pred, notificacion in filas
    ]
    orden = {"Alta": 0, "Media": 1, "Baja": 2}
    _items.sort(key=lambda x: (orden.get(x.prioridad, 3), -x.probabilidad, x.estudiante_id))
    return _items


@router.get("/estudiantes/{inscripcion_id}", response_model=EstudianteDetalle)
def detalle(
    inscripcion_id: int,
    momento: MOMENTOS_LITERAL = "T1_corte1",
    docente=Depends(get_current_docente),
    db: Session = Depends(get_db),
):
    inscripcion = db.get(Inscripcion, inscripcion_id)
    # 404 en vez de 403 para no revelar que existe una inscripción de otro docente.
    if inscripcion is None or inscripcion.docente_id != docente.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inscripción no encontrada")

    prediccion = procesar_inscripcion(db, inscripcion, momento)
    db.commit()
    notificacion = db.execute(
        select(Notificacion).where(
            Notificacion.inscripcion_id == inscripcion.id, Notificacion.momento == momento
        )
    ).scalar_one_or_none()

    factores = [
        FactorItem(
            variable=f["variable"], etiqueta=f["etiqueta"], valor=f["valor"], aporte=round(f["aporte"], 3)
        )
        for f in prediccion.factores
    ]
    return EstudianteDetalle(
        inscripcion_id=inscripcion.id,
        estudiante_id=inscripcion.estudiante_id,
        asignatura=inscripcion.asignatura,
        curso=inscripcion.curso,
        momento=momento,
        probabilidad=round(prediccion.probabilidad, 4),
        prioridad=prediccion.prioridad,
        modelo=prediccion.modelo,
        factores=factores,
        resumen=ResumenItem(
            titulo=prediccion.resumen_titulo,
            texto=prediccion.resumen_texto,
            accion=prediccion.resumen_accion,
            fuente=prediccion.resumen_fuente,  # type: ignore[arg-type]
        ),
        senales=[f.etiqueta for f in factores],
        notificacion_id=notificacion.id if notificacion else None,
        no_leida=bool(notificacion and notificacion.activa and notificacion.leida_at is None),
        atendida=bool(notificacion and notificacion.atendida_at is not None),
    )
