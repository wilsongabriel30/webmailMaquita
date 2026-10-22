"""Pruebas del panel general. Se ejecutan desde admin-panel/backend:  PYTHONPATH=. pytest tests

El panel exige sus secretos al importar app.config: aquí van valores de prueba (nunca los reales)."""

import os

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET", "secreto-de-pruebas-del-panel-0123456789")
os.environ.setdefault("ADMIN_JWT_SECRET", "secreto-compartido-de-pruebas-0123456789")
os.environ.setdefault("DB_PASS", "solo-para-pruebas")
os.environ.setdefault("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
# Sin el fichero de la organización del equipo en que se prueba: solo valores de ejemplo.
os.environ["ORG_FICHERO"] = os.path.join(os.path.dirname(__file__), "no-existe.env")
