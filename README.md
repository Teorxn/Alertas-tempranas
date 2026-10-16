# Sistema de Alertas Tempranas (EWS) - Pérdida de asignaturas

Prototipo que estima, **en distintos momentos del semestre**, qué estudiantes tienen alta
probabilidad de perder una asignatura, explica por qué y sugiere acciones al docente.

> Los datos actuales son **sintéticos** (inventados) y solo sirven para probar el pipeline.
> Cuando llegue el dataset del profesor se reemplazan sin cambiar el código (ver abajo).

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
```

```bash
python src/generar_datos_sinteticos.py
```

```bash
python src/entrenar.py
```

```bash
streamlit run app/dashboard.py
```

## Estructura

```
Alertas tempranas/
├── src/
│   ├── config.py                    # ÚNICO archivo a editar con el dataset real
│   ├── generar_datos_sinteticos.py  # datos de prueba (escala 0-5, cortes 30/30/40)
│   ├── features.py                  # variables por momento del semestre (sin fuga)
│   ├── entrenar.py                  # compara modelos, elige el mejor, genera reportes
│   └── explicar.py                  # semáforo, explicación individual, mensaje al docente
├── app/dashboard.py                 # dashboard docente (Streamlit)
├── data/synthetic/                  # dataset sintético
├── data/raw/                        # aquí va el dataset del profesor
├── models/                          # modelos entrenados (.joblib)
├── reports/                         # métricas, equidad, figuras
└── docs/AVANCE.md                   # documento de avance del proyecto
```

## Usar el dataset real

1. Copiar el archivo a `data/raw/`.
2. En `src/config.py`: cambiar `DATA_PATH`, los nombres de columnas, `PESOS_CORTES` y las
   listas `FEATURES_*` según lo que traiga el dataset.
3. Si las columnas no se llaman igual, renombrarlas o ajustar `features.py`.
4. Correr `src/entrenar.py` y luego el dashboard.
