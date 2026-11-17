"""Resumen narrativo del estudiante.

El LLM recibe SOLO datos estructurados y no sensibles: nunca nombres, IDs,
correos, género, estrato ni texto libre. Si no hay API key, falla o se tarda
demasiado, se usa una plantilla local (el sistema sigue funcionando).
"""
import hashlib
import json
import logging

from settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un orientador académico de una universidad. Redactas resúmenes breves para "
    "que un docente acompañe a un estudiante que puede perder una asignatura. "
    "Usa español neutro, cercano y respetuoso. Nunca etiquetes al estudiante, nunca "
    "inventes datos ni mencionemos identificadores, nombres ni información personal. "
    "Devuelve únicamente un objeto JSON con las claves: titulo (máximo 70 caracteres), "
    "texto (2 o 3 frases, máximo 350 caracteres) y accion (una frase, máximo 180 caracteres). "
    "Basate exclusivamente en las señales y acciones sugeridas que recibes."
)

_CLIENT = None
if settings.llm_enabled:
    try:
        from openai import OpenAI

        _CLIENT = OpenAI(api_key=settings.openai_api_key, timeout=8.0, max_retries=0)
    except Exception as exc:  # pragma: no cover - solo si la librería falla al iniciar
        logger.warning("No se pudo iniciar el cliente LLM: %s", type(exc).__name__)
        _CLIENT = None


def firma_resumen(payload: dict) -> str:
    canonico = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def resumen_plantilla(payload: dict) -> dict:
    prioridad = payload.get("prioridad", "Media")
    asignatura = payload.get("asignatura", "la asignatura")
    prob = float(payload.get("probabilidad", 0.0))
    senales = [s.get("etiqueta", "") for s in payload.get("senales", []) if s.get("etiqueta")]
    acciones = [a for a in payload.get("acciones", []) if a]

    texto = (
        f"La predicción estima un {prob:.0%} de probabilidad de no aprobar {asignatura} "
        f"en este momento del semestre. "
    )
    if senales:
        texto += "Señales que más influyen: " + "; ".join(senales[:3]) + "."
    else:
        texto += "No se observan señales individuales destacadas; conviene revisar el caso con el estudiante."

    accion = acciones[0] if acciones else "Programar una conversación breve para conocer cómo va el semestre."
    if len(acciones) > 1:
        accion += " También: " + acciones[1] + "."
    return {
        "titulo": f"Prioridad {prioridad.lower()} en {asignatura}",
        "texto": texto[:350],
        "accion": accion[:180],
    }


def _validar(datos: object) -> dict | None:
    if not isinstance(datos, dict):
        return None
    resultado = {}
    for clave, limite in (("titulo", 70), ("texto", 350), ("accion", 180)):
        valor = datos.get(clave)
        if not isinstance(valor, str) or not valor.strip():
            return None
        resultado[clave] = valor.strip()[:limite]
    return resultado


def resumen_llm(payload: dict) -> dict | None:
    if _CLIENT is None:
        return None
    try:
        respuesta = _CLIENT.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_completion_tokens=300,
        )
        contenido = respuesta.choices[0].message.content or ""
        return _validar(json.loads(contenido))
    except Exception as exc:
        # No registramos el payload: podría contener información del estudiante.
        logger.warning("LLM no disponible, se usa plantilla: %s", type(exc).__name__)
        return None


def generar_resumen(payload: dict) -> tuple[dict, str]:
    if settings.llm_enabled:
        redaccion = resumen_llm(payload)
        if redaccion:
            return redaccion, "llm"
    return resumen_plantilla(payload), "plantilla"
