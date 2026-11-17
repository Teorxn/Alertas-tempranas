"""Dependencias compartidas: base de datos, sesión autenticada y auditoría."""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import SessionLocal
from models_db import Auditoria, Docente, Sesion
from security import SESSION_COOKIE, as_utc, hash_token, is_expired
from settings import settings


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "desconocida")[:64]


def get_current_docente(request: Request, db: Session = Depends(get_db)) -> Docente:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesión para continuar")

    sesion = (
        db.query(Sesion)
        .filter(Sesion.token_hash == hash_token(token), Sesion.revoked_at.is_(None))
        .first()
    )
    ahora = datetime.now(timezone.utc)
    if sesion is None or is_expired(sesion.expires_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión vencida")

    ultimo = as_utc(sesion.last_seen_at)
    if ultimo is None or ultimo < ahora - timedelta(minutes=settings.idle_minutes):
        sesion.revoked_at = ahora
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión vencida por inactividad")

    docente = db.get(Docente, sesion.docente_id)
    if docente is None or not docente.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no activo")

    sesion.last_seen_at = ahora
    db.commit()
    return docente


def auditar(db: Session, accion: str, ip: str, docente_id: int | None = None, detalle: dict | None = None) -> None:
    """Registra un evento sin datos sensibles (nunca contraseñas ni notas individuales)."""
    db.add(Auditoria(docente_id=docente_id, accion=accion, ip=ip, detalle=detalle or {}))
