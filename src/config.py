"""Configuración central del sistema de alertas tempranas.

Cuando llegue el dataset del profesor, este es el ÚNICO archivo que debería
cambiar: rutas, nombres de columnas, pesos de los cortes y qué variables están
disponibles en cada momento del semestre.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "synthetic" / "estudiantes_sinteticos.csv"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figuras"

# --- Reglas académicas (escala colombiana 0.0 - 5.0) ---
NOTA_APROBATORIA = 3.0
PESOS_CORTES = (0.30, 0.30, 0.40)  # corte 1, corte 2, corte 3

# --- Columnas clave ---
ID_COL = "estudiante_id"
TARGET = "pierde"  # 1 si la nota definitiva < NOTA_APROBATORIA
SEMILLA = 42

# Variables sensibles: NO entran al modelo, solo se usan para auditar equidad.
VARIABLES_SENSIBLES = ["genero"]

# --- Variables disponibles en cada momento (evita fuga de información) ---
# Regla de oro: en el momento T solo se usa lo que el profesor YA conoce en T.
# Nunca se usan la nota del corte 3 ni la definitiva como entrada.
FEATURES_BASE = [
    "asignatura", "edad", "estrato", "tipo_colegio", "trabaja", "jornada",
    "semestre", "puntaje_saber11", "promedio_acumulado",
    "materias_perdidas_previas", "beca",
]
FEATURES_CORTE1 = [
    "quiz1", "taller1", "parcial1", "nota_corte1",
    "inasistencias_c1", "accesos_lms_c1", "entregas_tarde_c1",
]
FEATURES_CORTE2 = [
    "quiz2", "taller2", "parcial2", "nota_corte2",
    "inasistencias_c2", "accesos_lms_c2", "entregas_tarde_c2",
]

MOMENTOS = {
    "T0_inicio": FEATURES_BASE,
    "T1_corte1": FEATURES_BASE + FEATURES_CORTE1,
    "T2_corte2": FEATURES_BASE + FEATURES_CORTE1 + FEATURES_CORTE2,
}
DESCRIPCION_MOMENTOS = {
    "T0_inicio": "Semana 1 - solo historial y datos de ingreso",
    "T1_corte1": "Fin del corte 1 (~semana 5) - primeras notas",
    "T2_corte2": "Fin del corte 2 (~semana 10) - aún queda el 40%",
}

CATEGORICAS = ["asignatura", "tipo_colegio", "jornada"]

# --- Semáforo de acompañamiento (probabilidad de perder) ---
UMBRAL_ALTA = 0.60
UMBRAL_MEDIA = 0.30
