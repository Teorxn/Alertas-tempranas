"""Aplicación FastAPI del módulo de alertas tempranas.

Ejecutar:
    uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import alertas, auth, estudiantes
from security import (
    CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, csrf_for_session, secure_equal,
    verify_anon_csrf,
)
from settings import settings

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS", "TRACE"}

app = FastAPI(
    title="Alertas tempranas API",
    description="API segura de acompañamiento académico para docentes.",
    version="1.0.0",
    docs_url="/api/docs" if not settings.cookie_secure else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def protecciones(request: Request, call_next):
    ruta = request.url.path
    if request.method not in METODOS_SEGUROS and ruta.startswith("/api/"):
        origen = request.headers.get("origin")
        if origen and origen not in settings.allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "Origen no permitido"})

        cabecera_csrf = request.headers.get(CSRF_HEADER, "")
        if ruta == "/api/auth/login":
            cookie_csrf = request.cookies.get(CSRF_COOKIE, "")
            if not verify_anon_csrf(cookie_csrf) or not secure_equal(cookie_csrf, cabecera_csrf):
                return JSONResponse(status_code=403, content={"detail": "Token CSRF inválido"})
        else:
            token = request.cookies.get(SESSION_COOKIE, "")
            if not token or not secure_equal(csrf_for_session(token), cabecera_csrf):
                return JSONResponse(status_code=403, content={"detail": "Token CSRF inválido"})

    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    respuesta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    respuesta.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    respuesta.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.cookie_secure:
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return respuesta


@app.exception_handler(RequestValidationError)
async def errores_validacion(request: Request, exc: RequestValidationError):
    # No devolvemos los valores recibidos: podrían incluir contraseñas.
    errores = [
        {"campo": ".".join(str(p) for p in error["loc"][1:]) or "cuerpo", "mensaje": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Datos no válidos", "errores": errores})


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(estudiantes.router)
app.include_router(alertas.router)
