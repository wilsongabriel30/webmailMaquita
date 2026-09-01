"""Configuración de la app autónoma del Editor de PDF (Aplicación del Drive Maquita).

Todo se lee de variables de entorno; no hay credenciales en el código. Ver
`.env.example`. El módulo del editor hace `from config import Config`, por eso esta
clase vive en la raíz importable de la app.
"""
import os


class Config:
    # Base de datos de la app (documentos, anotaciones, firmas).
    HERRAMIENTAS_DATABASE_URI = os.getenv("HERRAMIENTAS_DATABASE_URI", "")
    # Base de datos de identidad (solo lectura de usuarios, si aplica).
    AUTH_DATABASE_URI = os.getenv("AUTH_DATABASE_URI", "")

    # Secreto para firmar/validar cookies y CSRF. Se comparte con el webmail/Drive
    # para poder validar su token (access_token).
    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("WEBMAIL_SECRET_KEY", "")
    WEBMAIL_SECRET_KEY = os.getenv("WEBMAIL_SECRET_KEY") or os.getenv("SECRET_KEY", "")

    # Redis del webmail: valida que la sesión del usuario siga viva (imap_pass:<user>).
    REDIS_URL = os.getenv("REDIS_URL", "")

    # Base pública del Drive, para construir enlaces y llamar a su API.
    ALMACEN_API = os.getenv("ALMACEN_INTERNAL_URL", "http://127.0.0.1:8788") + "/api/almacen"

    WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "1") != "0"
