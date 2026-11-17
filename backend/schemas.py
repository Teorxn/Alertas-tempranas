"""Contratos de la API. `extra=forbid` evita que lleguen campos inesperados."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MOMENTOS_LITERAL = Literal["T0_inicio", "T1_corte1", "T2_corte2"]
PRIORIDAD_LITERAL = Literal["Alta", "Media", "Baja"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COMPLEXA = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,128}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def email_valido(cls, value: str) -> str:
        value = value.lower()
        if not _EMAIL.match(value):
            raise ValueError("Correo electrónico no válido")
        return value


class ChangePasswordRequest(StrictModel):
    actual: str = Field(min_length=1, max_length=256)
    nueva: str = Field(min_length=10, max_length=128)

    @field_validator("nueva")
    @classmethod
    def nueva_compleja(cls, value: str) -> str:
        if not _COMPLEXA.match(value):
            raise ValueError("La contraseña debe tener 10+ caracteres, mayúscula, minúscula, número y símbolo")
        return value


class CsrfResponse(StrictModel):
    csrf_token: str


class DocenteResponse(StrictModel):
    id: int
    nombre: str
    email: str
    codigo: str


class LoginResponse(StrictModel):
    ok: bool
    docente: DocenteResponse


class MessageResponse(StrictModel):
    mensaje: str


class GenerarRequest(StrictModel):
    momento: MOMENTOS_LITERAL | None = None


class GenerarResponse(StrictModel):
    inscripciones: int
    alertas_activas: int
    momentos: list[str]


class CursoItem(StrictModel):
    asignatura: str
    curso: str
    estudiantes: int


class FactorItem(StrictModel):
    variable: str
    etiqueta: str
    valor: str
    aporte: float


class ResumenItem(StrictModel):
    titulo: str
    texto: str
    accion: str
    fuente: Literal["llm", "plantilla"]


class EstudianteItem(StrictModel):
    inscripcion_id: int
    estudiante_id: str
    asignatura: str
    curso: str
    momento: str
    probabilidad: float
    prioridad: PRIORIDAD_LITERAL
    no_leida: bool


class EstudianteDetalle(StrictModel):
    inscripcion_id: int
    estudiante_id: str
    asignatura: str
    curso: str
    momento: str
    probabilidad: float
    prioridad: PRIORIDAD_LITERAL
    modelo: str
    factores: list[FactorItem]
    resumen: ResumenItem
    senales: list[str]
    notificacion_id: int | None
    no_leida: bool
    atendida: bool


class NotificacionItem(StrictModel):
    id: int
    inscripcion_id: int
    estudiante_id: str
    asignatura: str
    curso: str
    momento: str
    prioridad: PRIORIDAD_LITERAL
    probabilidad: float
    titulo: str
    mensaje: str
    leida: bool
    atendida: bool
    created_at: str


class NotificacionUpdate(StrictModel):
    leida: bool | None = None
    atendida: bool | None = None
