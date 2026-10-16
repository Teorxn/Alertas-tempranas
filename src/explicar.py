"""Puntuación, semáforo, explicación individual y mensaje para el docente.

La explicación usa 'oclusión': se reemplaza cada variable por un valor típico
y se mide cuánto baja la probabilidad. Es simple y funciona con cualquier
modelo; en la siguiente fase se puede cambiar por SHAP.
"""
import joblib
import numpy as np
import pandas as pd

from config import MODELS_DIR, UMBRAL_ALTA, UMBRAL_MEDIA
from features import construir_features

# Lenguaje de apoyo, no estigmatizante: "prioridad de acompañamiento", no "en riesgo"
NIVELES = ["Baja", "Media", "Alta"]

SENALES = {  # variable -> (cómo se describe, acción sugerida)
    "nota_corte1": ("nota del corte 1 de {v:.1f}", "Repasar en tutoría los temas evaluados en el corte 1."),
    "nota_corte2": ("nota del corte 2 de {v:.1f}", "Revisar con el estudiante los errores del corte 2."),
    "parcial1": ("parcial 1 con {v:.1f}", "Ofrecer una sesión de refuerzo sobre los temas del parcial 1."),
    "parcial2": ("parcial 2 con {v:.1f}", "Ofrecer una sesión de refuerzo sobre los temas del parcial 2."),
    "quiz1": ("quiz 1 con {v:.1f}", "Proponer ejercicios cortos de práctica semanal."),
    "quiz2": ("quiz 2 con {v:.1f}", "Proponer ejercicios cortos de práctica semanal."),
    "taller1": ("taller 1 con {v:.1f}", "Verificar si entendió el enunciado de los talleres."),
    "taller2": ("taller 2 con {v:.1f}", "Verificar si entendió el enunciado de los talleres."),
    "nota_minima_requerida": ("necesita {v:.1f} en promedio en lo que resta para aprobar",
                              "Acordar un plan de estudio con metas semanales y revisarlo cada 15 días."),
    "tendencia_notas": ("cambio de {v:+.1f} entre el corte 1 y el corte 2",
                        "Conversar sobre qué cambió desde el inicio del semestre."),
    "inasistencias_c1": ("{v:.0f} inasistencias en el corte 1", "Contactar al estudiante para conocer la causa de las ausencias."),
    "inasistencias_c2": ("{v:.0f} inasistencias en el corte 2", "Contactar al estudiante para conocer la causa de las ausencias."),
    "inasistencias_total": ("{v:.0f} inasistencias en el semestre", "Contactar al estudiante para conocer la causa de las ausencias."),
    "accesos_lms_c1": ("{v:.0f} ingresos a la plataforma en el corte 1", "Confirmar que tiene acceso a la plataforma y al material."),
    "accesos_lms_c2": ("{v:.0f} ingresos a la plataforma en el corte 2", "Confirmar que tiene acceso a la plataforma y al material."),
    "cambio_accesos_lms": ("cambio de {v:+.0f} ingresos a la plataforma", "Preguntar si hay alguna dificultad nueva (tiempo, conexión, trabajo)."),
    "entregas_tarde_c1": ("{v:.0f} entregas tardías en el corte 1", "Ayudar a organizar un calendario de entregas."),
    "entregas_tarde_c2": ("{v:.0f} entregas tardías en el corte 2", "Ayudar a organizar un calendario de entregas."),
    "promedio_acumulado": ("promedio acumulado de {v:.2f}", "Remitir a bienestar / consejería académica."),
    "materias_perdidas_previas": ("{v:.0f} materias perdidas anteriormente", "Remitir a consejería académica para revisar la carga."),
    "puntaje_saber11": ("puntaje Saber 11 de {v:.0f}", "Sugerir cursos de nivelación o monitorías."),
    "trabaja": ("trabaja mientras estudia", "Considerar horarios flexibles de tutoría."),
}


def cargar_modelo(momento):
    return joblib.load(MODELS_DIR / f"{momento}.joblib")


def nivel(prob):
    return NIVELES[int(prob >= UMBRAL_MEDIA) + int(prob >= UMBRAL_ALTA)]


def puntuar(df, paquete):
    """Agrega probabilidad y nivel de acompañamiento a cada fila de `df`."""
    X = construir_features(df, paquete["momento"])
    salida = df.copy()
    salida["probabilidad"] = paquete["modelo"].predict_proba(X)[:, 1]
    salida["prioridad"] = salida["probabilidad"].map(nivel)
    return salida


def factores(paquete, fila_df, top=4):
    """Variables que más empujan la probabilidad hacia arriba para UNA fila."""
    X = construir_features(fila_df, paquete["momento"]).reset_index(drop=True)
    variantes = pd.concat([X] * (len(X.columns) + 1), ignore_index=True)
    variantes = variantes.apply(lambda s: s if s.dtype == object else s.astype(float))
    for i, col in enumerate(X.columns, start=1):
        variantes.loc[i, col] = paquete["referencia"][col]
    probs = np.clip(paquete["modelo"].predict_proba(variantes)[:, 1], 1e-6, 1 - 1e-6)
    logit = np.log(probs / (1 - probs))  # en escala logit para que funcione aun con probabilidades cercanas a 1
    aportes = logit[0] - logit[1:]
    orden = np.argsort(-aportes)
    return [(X.columns[i], X.iloc[0][X.columns[i]], float(aportes[i])) for i in orden[:top] if aportes[i] > 0.05]


def mensaje_docente(fila, prob, lista_factores):
    """Mensaje en lenguaje natural basado en plantillas.
    Punto de extensión: aquí se puede conectar un LLM que reciba estos mismos
    datos estructurados y redacte el texto, sin tocar el modelo predictivo."""
    prioridad = nivel(prob)
    if prioridad == "Baja" or not lista_factores:
        return (f"Prioridad de acompañamiento {prioridad.lower()} en {fila['asignatura']}. "
                "No se observan señales que requieran acción por ahora.")
    senales, acciones = [], []
    for var, valor, _ in lista_factores:
        desc, accion = SENALES.get(var, (var.replace("_", " ") + ": {v}", None))
        if var == "nota_minima_requerida" and valor > 5:
            desc = "necesitaría {v:.1f} en lo que resta: ya no es alcanzable en la escala 0-5"
            accion = "Remitir a consejería académica para evaluar opciones (cancelación, plan para repetir)."
        senales.append(desc.format(v=valor) if isinstance(valor, (int, float, np.number)) else f"{var}: {valor}")
        if accion and accion not in acciones:
            acciones.append(accion)
    texto = (f"Prioridad de acompañamiento {prioridad.upper()} en {fila['asignatura']} "
             f"(probabilidad estimada de no aprobar: {prob:.0%}).\n"
             f"Señales principales: {'; '.join(senales)}.")
    if acciones:
        texto += "\nAcciones sugeridas:\n" + "\n".join(f"  - {a}" for a in acciones)
    return texto
