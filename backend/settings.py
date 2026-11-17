"""Configuración del backend, leída desde variables de entorno.

Nunca poner secretos reales en este archivo. Copiar `.env.example` a `.env`
(.env está ignorado por Git) o exportar las variables antes de desplegar.
Las variables del entorno real tienen prioridad sobre las del archivo .env.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cargar_env_local() -> None:
    """Carga un .env local sin dependencias extra; no sobrescribe el entorno."""
    ruta = ROOT / ".env"
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave:
            os.environ.setdefault(clave, valor)


_cargar_env_local()


class Settings:
    def __init__(self) -> None:
        self.secret_key = os.getenv("EWS_SECRET_KEY", "dev-only-secret-change-me-1234567890")
        self.database_url = os.getenv("EWS_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'ews.db'}")
        self.cookie_secure = os.getenv("EWS_COOKIE_SECURE", "0") == "1"
        self.allowed_origins = [
            o.strip() for o in os.getenv(
                "EWS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",") if o.strip()
        ]
        self.session_hours = int(os.getenv("EWS_SESSION_HOURS", "8"))
        self.idle_minutes = int(os.getenv("EWS_IDLE_MINUTES", "30"))
        self.login_max_failures = int(os.getenv("EWS_LOGIN_MAX_FAILURES", "5"))
        self.login_window_minutes = int(os.getenv("EWS_LOGIN_WINDOW_MINUTES", "15"))

        # Resumen narrativo: se prefiere Gemini; OpenAI queda como respaldo.
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("EWS_GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("EWS_OPENAI_MODEL", "gpt-4o-mini")
        self.llm_enabled = (
            os.getenv("EWS_LLM_ENABLED", "1") == "1"
            and bool(self.gemini_api_key or self.openai_api_key)
        )
        self.llm_max_calls = int(os.getenv("EWS_LLM_MAX_CALLS", "25"))

    @property
    def is_production(self) -> bool:
        return self.cookie_secure

    @property
    def llm_proveedor(self) -> str:
        if not self.llm_enabled:
            return "plantilla"
        return "gemini" if self.gemini_api_key else "openai"


settings = Settings()
