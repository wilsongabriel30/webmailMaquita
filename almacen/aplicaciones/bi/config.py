"""Configuración de la app de Tableros/BI (Aplicación del Drive Maquita).
Todo por entorno; sin credenciales en el código. Ver `.env.example`.
"""
import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("WEBMAIL_SECRET_KEY", "")
    WEBMAIL_SECRET_KEY = os.getenv("WEBMAIL_SECRET_KEY") or os.getenv("SECRET_KEY", "")
    REDIS_URL = os.getenv("REDIS_URL", "")
    ALMACEN_INTERNAL_URL = os.getenv("ALMACEN_INTERNAL_URL", "http://127.0.0.1:8788")
    WTF_CSRF_ENABLED = False  # API de solo lectura; el token del Drive es la credencial
