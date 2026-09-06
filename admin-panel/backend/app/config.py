import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "maildb")
DB_USER = os.getenv("DB_USER", "mailserver")
DB_PASS = os.getenv("DB_PASS", "")

# Origenes CORS permitidos (coma-separado). El panel es mismo-origen; por defecto solo
# un placeholder. NUNCA "*" con allow_credentials. En produccion, fijar ADMIN_CORS_ORIGINS.
CORS_ORIGINS = os.getenv("ADMIN_CORS_ORIGINS", "https://admin.example.com")

JWT_SECRET = os.getenv("JWT_SECRET", "")
# Secreto COMPARTIDO con el backend del correo: solo firma el vale de impersonacion.
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480  # 8 horas

RSPAMD_URL = os.getenv("RSPAMD_URL", "http://localhost:11334")
RSPAMD_PASSWORD = os.getenv("RSPAMD_PASSWORD", "")

MAIL_LOG_PATH = "/var/log/mail.log"
POSTFIX_LOG_PATH = "/var/log/mail.log"

VMAIL_PATH = "/var/vmail"

# Entorno: "development"/"dev"/"local" habilita /docs; por defecto produccion (docs off).
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

def _validar_secretos_obligatorios():
    """Aborta el arranque del panel si falta JWT_SECRET o tiene valor de ejemplo.
    No muestra el valor, solo el nombre de la variable."""
    _PLACEHOLDER = ("change", "example", "placeholder", "tu-secreto", "your-secret", "changeme")
    if not (ADMIN_JWT_SECRET or "").strip():
        raise RuntimeError(
            "Falta ADMIN_JWT_SECRET — es el secreto compartido con el backend del correo; "
            "sin el no se puede emitir el vale de impersonacion."
        )
    if not (DB_PASS or "").strip():
        raise RuntimeError("Falta DB_PASS — el panel no puede conectar a la base de datos.")
    v = (JWT_SECRET or "").strip()
    if not v or any(p in v.lower() for p in _PLACEHOLDER):
        raise RuntimeError(
            "Falta JWT_SECRET (o tiene un valor de ejemplo) — el panel no puede firmar tokens. "
            "Defínelo en el entorno con un valor real."
        )


_validar_secretos_obligatorios()
