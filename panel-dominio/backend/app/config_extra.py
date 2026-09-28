"""Ajustes de la segunda entrega (segundo factor, marca, DNS)."""

import os

# El segundo factor es obligatorio salvo que se apague a propósito (instalaciones de prueba).
TOTP_OBLIGATORIO = os.getenv("PD_TOTP_OBLIGATORIO", "1").lower() not in ("0", "no", "false")
EMISOR = os.getenv("PD_EMISOR", "Portal de dominio")[:40]

# Carpeta que comparte con el webmail, que es quien muestra el logo en público.
DIR_MARCA = os.getenv("PD_DIR_MARCA", "/opt/webmail/uploads/branding/empresas")
MARCA_MAX_BYTES = int(os.getenv("PD_MARCA_MAX_KB", "512")) * 1024

# Selectores DKIM que se consultan en la verificación DNS.
SELECTORES_DKIM = [s.strip() for s in os.getenv("PD_SELECTORES_DKIM", "default,dkim,mail,selector1,selector2").split(",") if s.strip()]
