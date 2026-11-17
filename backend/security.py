"""Primitivas de seguridad: contraseñas, sesiones, CSRF y límite de intentos.

- Contraseñas: bcrypt con pre-hash SHA-256 (evita el límite de 72 bytes de bcrypt).
- Sesiones: token aleatorio de 256 bits; solo se guarda su SHA-256 en la BD.
- CSRF: doble envío. La cookie de sesión es HttpOnly; el token se deriva con HMAC
  del secreto del servidor y se compara en tiempo constante con la cabecera.
"""
import base64
import bcrypt
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from settings import settings

SESSION_COOKIE = "ews_session"
CSRF_COOKIE = "ews_csrf"
CSRF_HEADER = "x-csrf-token"
_ANON_CSRF_TTL = 3600


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite devuelve datetimes sin zona; los normalizamos a UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _prehash(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _sign(message: str) -> str:
    return hmac.new(settings.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def csrf_for_session(token: str) -> str:
    return _sign("session:" + token)


def mint_anon_csrf() -> str:
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    return f"{timestamp}.{nonce}.{_sign(f'anon:{timestamp}.{nonce}')}"


def verify_anon_csrf(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 3 or not parts[0].isdigit():
        return False
    timestamp, nonce, signature = parts
    if abs(time.time() - int(timestamp)) > _ANON_CSRF_TTL:
        return False
    return hmac.compare_digest(_sign(f"anon:{timestamp}.{nonce}"), signature)


def secure_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")


class InMemoryLimiter:
    """Limitador por clave, suficiente para una instancia; en producción usar Redis."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)


login_limiter = InMemoryLimiter()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)


def is_expired(value: datetime | None) -> bool:
    value = as_utc(value)
    return value is None or value <= datetime.now(timezone.utc)
