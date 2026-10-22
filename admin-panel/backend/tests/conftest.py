"""Pruebas del panel general. app.config exige secretos al importarse: aquí van valores de prueba."""

import os
import sys

os.environ.setdefault("JWT_SECRET", "secreto-de-pruebas-del-panel-2026")  # gitleaks:allow (valor de prueba)
os.environ.setdefault("ADMIN_JWT_SECRET", "secreto-compartido-de-pruebas-2026")  # gitleaks:allow (valor de prueba)
os.environ.setdefault("DB_PASS", "solo-para-pruebas")
os.environ.setdefault("ORG_FICHERO", "/nonexistent/organizacion.env")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
