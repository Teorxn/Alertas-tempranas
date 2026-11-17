"""Construcción de variables por momento del semestre (sin fuga de información)."""
import pandas as pd

from config import CATEGORICAS, MOMENTOS, NOTA_APROBATORIA, PESOS_CORTES


def construir_features(df: pd.DataFrame, momento: str) -> pd.DataFrame:
    """Devuelve solo las columnas que el profesor conoce en `momento`,
    más variables derivadas calculadas con esa misma información."""
    X = df[MOMENTOS[momento]].copy()
    p1, p2, p3 = PESOS_CORTES

    if momento == "T1_corte1":
        # Nota promedio que necesita en el 70% restante para aprobar
        X["nota_minima_requerida"] = (NOTA_APROBATORIA - p1 * X["nota_corte1"]) / (p2 + p3)
    elif momento == "T2_corte2":
        X["nota_minima_requerida"] = (NOTA_APROBATORIA - p1 * X["nota_corte1"] - p2 * X["nota_corte2"]) / p3
        X["tendencia_notas"] = X["nota_corte2"] - X["nota_corte1"]
        X["inasistencias_total"] = X["inasistencias_c1"] + X["inasistencias_c2"]
        X["cambio_accesos_lms"] = X["accesos_lms_c2"] - X["accesos_lms_c1"]
    return X


def tipos_columnas(X: pd.DataFrame):
    categoricas = [c for c in X.columns if c in CATEGORICAS]
    numericas = [c for c in X.columns if c not in categoricas]
    return numericas, categoricas
