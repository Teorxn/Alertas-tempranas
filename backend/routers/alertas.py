"""Generación de alertas y centro de notificaciones del docente."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from config import MOMENTOS
from deps import auditar, client_ip, get_current_docente, get_db
from models_db import Inscripcion, Notificacion, utcnow
from schemas import GenerarRequest, GenerarResponse, NotificacionItem, NotificacionUpdate
from services.scoring import generar_alertas

router = APIRouter(prefix="/api", tags=["alertas"])


@router.post("/alertas/generar", response_model=GenerarResponse)
def generar(
    body: GenerarRequest,
    request: Request,
    docente=Depends(get_current_docente),
    db: Session = Depends(get_db),
):
    momentos = [body.momento] if body.momento else list(MOMENTOS)
    return GenerarResponse(**generar_alertas(db, docente, momentos, client_ip(request)))


def _consulta_notificaciones(docente_id: int):
    return (
        select(Notificacion, Inscripcion)
        .join(Inscripcion, Inscripcion.id == Notificacion.inscripcion_id)
        .where(Notificacion.docente_id == docente_id, Notificacion.activa.is_(True))
    )


@router.get("/notificaciones", response_model=list[NotificacionItem])
def notificaciones(
    limite: int = Query(default=50, ge=1, le=200),
    docente=Depends(get_current_docente),
    db: Session = Depends(get_db),
):
    filas = db.execute(
        _consulta_notificaciones(docente.id)
        .order_by(Notificacion.created_at.desc(), Notificacion.id.desc())
        .limit(limite)
    ).all()
    return [
        NotificacionItem(
            id=n.id,
            inscripcion_id=n.inscripcion_id,
            estudiante_id=i.estudiante_id,
            asignatura=i.asignatura,
            curso=i.curso,
            momento=n.momento,
            prioridad=n.prioridad,
            probabilidad=round(n.probabilidad, 4),
            titulo=n.titulo,
            mensaje=n.mensaje,
            leida=n.leida_at is not None,
            atendida=n.atendida_at is not None,
            created_at=n.created_at.isoformat() if n.created_at else "",
        )
        for n, i in filas
    ]


@router.get("/notificaciones/resumen")
def resumen_notificaciones(docente=Depends(get_current_docente), db: Session = Depends(get_db)):
    filas = db.execute(
        select(
            func.count(Notificacion.id),
            func.sum(case((Notificacion.leida_at.is_(None), 1), else_=0)),
            func.sum(case((Notificacion.atendida_at.is_(None), 1), else_=0)),
        )
        .where(Notificacion.docente_id == docente.id, Notificacion.activa.is_(True))
    ).one()
    return {"activas": filas[0] or 0, "no_leidas": filas[1] or 0, "pendientes": filas[2] or 0}


@router.patch("/notificaciones/{notificacion_id}", response_model=NotificacionItem)
def actualizar_notificacion(
    notificacion_id: int,
    body: NotificacionUpdate,
    request: Request,
    docente=Depends(get_current_docente),
    db: Session = Depends(get_db),
):
    fila = db.execute(
        _consulta_notificaciones(docente.id).where(Notificacion.id == notificacion_id)
    ).first()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificación no encontrada")
    notificacion, inscripcion = fila

    if body.leida is not None:
        notificacion.leida_at = utcnow() if body.leida else None
    if body.atendida is not None:
        notificacion.atendida_at = utcnow() if body.atendida else None
    notificacion.updated_at = utcnow()
    db.commit()
    auditar(db, "notificacion_actualizada", client_ip(request), docente.id,
            {"notificacion_id": notificacion_id})
    db.commit()

    return NotificacionItem(
        id=notificacion.id,
        inscripcion_id=notificacion.inscripcion_id,
        estudiante_id=inscripcion.estudiante_id,
        asignatura=inscripcion.asignatura,
        curso=inscripcion.curso,
        momento=notificacion.momento,
        prioridad=notificacion.prioridad,
        probabilidad=round(notificacion.probabilidad, 4),
        titulo=notificacion.titulo,
        mensaje=notificacion.mensaje,
        leida=notificacion.leida_at is not None,
        atendida=notificacion.atendida_at is not None,
        created_at=notificacion.created_at.isoformat() if notificacion.created_at else "",
    )
