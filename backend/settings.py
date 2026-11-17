"""Configuración del backend, leída desde variables de entorno.

Nunca poner secretos reales en este archivo. Copiar `.env.example` a `.env`
(y exportar las variables) antes de desplegar.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("EWS_OPENAI_MODEL", "gpt-4o-mini")
        self.llm_enabled = os.getenv("EWS_LLM_ENABLED", "1") == "1" and bool(self.openai_api_key)
        self.llm_max_calls = int(os.getenv("EWS_LLM_MAX_CALLS", "25"))

    @property
    def is_production(self) -> bool:
        return self.cookie_secure


settings = Settings()
