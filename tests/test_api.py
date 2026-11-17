"""Pruebas de humo de seguridad y aislamiento por docente.

Ejecutar después de cargar la BD (python -m backend.services.seed):
    pytest -q tests
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

ANA = {"email": "ana.torres@universidad.edu.co", "password": "ClaveSegura123!"}
LUIS = {"email": "luis.herrera@universidad.edu.co", "password": "ClaveSegura123!"}


def _login(credenciales):
    anon = client.get("/api/auth/csrf")
    assert anon.status_code == 200
    token = anon.json()["csrf_token"]
    respuesta = client.post("/api/auth/login", json=credenciales, headers={"X-CSRF-Token": token})
    assert respuesta.status_code == 200, respuesta.text
    return client.cookies.get("ews_csrf")


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_requiere_csrf():
    respuesta = client.post("/api/auth/login", json=ANA)
    assert respuesta.status_code == 403


def test_flujo_completo_y_aislamiento():
    csrf = _login(ANA)
    assert client.get("/api/auth/me").json()["email"] == ANA["email"]

    cursos = client.get("/api/cursos").json()
    assert cursos and all(curso["asignatura"] == "Calculo I" for curso in cursos)

    estudiantes = client.get("/api/estudiantes", params={"momento": "T1_corte1"}).json()
    assert estudiantes
    assert all(e["asignatura"] == "Calculo I" for e in estudiantes)
    inscripcion_id = estudiantes[0]["inscripcion_id"]

    detalle = client.get(f"/api/estudiantes/{inscripcion_id}", params={"momento": "T1_corte1"})
    assert detalle.status_code == 200
    assert detalle.json()["resumen"]["texto"]
    assert detalle.json()["resumen"]["fuente"] in ("llm", "plantilla")

    notificaciones = client.get("/api/notificaciones").json()
    assert all(n["asignatura"] == "Calculo I" for n in notificaciones)
    if notificaciones:
        primera = notificaciones[0]
        marcada = client.patch(
            f"/api/notificaciones/{primera['id']}",
            json={"leida": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert marcada.status_code == 200
        assert marcada.json()["leida"] is True

    # Generar alertas también exige CSRF de sesión.
    assert client.post("/api/alertas/generar", json={"momento": "T1_corte1"}).status_code == 403
    generadas = client.post(
        "/api/alertas/generar", json={"momento": "T1_corte1"}, headers={"X-CSRF-Token": csrf}
    )
    assert generadas.status_code == 200

    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    _login(LUIS)
    ajena = client.get(f"/api/estudiantes/{inscripcion_id}", params={"momento": "T1_corte1"})
    assert ajena.status_code == 404
    propios = client.get("/api/estudiantes", params={"momento": "T1_corte1"}).json()
    assert propios and all(e["asignatura"] == "Fisica I" for e in propios)


def test_busqueda_no_interpreta_sql_ni_html():
    _login(ANA)
    respuesta = client.get("/api/estudiantes", params={"q": "' OR 1=1 -- <script>alert(1)</script>"})
    assert respuesta.status_code == 200
    assert respuesta.json() == []
