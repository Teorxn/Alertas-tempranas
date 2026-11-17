"""Puente entre los modelos entrenados y la API: scoring, explicación y alertas."""
from dataclasses import dataclass
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import (
    DESCRIPCION_MOMENTOS, MODELS_DIR, MOMENTOS, UMBRAL_ALTA, UMBRAL_MEDIA,
)
from deps import auditar
from explicar import SENALES
from features import construir_features
from models_db import Docente, Inscripcion, Notificacion, Prediccion, utcnow
from services.llm import firma_resumen, generar_resumen
from settings import settings


@lru_cache(maxsize=3)
def cargar_modelo(momento: str) -> dict:
    return joblib.load(MODELS_DIR / f"{momento}.joblib")


def nivel(prob: float) -> str:
    if prob >= UMBRAL_ALTA:
        return "Alta"
    if prob >= UMBRAL_MEDIA:
        return "Media"
    return "Baja"


@dataclass
class LlmBudget:
    """Limita cuántas redacciones se piden al proveedor de pago por lote."""

    remaining: int = settings.llm_max_calls

    def permite(self) -> bool:
        return self.remaining > 0

    def consumir(self) -> None:
        self.remaining -= 1


def _factores(paquete: dict, datos: dict, top: int = 4) -> list[dict]:
    """Oclusión: reemplaza cada variable por su valor típico y mide el cambio en logit."""
    fila = pd.DataFrame([datos])
    try:
        X = construir_features(fila, paquete["momento"]).reset_index(drop=True)
    except KeyError as exc:
        raise ValueError(f"Falta la columna {exc} en los datos del estudiante") from exc
    if X.empty:
        return []

    columnas = list(X.columns)
    variantes = pd.concat([X] * (len(columnas) + 1), ignore_index=True)
    for numero, columna in enumerate(columnas, start=1):
        variantes.loc[numero, columna] = paquete["referencia"].get(columna, X.iloc[0][columna])
    variantes = variantes.apply(lambda s: s if s.dtype == object else s.astype(float))

    probabilidades = np.clip(paquete["modelo"].predict_proba(variantes)[:, 1], 1e-6, 1 - 1e-6)
    logits = np.log(probabilidades / (1 - probabilidades))
    aportes = logits[0] - logits[1:]
    base = X.iloc[0]

    salida: list[dict] = []
    for indice in np.argsort(-aportes):
        if aportes[indice] <= 0.05 or len(salida) >= top:
            break
        variable = columnas[indice]
        valor = base[variable]
        descripcion, accion = SENALES.get(variable, (variable.replace("_", " ") + ": {v}", None))
        if variable == "nota_minima_requerida" and float(valor) > 5:
            descripcion = "necesitaría {v:.1f} en lo que resta: ya no es alcanzable en la escala 0-5"
            accion = "Remitir a consejería académica para evaluar opciones de recuperación."
        if isinstance(valor, (int, float, np.number)) and pd.notna(valor):
            etiqueta = descripcion.format(v=float(valor))
        else:
            etiqueta = f"{variable.replace('_', ' ')}: {valor}"
        salida.append({
            "variable": variable,
            "etiqueta": etiqueta,
            "valor": "" if pd.isna(valor) else str(valor),
            "aporte": float(aportes[indice]),
            "accion": accion or "",
        })
    return salida


def _payload_llm(datos: dict, momento: str, probabilidad: float, prioridad: str, factores: list[dict]) -> dict:
    acciones: list[str] = []
    for factor in factores:
        if factor["accion"] and factor["accion"] not in acciones:
            acciones.append(factor["accion"])

    # Lista blanca: nunca se envían identificadores, género, estrato ni datos de contacto.
    return {
        "asignatura": datos.get("asignatura", ""),
        "momento": momento,
        "prioridad": prioridad,
        "probabilidad": round(float(probabilidad), 3),
        "senales": [{"etiqueta": f["etiqueta"], "aporte": round(f["aporte"], 2)} for f in factores],
        "acciones": acciones,
    }


def procesar_inscripcion(
    db: Session, inscripcion: Inscripcion, momento: str, presupuesto: LlmBudget | None = None
) -> Prediccion:
    """Calcula (o reutiliza) la predicción de una inscripción en un momento."""
    presupuesto = presupuesto or LlmBudget()
    paquete = cargar_modelo(momento)
    datos = dict(inscripcion.datos)

    X = construir_features(pd.DataFrame([datos]), momento)
    probabilidad = float(paquete["modelo"].predict_proba(X)[0, 1])
    prioridad = nivel(probabilidad)
    factores = _factores(paquete, datos)
    payload = _payload_llm(datos, momento, probabilidad, prioridad, factores)
    firma = firma_resumen(payload)

    prediccion = db.execute(
        select(Prediccion).where(
            Prediccion.inscripcion_id == inscripcion.id, Prediccion.momento == momento
        )
    ).scalar_one_or_none()

    if prediccion is None:
        prediccion = Prediccion(inscripcion_id=inscripcion.id, momento=momento)

    if prediccion.resumen_firma != firma:
        if presupuesto.permite():
            redaccion, fuente = generar_resumen(payload)
            presupuesto.consumir()
        else:
            from services.llm import resumen_plantilla

            redaccion, fuente = resumen_plantilla(payload), "plantilla"
        prediccion.resumen_titulo = redaccion["titulo"]
        prediccion.resumen_texto = redaccion["texto"]
        prediccion.resumen_accion = redaccion["accion"]
        prediccion.resumen_fuente = fuente
        prediccion.resumen_firma = firma

    prediccion.probabilidad = probabilidad
    prediccion.prioridad = prioridad
    prediccion.modelo = paquete["nombre"]
    prediccion.factores = [
        {k: f[k] for k in ("variable", "etiqueta", "valor", "aporte")} for f in factores
    ]
    prediccion.updated_at = utcnow()
    db.add(prediccion)
    db.flush()

    _sincronizar_notificacion(db, inscripcion, prediccion, momento)
    return prediccion


def _sincronizar_notificacion(
    db: Session, inscripcion: Inscripcion, prediccion: Prediccion, momento: str
) -> None:
    activa = prediccion.prioridad in ("Alta", "Media")
    notificacion = db.execute(
        select(Notificacion).where(
            Notificacion.inscripcion_id == inscripcion.id, Notificacion.momento == momento
        )
    ).scalar_one_or_none()

    if notificacion is None:
        if not activa:
            return
        notificacion = Notificacion(
            docente_id=inscripcion.docente_id,
            inscripcion_id=inscripcion.id,
            prediccion_id=prediccion.id,
            momento=momento,
        )

    notificacion.prediccion_id = prediccion.id
    notificacion.prioridad = prediccion.prioridad
    notificacion.probabilidad = prediccion.probabilidad
    notificacion.titulo = prediccion.resumen_titulo
    notificacion.mensaje = prediccion.resumen_texto[:500]
    notificacion.activa = activa
    notificacion.updated_at = utcnow()
    # Si la alerta vuelve a activarse después de resuelta, se marca como no leída.
    if activa and notificacion.leida_at is not None and prediccion.prioridad == "Alta":
        notificacion.leida_at = None
    db.add(notificacion)


def generar_alertas(
    db: Session, docente: Docente, momentos: list[str], ip: str = ""
) -> dict:
    inscripciones = db.execute(
        select(Inscripcion).where(Inscripcion.docente_id == docente.id)
    ).scalars().all()
    presupuesto = LlmBudget()

    for inscripcion in inscripciones:
        for momento in momentos:
            procesar_inscripcion(db, inscripcion, momento, presupuesto)

    activas = db.execute(
        select(Notificacion).where(
            Notificacion.docente_id == docente.id,
            Notificacion.momento.in_(momentos),
            Notificacion.activa.is_(True),
        )
    ).scalars().all()
    db.commit()
    auditar(
        db, "alertas_generadas", ip, docente.id,
        {"inscripciones": len(inscripciones), "momentos": momentos},
    )
    db.commit()
    return {
        "inscripciones": len(inscripciones),
        "alertas_activas": len(activas),
        "momentos": momentos,
    }


def descripcion_momento(momento: str) -> str:
    return DESCRIPCION_MOMENTOS.get(momento, momento)


def momentos_validos() -> list[str]:
    return list(MOMENTOS)
