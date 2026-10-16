"""Dashboard docente del sistema de alertas tempranas (prototipo).

Ejecutar desde la carpeta del proyecto:
    streamlit run app/dashboard.py
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import DATA_PATH, DESCRIPCION_MOMENTOS, FIGURES_DIR, MODELS_DIR, MOMENTOS, REPORTS_DIR  # noqa: E402
from explicar import cargar_modelo, factores, mensaje_docente, puntuar  # noqa: E402

COLORES = {"Alta": "#f8d7da", "Media": "#fff3cd", "Baja": "#d1e7dd"}

st.set_page_config(page_title="Alertas tempranas", page_icon="🚦", layout="wide")
st.title("🚦 Sistema de Alertas Tempranas - Acompañamiento académico")

with st.sidebar:
    momento = st.radio("Momento del semestre", list(MOMENTOS), format_func=lambda m: f"{m}")
    st.caption(DESCRIPCION_MOMENTOS[momento])
    archivo = st.file_uploader("Cargar CSV del curso (mismas columnas)", type="csv")
    st.info("Sin archivo se usan los estudiantes de PRUEBA del dataset sintético "
            "(el modelo nunca los vio durante el entrenamiento).")

paquete = cargar_modelo(momento)
if archivo is not None:
    df = pd.read_csv(archivo)
else:
    df = pd.read_csv(DATA_PATH)
    ids = pd.read_csv(MODELS_DIR / "ids_prueba.csv")["estudiante_id"]
    df = df[df["estudiante_id"].isin(ids)].reset_index(drop=True)

res = puntuar(df, paquete)
tab_alertas, tab_modelo = st.tabs(["Alertas del curso", "Desempeño del modelo"])

with tab_alertas:
    asignaturas = ["Todas"] + sorted(res["asignatura"].unique())
    filtro = st.selectbox("Asignatura", asignaturas)
    vista = res if filtro == "Todas" else res[res["asignatura"] == filtro]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Inscripciones", len(vista))
    for col, nivel in zip((c2, c3, c4), ("Alta", "Media", "Baja")):
        col.metric(f"Prioridad {nivel}", int((vista["prioridad"] == nivel).sum()))
    st.caption(f"Modelo: **{paquete['nombre']}** · {DESCRIPCION_MOMENTOS[momento]}")

    columnas = ["estudiante_id", "asignatura", "prioridad", "probabilidad", "promedio_acumulado"]
    columnas += [c for c in ("nota_corte1", "nota_corte2", "inasistencias_c1") if c in paquete["features"]]
    if "pierde" in vista.columns:  # solo existe en datos históricos: sirve para validar la demo
        columnas.append("pierde")
    tabla = vista.sort_values("probabilidad", ascending=False)[columnas]
    st.dataframe(
        tabla.style.apply(lambda f: [f"background-color: {COLORES[f['prioridad']]}; color: #1a1a1a"] * len(f), axis=1)
        .format({"probabilidad": "{:.0%}", "promedio_acumulado": "{:.2f}"}),
        use_container_width=True, height=380, hide_index=True,
    )

    st.subheader("Ficha individual")
    opciones = tabla.index.tolist()
    elegido = st.selectbox("Seleccione una inscripción", opciones,
                           format_func=lambda i: f"{res.loc[i, 'estudiante_id']} - {res.loc[i, 'asignatura']} "
                                                 f"({res.loc[i, 'prioridad']})")
    fila = res.loc[[elegido]]
    lista = factores(paquete, fila.drop(columns=["probabilidad", "prioridad"]))
    izq, der = st.columns([1, 1])
    with izq:
        st.markdown("**Mensaje para el docente**")
        st.text(mensaje_docente(fila.iloc[0], fila["probabilidad"].iloc[0], lista))
    with der:
        if lista:
            st.markdown("**Peso de cada señal en la alerta** (escala logit)")
            st.bar_chart(pd.Series({v: a for v, _, a in lista}, name="aporte"), horizontal=True)
        if "nota_definitiva" in fila.columns:
            st.caption(f"Validación de la demo — nota definitiva real: {fila['nota_definitiva'].iloc[0]:.2f}")

with tab_modelo:
    resumen = json.loads((REPORTS_DIR / "resumen.json").read_text(encoding="utf-8"))
    st.markdown("**Mejor modelo por momento (conjunto de prueba)**")
    st.dataframe(pd.DataFrame(resumen).T, use_container_width=True)
    st.image(str(FIGURES_DIR / "comparacion_modelos.png"))
    a, b = st.columns(2)
    a.image(str(FIGURES_DIR / f"importancia_{momento}.png"))
    b.image(str(FIGURES_DIR / f"confusion_{momento}.png"))
    st.markdown("**Auditoría de equidad** (recall y falsas alarmas por grupo)")
    equidad = pd.read_csv(REPORTS_DIR / "equidad.csv")
    st.dataframe(equidad[equidad["momento"] == momento], use_container_width=True, hide_index=True)
