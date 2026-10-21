"""Funciones web por sitio (v1.10): un router por función. main.py los registra todos con `routers`."""

from app.sitios.web import bloqueo_ip, errores, estado, ftp_cuentas, hotlink, optimizacion, privacidad, redirecciones

routers = [m.router for m in (estado, redirecciones, privacidad, errores, hotlink, bloqueo_ip, optimizacion, ftp_cuentas)]
