"""Autenticación: CSRF inicial, login, sesión, cierre y cambio de contraseña."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from deps import auditar, client_ip, get_current_docente, get_db
from models_db import Docente, Sesion, utcnow
from schemas import (
    ChangePasswordRequest, CsrfResponse, DocenteResponse, LoginRequest, LoginResponse,
    MessageResponse,
)
from security import (
    CSRF_COOKIE, SESSION_COOKIE, as_utc, csrf_for_session, hash_password, hash_token,
    login_limiter, mint_anon_csrf, new_session_token, session_expiry, verify_password,
)
from settings import settings

router = APIRouter(prefix="/api/auth", tags=["autenticación"])


def _cookie_args() -> dict:
    return {"secure": settings.cookie_secure, "samesite": "lax", "path": "/"}


@router.get("/csrf", response_model=CsrfResponse)
def emitir_csrf(response: Response) -> CsrfResponse:
    token = mint_anon_csrf()
    response.set_cookie(CSRF_COOKIE, token, httponly=False, max_age=3600, **_cookie_args())
    return CsrfResponse(csrf_token=token)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    ventana = settings.login_window_minutes * 60
    clave_usuario = f"usuario:{ip}:{body.email}"
    clave_ip = f"ip:{ip}"
    if not login_limiter.allow(clave_usuario, 10, ventana) or not login_limiter.allow(clave_ip, 40, ventana):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Intenta más tarde.")

    docente = db.execute(select(Docente).where(Docente.email == body.email)).scalar_one_or_none()
    ahora = datetime.now(timezone.utc)
    if docente and docente.locked_until and as_utc(docente.locked_until) > ahora:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Cuenta bloqueada temporalmente.")

    if docente is None or not docente.activo or not verify_password(body.password, docente.password_hash):
        if docente is not None:
            docente.failed_attempts += 1
            if docente.failed_attempts >= settings.login_max_failures:
                docente.locked_until = ahora + timedelta(minutes=settings.login_window_minutes)
        db.commit()
        auditar(db, "login_fallido", ip, docente.id if docente else None,
                {"dominio": body.email.split("@")[-1]})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")

    login_limiter.reset(clave_usuario)
    docente.failed_attempts = 0
    docente.locked_until = None

    token = new_session_token()
    db.add(Sesion(
        token_hash=hash_token(token),
        docente_id=docente.id,
        expires_at=session_expiry(),
        last_seen_at=utcnow(),
    ))
    db.commit()
    auditar(db, "login_ok", ip, docente.id)
    db.commit()

    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, max_age=settings.session_hours * 3600, **_cookie_args()
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_for_session(token), httponly=False,
        max_age=settings.session_hours * 3600, **_cookie_args()
    )
    return LoginResponse(ok=True, docente=DocenteResponse(
        id=docente.id, nombre=docente.nombre, email=docente.email, codigo=docente.codigo
    ))


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, docente=Depends(get_current_docente), db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE, "")
    sesion = db.execute(
        select(Sesion).where(Sesion.token_hash == hash_token(token), Sesion.docente_id == docente.id)
    ).scalar_one_or_none()
    if sesion is not None:
        sesion.revoked_at = utcnow()
        db.commit()
    auditar(db, "logout", client_ip(request), docente.id)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return MessageResponse(mensaje="Sesión cerrada")


@router.get("/me", response_model=DocenteResponse)
def yo(docente=Depends(get_current_docente)) -> DocenteResponse:
    return DocenteResponse(
        id=docente.id, nombre=docente.nombre, email=docente.email, codigo=docente.codigo
    )


@router.post("/password", response_model=MessageResponse)
def cambiar_clave(
    body: ChangePasswordRequest,
    request: Request,
    docente=Depends(get_current_docente),
    db: Session = Depends(get_db),
):
    if not verify_password(body.actual, docente.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    docente.password_hash = hash_password(body.nueva)
    token_actual = hash_token(request.cookies.get(SESSION_COOKIE, ""))
    sesiones = db.execute(select(Sesion).where(Sesion.docente_id == docente.id)).scalars().all()
    for sesion in sesiones:
        if sesion.token_hash != token_actual and sesion.revoked_at is None:
            sesion.revoked_at = utcnow()
    db.commit()
    auditar(db, "password_cambiada", client_ip(request), docente.id)
    db.commit()
    return MessageResponse(mensaje="Contraseña actualizada. Las demás sesiones se cerraron.")
