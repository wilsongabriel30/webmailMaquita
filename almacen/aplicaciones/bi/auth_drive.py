"""Puente de autenticación: valida el token del Drive Maquita y lo expone a
flask_login, para que el Editor de PDF (que usa `@login_required` / `current_user`)
funcione como una Aplicación del Drive sin login propio.

Reutiliza el mismo contrato que el resto del Almacén:
- cookie `access_token` = JWT firmado con `WEBMAIL_SECRET_KEY` (payload: `sub`=usuario
  del buzón, `type`=access);
- la sesión debe seguir viva en Redis (`imap_pass:<usuario>`), que el logout borra.
"""
import os

import jwt
from flask import request
from flask_login import LoginManager, UserMixin

_SECRET = os.getenv("WEBMAIL_SECRET_KEY") or os.getenv("SECRET_KEY", "")
_REDIS_URL = os.getenv("REDIS_URL", "")
_redis = None


class UsuarioDrive(UserMixin):
    """Usuario mínimo para flask_login; `id` es el correo/usuario del buzón."""
    def __init__(self, username):
        self.id = username
        self.username = username


def _sesion_viva(username):
    """Con Redis, exige que la sesión del webmail siga activa. Sin Redis, basta el JWT."""
    global _redis
    if not _REDIS_URL:
        return True
    try:
        if _redis is None:
            import redis
            _redis = redis.Redis.from_url(_REDIS_URL, socket_timeout=2)
        return bool(_redis.exists("imap_pass:%s" % username))
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
    if not username or not _sesion_viva(username):
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
