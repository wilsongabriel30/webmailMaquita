"""Puente de autenticación: valida el token del Drive y lo expone a flask_login, para
que la Aplicación del Drive (que usa `@login_required` / `current_user`) funcione sin
login propio.

Reutiliza el mismo contrato que el resto del Almacén:
- cookie `access_token` = JWT firmado con `WEBMAIL_SECRET_KEY` (payload: `sub`=usuario
  del buzón, `type`=access y, desde F-01, `sid`=sesión);
- la sesión debe seguir viva en Redis. Desde el 12/10/2026 el webmail la guarda POR
  SESIÓN, `imap_pass:<usuario>:<sid>` (`backend/app/auth/sesiones.py`), y la borra al
  cerrar o revocar esa sesión. Aquí se seguía mirando `imap_pass:<usuario>`, que ya no
  existe, y todas las sesiones abiertas recibían 401.

ESTE ARCHIVO ES IDÉNTICO en `almacen/aplicaciones/pdf_editor` y `almacen/aplicaciones/bi`
(cada aplicación se instala por separado). Si cambias uno, copia el otro: la prueba
`almacen/tests/test_auth_drive_aplicaciones.py` falla si divergen.
"""
import os

import jwt
from flask import request
from flask_login import LoginManager, UserMixin

_SECRET = os.getenv("WEBMAIL_SECRET_KEY") or os.getenv("SECRET_KEY", "")
_REDIS_URL = os.getenv("REDIS_URL", "")
_redis = None

# Lote de cada vuelta de SCAN (acotado: nunca KEYS, que bloquea Redis entero).
_LOTE_SCAN = 200


class UsuarioDrive(UserMixin):
    """Usuario mínimo para flask_login; `id` es el correo/usuario del buzón."""
    def __init__(self, username):
        self.id = username
        self.username = username


def _escapar_patron(texto):
    """Escapa los comodines de un patrón MATCH de Redis (`*`, `?`, `[`, `]`, `\\`)."""
    return "".join("\\" + c if c in "*?[]\\" else c for c in texto)


def _cliente_redis():
    global _redis
    if _redis is None:
        import redis
        _redis = redis.Redis.from_url(_REDIS_URL, socket_timeout=2)
    return _redis


def _sesion_viva(username, sid=None):
    """Con Redis, exige que la sesión del webmail siga activa. Sin Redis, basta el JWT.

    - Token con `sid`: solo vale `imap_pass:<usuario>:<sid>`. Una sesión cerrada o
      revocada no revive porque haya otra abierta (ni por la clave antigua).
    - Token sin `sid` (anterior a F-01): vale la clave antigua `imap_pass:<usuario>` o
      cualquier `imap_pass:<usuario>:*` (SCAN con MATCH y COUNT acotado).
    """
    if not _REDIS_URL:
        return True
    try:
        cliente = _cliente_redis()
        if sid:
            return bool(cliente.exists("imap_pass:%s:%s" % (username, sid)))
        if cliente.exists("imap_pass:%s" % username):
            return True
        patron = "imap_pass:%s:*" % _escapar_patron(username)
        for _clave in cliente.scan_iter(match=patron, count=_LOTE_SCAN):
            return True
        return False
    except Exception:
        return False


def usuario_desde_cookie():
    """Devuelve un UsuarioDrive validado desde la cookie `access_token`, o None."""
    token = request.cookies.get("access_token")
    if not token or not _SECRET:
        return None
    try:
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    username = (payload.get("sub") or "").strip().lower()
    sid = str(payload.get("sid") or "").strip()
    if not username or not _sesion_viva(username, sid=sid or None):
        return None
    return UsuarioDrive(username)


def init_auth(app):
    """Conecta flask_login a la validación del token del Drive (por request, no sesión)."""
    lm = LoginManager()
    lm.init_app(app)

    @lm.request_loader
    def cargar_usuario(_req):
        return usuario_desde_cookie()

    return lm
