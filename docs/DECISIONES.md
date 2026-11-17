# Decisiones del proyecto

Registro ligero de las decisiones que cambiaron el rumbo. Complementa
[ESTADO.md](ESTADO.md) y [AVANCE.md](AVANCE.md). Formato: contexto, decisión, razón.

---

## 2026-10-01 · Pérdida de asignatura, no deserción

**Contexto.** La literatura revisada predice abandono de la carrera en horizontes de
semestres o años. El profesor necesita actuar dentro del semestre.

**Decisión.** Predecir nota definitiva < 3.0 en una asignatura, con el estudiante-asignatura
como unidad de análisis.

**Razón.** Es el problema que el docente puede intervenir: quedan semanas y tiene el plan de
estudio de su curso. La deserción es competencia de bienestar universitario.

## 2026-10-05 · Tres momentos, variables sin fuga

**Contexto.** El riesgo cambia según la información disponible. Usar notas futuras daría
resultados engañosos.

**Decisión.** Definir T0 (solo historial), T1 (corte 1) y T2 (corte 2), con listas explícitas
de variables por momento en `src/config.py`.

**Razón.** Permite responder la pregunta de investigación sobre anticipación vs. confiabilidad
y evita fuga de información. Consecuencia: tres modelos, no uno.

## 2026-10-08 · Cinco estrategias y una línea base obligatoria

**Contexto.** Existían alternativas de deep learning, pero el dataset probablemente será
tabular y pequeño.

**Decisión.** Comparar regla docente, regresión logística, árbol, Random Forest y Gradient
Boosting. Descartar LSTM/GRU y KoBERT+MLP por ahora.

**Razón.** Si el modelo no supera la regla «corte 1 < 3.0», no se justifica. Los modelos
secuenciales exigen datos de plataforma o texto libre y GPU, de los que hoy no se dispone.

## 2026-10-10 · PR-AUC para elegir, F2 para el umbral, recall como prioridad

**Contexto.** Con 27% de pérdida, el accuracy es engañoso; alertar demasiados estudiantes no
es accionable.

**Decisión.** Seleccionar modelo por PR-AUC en validación cruzada; fijar umbral por F2;
reportar recall, precisión y % alertado.

**Razón.** Faltar un estudiante que pierde es más costoso que una falsa alarma, pero alertar
al 70% del curso satura al docente.

## 2026-10-12 · Validación agrupada por estudiante

**Contexto.** Cada estudiante aporta varias inscripciones; una partición aleatoria filtraría
información del mismo estudiante entre entrenamiento y prueba.

**Decisión.** `GroupShuffleSplit` 80/20 por estudiante y `StratifiedGroupKFold(5)`.

**Razón.** Evita optimismo indebido. Los identificadores de prueba quedan en
`docs/evidencias/ids_prueba.csv`.

## 2026-11-03 · Reutilizar los modelos en la API

**Contexto.** El módulo web necesitaba predicciones; reentrenar por petición era lento y
podía cambiar los resultados evaluados.

**Decisión.** Cargar los `.joblib` existentes una vez y puntuar con ellos.

**Razón.** Congela el modelo evaluado y mantiene la API rápida. Consecuencia: si cambia el
dataset real, hay que reentrenar y recargar.

## 2026-11-05 · FastAPI + Next.js, mismo origen

**Contexto.** Se necesitaba separar la lógica de la interfaz sin complicar el despliegue del
prototipo.

**Decisión.** API FastAPI en 8000 e interfaz Next.js en 3000, con proxy de `/api/*` en
`next.config.ts`; cookies `HttpOnly` y `SameSite=Lax`.

**Razón.** Evita CORS en el navegador y reduce la superficie de exposición de tokens.

## 2026-11-06 · Aislamiento en servidor, no en la interfaz

**Contexto.** Los filtros de curso en la interfaz son visibles y modificables por el usuario.

**Decisión.** El dataset incluye `docente_id` y `curso`; cada endpoint filtra por el docente
de la sesión y una ficha ajena responde 404.

**Razón.** Un filtro de UI no es una barrera de seguridad. Consecuencia: las pruebas cubren
explícitamente el acceso entre docentes.

## 2026-11-08 · LLM al final, con lista blanca y presupuesto

**Contexto.** Un LLM puede redactar mejor que una plantilla, pero es un costo, puede fallar y
no debe ver datos personales.

**Decisión.** El modelo clásico predice y explica; el LLM solo redacta un JSON con
`titulo/texto/accion`. Se envían solo asignatura, momento, prioridad, probabilidad, señales y
acciones. Máximo 25 llamadas por lote; firma de datos para no repetir cobro.

**Razón.** Separa predecir de narrar, preserva la trazabilidad y evita filtrar nombres, IDs,
correo, género ni estrato. Consecuencia: si falla, se muestra la plantilla etiquetada como tal.

## 2026-11-17 · Gemini como proveedor principal

**Contexto.** No había clave de OpenAI, así que los resúmenes salían por plantilla. El dueño
del repositorio aportó una clave de Gemini.

**Decisión.** Usar Gemini 3.5 Flash Lite mediante la Interactions API con `store=false`,
manteniendo OpenAI y la plantilla como respaldos. La clave vive solo en un `.env` local
ignorado por Git; `.env.example` queda vacío.

**Razón.** `generateContent` ya no está disponible para cuentas nuevas en los modelos
recomendados; la Interactions API es la interfaz recomendada desde 2026. `store=false`
evita que el proveedor conserve el caso. Consecuencia: hace falta `GEMINI_API_KEY` para ver
resúmenes redactados; sin ella el sistema sigue funcionando con plantillas.

## 2026-11-17 · SQLite temporal y datos sintéticos

**Contexto.** Aún no llega la base de datos real del profesor.

**Decisión.** Sembrar SQLite local con 6 docentes de demostración y datos sintéticos; dejar
`data/raw/` y `*.db` fuera de Git. Documentar el estado explícitamente en `docs/ESTADO.md`.

**Razón.** Permite demostrar el flujo completo sin exponer datos reales ni fingir un
despliegue. Consecuencia: las cifras son preliminares; pendiente PostgreSQL y LMS.

## 2026-11-17 · Interfaz sobria, sin emojis

**Contexto.** La primera interfaz tenía elementos decorativos y etiquetas de «IA» que
distraían y daban una impresión incorrecta del proyecto.

**Decisión.** Paleta azul institucional, texto en vez de iconos, bloque llamado «Resumen del
caso» y pie que recuerda que el docente decide.

**Razón.** Es una herramienta de acompañamiento académico en investigación, no un producto
de IA. La transparencia se conserva en lenguaje neutro.
