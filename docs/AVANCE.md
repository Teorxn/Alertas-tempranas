# Avance del proyecto - Sistema de Alertas Tempranas para pérdida de asignaturas

## 1. Problema y alcance

**Problema.** Los docentes se enteran de que un estudiante va a perder una asignatura cuando ya
es tarde (después del corte 2 o en el examen final). Se necesita identificar el riesgo **mientras
aún hay tiempo para intervenir**.

**Ajuste de alcance frente a la revisión de literatura.** La mayoría de las fuentes revisadas
predicen *deserción universitaria* (abandono de la carrera). Nuestro problema es más acotado y
concreto: **predecir la pérdida de una asignatura** (nota definitiva < 3.0) a partir de las
calificaciones parciales. Esto cambia el diseño:

| | Deserción (literatura) | Pérdida de asignatura (nuestro caso) |
|---|---|---|
| Unidad de análisis | Estudiante | Estudiante × asignatura |
| Variable objetivo | ¿Abandona la carrera? | ¿Nota definitiva < 3.0? |
| Horizonte | Semestres / años | Un semestre |
| Señal principal | Socioeconómica + académica | Notas parciales + asistencia |
| Acción | Bienestar universitario | Plan de estudio del docente |

**Pregunta de investigación.** ¿Con qué anticipación y con qué confiabilidad se puede predecir
que un estudiante perderá una asignatura usando las calificaciones disponibles durante el
semestre, y cuál modelo ofrece el mejor equilibrio entre detección, falsas alarmas e
interpretabilidad para el docente?

**Objetivo general.** Desarrollar un sistema de alerta temprana que estime la probabilidad de
pérdida de asignatura en distintos momentos del semestre y entregue al docente una explicación
y acciones sugeridas.

**Objetivos específicos.**
1. Caracterizar el dataset y definir qué variables están disponibles en cada momento del semestre.
2. Comparar modelos de clasificación (regresión logística, árbol de decisión, Random Forest,
   Gradient Boosting) contra una línea base de reglas docentes.
3. Determinar el momento más temprano en que la predicción es útil (curva anticipación vs. precisión).
4. Diseñar e implementar un prototipo con semáforo, explicación individual y mensaje al docente.
5. Evaluar la equidad del modelo entre grupos de estudiantes.

## 2. Metodología: CRISP-DM

| Fase | Contenido | Estado |
|---|---|---|
| 1. Comprensión del problema | Revisión de literatura y patentes (Google Scholar / Patents), definición del objetivo | ✅ Hecho |
| 2. Comprensión de los datos | Exploración del dataset del profesor | ⏳ Pendiente (a la espera del dataset) |
| 3. Preparación | Variables por momento, variables derivadas, manejo de faltantes | ✅ Pipeline listo (probado con datos sintéticos) |
| 4. Modelado | 4 modelos + línea base, validación cruzada por estudiante | ✅ Prototipo funcionando |
| 5. Evaluación | Recall, PR-AUC, F2, matriz de confusión, equidad | ✅ Prototipo / ⏳ con datos reales |
| 6. Despliegue | Dashboard docente con semáforo y explicaciones | ✅ Prototipo local |

## 3. Decisión clave: qué significa "temprano"

El modelo **solo puede usar lo que el profesor ya conoce** en el momento de la predicción. Si se
entrena con la nota del corte 3 o la definitiva, el modelo "acierta" en el laboratorio pero no
sirve en la vida real (fuga de información o *data leakage*). Por eso se entrena **un modelo por
momento**:

| Momento | Cuándo | Información disponible |
|---|---|---|
| T0 | Semana 1 | Historial: promedio acumulado, materias perdidas, Saber 11, datos de ingreso |
| T1 | Fin del corte 1 (~semana 5) | T0 + notas del corte 1, inasistencias, actividad en plataforma |
| T2 | Fin del corte 2 (~semana 10) | T1 + notas del corte 2 (todavía queda el 40%) |

Variable derivada importante: **nota mínima requerida** = nota promedio que necesita el
estudiante en lo que resta para llegar a 3.0. Si es mayor a 5.0, aprobar ya no es posible: eso
muestra por qué la alerta en T1 vale más que en T2.

## 4. Modelos considerados

| Modelo | Por qué se incluye | Limitación |
|---|---|---|
| Regla docente (línea base) | Representa lo que el profesor hace "a ojo" (p. ej. corte 1 < 3.0). **Si el modelo no la supera, no se justifica.** | No combina señales |
| Regresión logística | Interpretable, robusta con pocos datos | Relaciones solo lineales |
| Árbol de decisión | Reglas legibles para el docente | Inestable, sobreajusta |
| Random Forest | Muy usado en la literatura (Zhao & Ren; JUTIF 2026) | Menos interpretable |
| Gradient Boosting (equivalente a XGBoost/LightGBM) | Mejor desempeño en datos tabulares según la literatura (Balas 2025; Carballo-Mendívil 2025) | Requiere ajuste de hiperparámetros |

**Descartados por ahora (y por qué):** LSTM/GRU y KoBERT+MLP necesitan datos secuenciales
de plataforma o texto libre que probablemente no tenga el dataset, además de GPU; no se
justifican con datos tabulares de notas.

**Desbalance de clases:** se usa `class_weight="balanced"` y se ajusta el umbral de decisión.
SMOTE/ADASYN quedan como experimento de la fase 2.

## 5. Métricas de evaluación

- **No se usa accuracy como métrica principal**: si pierde el 25%, un modelo que dice "todos
  aprueban" tiene 75% de accuracy y no sirve.
- **Recall (sensibilidad)**: de los que perdieron, ¿a cuántos detectamos? Es la prioridad.
- **Precisión / % de alertados**: si se alerta al 70% del curso, el docente no puede actuar.
- **PR-AUC**: calidad del ranking de riesgo, independiente del umbral; se usa para elegir modelo.
- **F2**: combina recall y precisión dando más peso al recall; se usa para elegir el umbral.
- **Validación**: partición 80/20 **por estudiante** (el mismo estudiante no queda en
  entrenamiento y prueba) + validación cruzada de 5 particiones estratificada por grupos.

## 6. Arquitectura propuesta

**Idea central: no es un agente, es un pipeline de ML por capas.** La predicción la hace un
modelo clásico (reproducible y medible). Un LLM, si se usa, va **solo al final** para redactar
el mensaje al docente, y es reemplazable por plantillas. Además, como las notas cambian por
corte y no cada segundo, el sistema funciona **por lotes (batch)**: se ejecuta 3 veces por
semestre. No se necesita tiempo real, colas de mensajes ni infraestructura compleja.

```
[CSV / Excel del profesor]
        │
        ▼
1. Ingesta y validación ──── revisa columnas, rangos 0-5, faltantes
        │
        ▼
2. Variables por momento ─── T0 / T1 / T2, sin fuga de información
        │
        ▼
3. Modelo predictivo ─────── entrenado offline, versionado (.joblib)
        │
        ▼
4. Semáforo + explicación ── prioridad Alta/Media/Baja + señales que más pesan
        │
        ▼
5. Mensaje al docente ────── plantillas (hoy) │ LLM opcional (fase 3)
        │
        ▼
6. Dashboard docente ─────── Streamlit (hoy) │ web + API (fase 2)
```

**Plan de migración por fases** (para que pasar a una arquitectura formal no sea un salto al vacío):

| Fase | Componentes | Complejidad |
|---|---|---|
| 1 - Prototipo (actual) | Scripts Python + Streamlit local, archivos CSV | Baja |
| 2 - Servicio | API REST (FastAPI) con `/predecir`, base de datos (PostgreSQL/SQLite), modelo versionado, SHAP | Media |
| 3 - Integración | Conexión con LMS/sistema de notas, LLM para narrativas, notificaciones, control de fatiga de alertas | Alta |

Cada capa es un módulo independiente (`features.py`, `entrenar.py`, `explicar.py`,
`dashboard.py`), así que pasar de la fase 1 a la 2 es envolver las mismas funciones en una API,
no reescribir.

## 7. Resultados preliminares (DATOS SINTÉTICOS)

> ⚠️ Estos números provienen de datos inventados para probar el pipeline. **No son resultados de
> la investigación**; con datos reales el desempeño será menor. Sirven para demostrar que el
> pipeline completo funciona.

Dataset sintético: 700 estudiantes, 2 800 inscripciones, 27.4% de pérdida. Conjunto de prueba:
560 inscripciones de estudiantes que el modelo nunca vio.

| Momento | Mejor modelo | Recall | Precisión | PR-AUC | % alertado | Línea base (recall / PR-AUC) |
|---|---|---|---|---|---|---|
| T0 inicio | Regresión logística | 0.96 | 0.41 | 0.76 | 66% | 0.76 / 0.45 |
| T1 corte 1 | Regresión logística | 0.94 | 0.68 | 0.91 | 40% | 0.79 / 0.71 |
| T2 corte 2 | Random Forest | 0.92 | 0.78 | 0.96 | 33% | 0.86 / 0.77 |

Lectura de los resultados del prototipo:
- En **T0** el modelo detecta a casi todos, pero alertaría a 2 de cada 3 estudiantes: no es
  accionable. El historial solo no basta.
- **T1 es el punto óptimo**: detecta 94% de los que pierden, con suficiente tiempo para intervenir
  (queda el 70% de la nota). Supera claramente la regla "corte 1 < 3.0" (79% de detección).
- En **T2** la precisión mejora, pero a varios estudiantes ya no les alcanza la nota.
- La regresión logística gana en los datos sintéticos porque se generaron con relaciones casi
  lineales; con datos reales se espera que los modelos de árboles compitan mejor.

Figuras generadas en `reports/figuras/` (comparación de modelos, importancia de variables,
matrices de confusión) y auditoría de equidad en `reports/equidad.csv`.

## 8. Ética y gobernanza

- **Lenguaje no estigmatizante:** el sistema muestra "prioridad de acompañamiento", nunca
  "estudiante en riesgo".
- **Variables sensibles fuera del modelo:** el género no se usa para predecir; solo para auditar
  que el modelo detecte igual en todos los grupos (recall y falsas alarmas por grupo).
- **Seudonimización:** se trabaja con identificadores, no con nombres ni documentos.
- **El modelo sugiere, el docente decide:** la alerta es un apoyo, no una decisión automática.

## 9. Lo que necesitamos saber del dataset (preguntas para el profesor)

1. ¿Qué columnas trae? ¿Notas por actividad, por corte o solo definitiva?
2. ¿Cuál es la escala (0-5) y la nota aprobatoria? ¿Cuáles son los pesos de los cortes?
3. ¿Cuántos estudiantes, asignaturas y semestres? ¿Qué porcentaje pierde?
4. ¿Incluye asistencia, actividad en plataforma (Moodle/Teams) o datos socioeconómicos?
5. ¿Hay fechas? (para simular el momento de cada alerta)
6. ¿Los datos están anonimizados? ¿Hay restricciones de uso?
7. ¿La alerta es para el docente de la asignatura, para un tutor o para bienestar?

## 10. Próximos pasos

| Semana | Actividad |
|---|---|
| 1 | Recibir el dataset, análisis exploratorio, adaptar `config.py` |
| 2 | Entrenar con datos reales, comparar contra la línea base |
| 3 | Agregar XGBoost/LightGBM + SHAP, probar SMOTE, ajuste de hiperparámetros |
| 4 | Auditoría de equidad, validación con un docente (¿le sirven los mensajes?) |
| 5 | Fase 2 de arquitectura: API REST + base de datos |
| 6 | Informe final y artículo |

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| El dataset no tiene notas parciales (solo definitivas) | Predecir con historial de semestres anteriores (modelo T0 por semestre) |
| Pocos datos | Modelos simples (logística, árbol), validación cruzada, intervalos de confianza |
| Desbalance fuerte | Pesos por clase, ajuste de umbral, SMOTE |
| Fuga de información | Variables definidas por momento en `config.py` |
| Docentes no confían en la alerta | Explicación por estudiante + acciones concretas + validación con docentes |
