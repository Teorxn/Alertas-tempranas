# Sistema de Alertas Tempranas (EWS) - Pérdida de asignaturas

Prototipo que estima, **en distintos momentos del semestre**, qué estudiantes tienen alta
probabilidad de perder una asignatura, explica por qué y sugiere acciones al docente.

> Los datos actuales son **sintéticos** (inventados) y solo sirven para probar el pipeline.
> Cuando llegue el dataset real se reemplazan sin cambiar la lógica del modelo.

**[Estado del proyecto y evidencias](docs/ESTADO.md)** ·
[Evidencias detalladas](docs/EVIDENCIAS.md) · [Decisiones](docs/DECISIONES.md) ·
[Avance completo](docs/AVANCE.md)

## Módulo web para docentes (FastAPI + Next.js)

Además del prototipo Streamlit, hay un módulo web con **login seguro**, aislamiento por
docente, notificaciones in-app y resúmenes generados con LLM.

```
Navegador (Next.js :3000)
   │  /api/*  (mismo origen, proxy next.config.ts)
   ▼
FastAPI (:8000) ── SQLAlchemy ── SQLite/PostgreSQL
   │
   ├── auth: bcrypt + sesiones opacas + CSRF + límite de intentos
   ├── ML: modelos .joblib existentes (T0/T1/T2) + explicación por oclusión
   ├── LLM: resumen estructurado (Gemini) con OpenAI y plantilla de respaldo
   └── notificaciones: se crean/actualizan al generar alertas
```

### Puesta en marcha

```bash
# 1) Dependencias
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2) Datos sintéticos + modelos (si aún no existen)
python src/generar_datos_sinteticos.py
python src/entrenar.py

# 3) Cargar BD de ejemplo (docentes, inscripciones y alertas)
python -m backend.services.seed

# 4) Terminal 1: API
python -m uvicorn backend.main:app --port 8000

# 5) Terminal 2: interfaz
cd frontend && npm run dev
```

Abrir **http://localhost:3000**. Usuarios de ejemplo (contraseña `ClaveSegura123!`):

| Correo | Docente | Asignatura |
|---|---|---|
| ana.torres@universidad.edu.co | Ana Torres | Cálculo I |
| luis.herrera@universidad.edu.co | Luis Herrera | Física I |
| marta.rios@universidad.edu.co | Marta Ríos | Álgebra Lineal |
| carlos.vega@universidad.edu.co | Carlos Vega | Programación I |
| sofia.duque@universidad.edu.co | Sofía Duque | Estadística |
| julia.moreno@universidad.edu.co | Julia Moreno | Comunicación Oral |

El botón «Actualizar predicciones» vuelve a puntuar **solo los cursos del docente** y
actualiza el centro de notificaciones.

### Seguridad implementada

| Riesgo | Medida |
|---|---|
| Contraseñas | bcrypt (pre-hash SHA-256, 12 rondas); nunca se guardan en claro |
| Fijación/sección de sesiones | token aleatorio de 256 bits, solo su SHA-256 en BD; expiración absoluta e inactividad; revocación al cerrar sesión y al cambiar contraseña |
| CSRF | doble envío con HMAC del secreto del servidor + validación de `Origin` en todo `POST/PATCH` |
| SQL injection | SQLAlchemy ORM, consultas parametrizadas; búsqueda con escape de `%`, `_` y `\` |
| XSS | React escapa todo por defecto (sin `dangerouslySetInnerHTML`) + CSP estricta en API y frontend |
| Fuerza bruta | límite por IP+correo y por IP, bloqueo temporal de la cuenta; respuestas genéricas |
| Privilegios | filtro `docente_id` en **cada consulta**; acceso a ficha ajena devuelve 404 |
| Errores | los 422 no devuelven los valores recibidos (evita filtrar contraseñas) |
| Cabeceras | `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS en producción |
| Datos del LLM | solo campos académicos en blanca; nunca nombre, ID, correo, género ni estrato |

Para producción: definir `EWS_SECRET_KEY` aleatorio y estable, `EWS_COOKIE_SECURE=1`,
orígenes permitidos y una clave de proveedor de LLM. Ver `.env.example`.

### LLM y resúmenes

Si hay `GEMINI_API_KEY`, el resumen se redacta con Gemini (por defecto `gemini-3.5-flash-lite`)
mediante la Interactions API, con `store=false` para que el proveedor no conserve el caso.
Si no hay clave de Gemini pero hay `OPENAI_API_KEY`, se usa `gpt-4o-mini` (configurable). Si
hay error, se agota el tiempo o se supera `EWS_LLM_MAX_CALLS`, se usa una plantilla local.
En la interfaz el bloque se llama «Resumen del caso»; la fuente se regresa en el campo
`resumen.fuente` (`llm` o `plantilla`).

Solo se envían campos académicos en blanca: nunca nombre, ID, correo, género ni estrato.
Los resúmenes se guardan asociados a una firma de los datos, así que no se cobra dos veces
por el mismo caso. El modelo clásico siempre hace la predicción; el LLM solo redacta.
La clave real va en un `.env` local, ignorado por Git.

### Pruebas

```bash
python -m pytest -q tests
```

Cubren: login con/sin CSRF, flujo de sesión, aislamiento entre docentes, notificaciones y
búsqueda con carga SQL/HTML.

---

## Pipeline de ML original

```bash
python src/generar_datos_sinteticos.py
python src/entrenar.py
streamlit run app/dashboard.py
```

El dashboard Streamlit sigue disponible como prototipo de investigación.

## Estructura

```
Alertas tempranas/
├── src/                       # config, datos sintéticos, features, entrenamiento, explicación
├── backend/
│   ├── main.py                # app FastAPI, CSRF y cabeceras de seguridad
│   ├── settings.py            # configuración por entorno
│   ├── security.py            # contraseñas, sesiones, CSRF, limitador
│   ├── deps.py                # sesión autenticada y auditoría
│   ├── models_db.py           # docentes, inscripciones, predicciones, notificaciones
│   ├── routers/               # auth, estudiantes, alertas
│   └── services/              # scoring (ML), llm, seed
├── frontend/                  # app Next.js (login, panel, filtros, notificaciones)
├── data/raw/                  # aquí va el dataset real (excluido de Git)
├── models/                    # modelos .joblib versionados localmente
├── reports/                   # métricas, equidad, figuras (regenerables)
├── tests/                     # pruebas de la API
└── docs/
    ├── ESTADO.md              # estado del prototipo y evidencias (índice)
    ├── EVIDENCIAS.md          # métricas, figuras y verificación
    ├── DECISIONES.md          # por qué se tomó cada camino
    ├── AVANCE.md              # documento de avance del proyecto
    ├── evidencias/            # copia versionada de métricas y figuras
    └── investigacion/         # informe técnico y fuentes revisadas
```

## Usar el dataset real

1. Copiar el archivo a `data/raw/`.
2. En `src/config.py`: ajustar `DATA_PATH`, nombres de columnas, `PESOS_CORTES` y `FEATURES_*`.
3. Agregar `docente_id` y `curso` a cada inscripción (son la clave del aislamiento).
4. Correr `python src/entrenar.py` y luego `python -m backend.services.seed`.
