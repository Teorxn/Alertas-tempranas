"""Genera un dataset SINTÃ‰TICO para probar el pipeline mientras llega el real.

Imita una universidad colombiana: escala 0-5, tres cortes (30/30/40) y
estudiantes inscritos en varias asignaturas. Los datos son inventados; solo
sirven para verificar que el pipeline funciona de punta a punta.
"""
import numpy as np
import pandas as pd

from config import DATA_PATH, NOTA_APROBATORIA, PESOS_CORTES, SEMILLA

ASIGNATURAS = {  # dificultad relativa
    "Calculo I": 0.45, "Fisica I": 0.40, "Algebra Lineal": 0.30,
    "Programacion I": 0.25, "Estadistica": 0.20, "Comunicacion Oral": -0.20,
}


def _sigmoide(x):
    return 1 / (1 + np.exp(-x))


def _nota(rng, media, ruido):
    return float(np.clip(media + rng.normal(0, ruido), 0, 5).round(1))


def generar(n_estudiantes=700, materias_por_estudiante=4, semilla=SEMILLA):
    rng = np.random.default_rng(semilla)
    n = n_estudiantes
    habilidad = rng.normal(0, 1, n)
    compromiso = rng.normal(0, 1, n)

    edad = np.clip(np.round(17 + rng.gamma(2.0, 1.6, n)), 16, 40).astype(int)
    trabaja = rng.random(n) < _sigmoide(-1.4 + 0.3 * (edad - 20))
    jornada = np.where(trabaja & (rng.random(n) < 0.6), "nocturna", "diurna")
    estrato = np.clip(np.round(rng.normal(2.7 + 0.3 * habilidad, 1.0)), 1, 6).astype(int)
    tipo_colegio = np.where(rng.random(n) < _sigmoide(-1 + 0.6 * (estrato - 3)), "privado", "publico")
    saber11 = np.clip(np.round(280 + 45 * habilidad + 8 * (estrato - 3) + rng.normal(0, 25, n)), 150, 480)
    semestre = rng.integers(1, 9, n)
    promedio = np.clip(3.5 + 0.45 * habilidad + 0.2 * compromiso + rng.normal(0, 0.25, n), 1.5, 5).round(2)
    promedio = np.where(semestre == 1, np.nan, promedio)  # primÃ­paros no tienen promedio
    lam_perdidas = (semestre - 1) * 0.35 * np.exp(-0.8 * habilidad - 0.4 * compromiso)
    perdidas_previas = rng.poisson(np.minimum(lam_perdidas, 4))
    beca = rng.random(n) < (0.12 + 0.15 * (habilidad > 1))
    genero = rng.choice(["F", "M"], n)

    filas = []
    for i in range(n):
        for asig in rng.choice(list(ASIGNATURAS), materias_por_estudiante, replace=False):
            dif = ASIGNATURAS[asig]
            base = 3.72 + 0.55 * habilidad[i] + 0.3 * compromiso[i] - 0.6 * dif + rng.normal(0, 0.35)
            # Algunos estudiantes pierden el ritmo a mitad de semestre
            caida = rng.normal(0, 0.5) - 0.5 * trabaja[i] * (rng.random() < 0.5)
            fila = {
                "estudiante_id": f"E{i:04d}", "asignatura": asig, "edad": edad[i],
                "genero": genero[i], "estrato": estrato[i], "tipo_colegio": tipo_colegio[i],
                "trabaja": int(trabaja[i]), "jornada": jornada[i], "semestre": semestre[i],
                "puntaje_saber11": int(saber11[i]), "promedio_acumulado": promedio[i],
                "materias_perdidas_previas": perdidas_previas[i], "beca": int(beca[i]),
            }
            notas_cortes = []
            for c, comp in ((1, compromiso[i]), (2, compromiso[i] + caida)):
                inas = rng.poisson(max(0.2, 1.5 - 0.8 * comp + 0.8 * trabaja[i]))
                media = base + (0.25 * caida - 0.15 * dif if c == 2 else 0) - 0.08 * inas
                quiz, taller, parcial = _nota(rng, media + 0.2, 0.5), _nota(rng, media + 0.3, 0.45), _nota(rng, media - 0.2, 0.5)
                nota_c = round(0.3 * quiz + 0.3 * taller + 0.4 * parcial, 2)
                notas_cortes.append(nota_c)
                fila.update({
                    f"quiz{c}": quiz, f"taller{c}": taller, f"parcial{c}": parcial,
                    f"nota_corte{c}": nota_c, f"inasistencias_c{c}": inas,
                    f"accesos_lms_c{c}": rng.poisson(max(1, 25 + 8 * comp)),
                    f"entregas_tarde_c{c}": rng.poisson(max(0.1, 0.8 - 0.5 * comp + 0.4 * trabaja[i])),
                })
            nota_c3 = _nota(rng, base + 0.35 * caida - 0.2 * dif, 0.45)
            definitiva = round(sum(p * nc for p, nc in zip(PESOS_CORTES, notas_cortes + [nota_c3])), 2)
            fila.update({"nota_corte3": nota_c3, "nota_definitiva": definitiva,
                         "pierde": int(definitiva < NOTA_APROBATORIA)})
            filas.append(fila)
    return pd.DataFrame(filas)


if __name__ == "__main__":
    df = generar()
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    print(f"Dataset sintÃ©tico: {len(df)} filas, {df['estudiante_id'].nunique()} estudiantes")
    print(f"Tasa de pÃ©rdida: {df['pierde'].mean():.1%}")
    print(df.groupby("asignatura")["pierde"].mean().round(3).to_string())
