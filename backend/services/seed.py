"""Carga inicial: crea tablas, docentes, inscripciones y alertas de ejemplo.

Uso:
    python src/generar_datos_sinteticos.py
    python -m backend.services.seed

Solo para desarrollo/demo. La contraseña inicial se puede cambiar con la variable
EWS_SEED_PASSWORD y debe cambiarse desde la interfaz antes de usar en producción.
"""
import os

import numpy as np
import pandas as pd
from sqlalchemy import select

from config import DATA_PATH, ID_COL, MOMENTOS
from database import Base, SessionLocal, engine
from generar_datos_sinteticos import DOCENTES
from models_db import Docente, Inscripcion
from security import hash_password
from services.scoring import generar_alertas

# Solo columnas académicas necesarias para el modelo. Se excluye `genero`.
COLUMNAS_DATOS = list(dict.fromkeys(MOMENTOS["T2_corte2"] + [ID_COL]))


def _limpio(valor):
    if isinstance(valor, np.generic):
        valor = valor.item()
    if isinstance(valor, float) and np.isnan(valor):
        return None
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return None if pd.isna(valor) else valor


def ejecutar(sobrescribir_claves: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        docentes_por_codigo: dict[str, Docente] = {}
        for info in DOCENTES.values():
            docente = db.execute(select(Docente).where(Docente.codigo == info["codigo"])).scalar_one_or_none()
            if docente is None:
                docente = Docente(
                    codigo=info["codigo"], nombre=info["nombre"], email=info["email"],
                    password_hash=hash_password(os.getenv("EWS_SEED_PASSWORD", "ClaveSegura123!")),
                    activo=True,
                )
                db.add(docente)
                db.flush()
            elif sobrescribir_claves:
                docente.password_hash = hash_password(
                    os.getenv("EWS_SEED_PASSWORD", "ClaveSegura123!")
                )
            docentes_por_codigo[info["codigo"]] = docente
        db.commit()

        if not DATA_PATH.exists():
            raise FileNotFoundError(f"No existe {DATA_PATH}. Ejecuta primero src/generar_datos_sinteticos.py")

        df = pd.read_csv(DATA_PATH)
        requeridas = set(COLUMNAS_DATOS + ["docente_id", "curso", "asignatura"])
        faltantes = requeridas - set(df.columns)
        if faltantes:
            raise ValueError(f"Faltan columnas en el CSV: {sorted(faltantes)}")

        total = 0
        for _, fila in df.iterrows():
            docente = docentes_por_codigo.get(fila["docente_id"])
            if docente is None:
                continue
            existente = db.execute(
                select(Inscripcion).where(
                    Inscripcion.estudiante_id == fila[ID_COL],
                    Inscripcion.asignatura == fila["asignatura"],
                    Inscripcion.curso == fila["curso"],
                )
            ).scalar_one_or_none()
            if existente is not None:
                continue
            datos = {columna: _limpio(fila[columna]) for columna in COLUMNAS_DATOS if columna in fila}
            db.add(Inscripcion(
                estudiante_id=str(fila[ID_COL]),
                docente_id=docente.id,
                asignatura=str(fila["asignatura"]),
                curso=str(fila["curso"]),
                datos=datos,
            ))
            total += 1
        db.commit()

        resumen = []
        for docente in docentes_por_codigo.values():
            resumen.append(generar_alertas(db, docente, list(MOMENTOS)))

        print(f"Docentes: {len(docentes_por_codigo)} | inscripciones nuevas: {total}")
        for item in resumen:
            print(f"  Alertas activas generadas: {item['alertas_activas']} en {item['inscripciones']} inscripciones")
        print("\nUsuarios de ejemplo (contraseña inicial: ClaveSegura123!):")
        for info in DOCENTES.values():
            print(f"  {info['email']}  ->  {info['nombre']}")
    finally:
        db.close()


if __name__ == "__main__":
    ejecutar(sobrescribir_claves=os.getenv("EWS_SEED_RESET", "0") == "1")
