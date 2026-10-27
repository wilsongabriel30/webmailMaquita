"""Sesiones de la app de escritorio (Teams Maquita): abiertas hasta que la persona cierra sesión.

Regla de gerencia TI (27/10/2026): en Teams Maquita la sesión se queda abierta de forma permanente
salvo que el usuario la cierre desde la app. En el navegador se mantiene el vencimiento normal
(ACCESS_TOKEN_EXPIRE_MINUTES / REFRESH_TOKEN_EXPIRE_DAYS).

Cómo se reconoce la app al iniciar sesión (/login y /login/2fa):
- User-Agent con «MaquitaTeams» (el de sus WebView2: renovaciones y páginas), o
- cabecera `X-Maquita-App` (la app la enviará en su login nativo desde la 0.7.2), o
- User-Agent vacío: el login nativo de la 0.7.1 sale de un HttpClient de .NET sin User-Agent, y
  ningún navegador manda uno vacío.

Qué cambia en una sesión `app` (kind="app"):
- vencimiento absoluto: APP_SESION_DIAS (365) en vez de REFRESH_TOKEN_EXPIRE_DAYS (7);
- el refresh dura APP_SESION_DIAS y se rota en cada renovación (la app renueva cada 6 h);
- el access y el estado en Redis (sess / imap_pass) duran APP_ACCESS_DIAS (7) en vez de 8 h, para
  que un fin de semana o unos días con el equipo apagado no cierren la sesión.
La regla única de F-01/F-04 no cambia: cerrar sesión, cambiar la contraseña o revocar la generación
(auth_version) la mata al instante, igual que a cualquier otra sesión.
"""

from datetime import datetime, timedelta, timezone

from app.config import get_settings

KIND_APP = "app"
MARCA_UA = "maquitateams"
CABECERA_APP = "x-maquita-app"


def es_app(request) -> bool:
    """¿La petición viene de la app de escritorio? Ver el módulo para las señales."""
    if request is None:
        return False
    cabeceras = request.headers
    ua = (cabeceras.get("user-agent") or "").strip()
    if MARCA_UA in ua.lower():
        return True
    if (cabeceras.get(CABECERA_APP) or "").strip():
        return True
    return ua == ""


def parametros_sesion(request) -> dict:
    """Argumentos extra para `crear_sesion`: vacíos en el navegador, `kind`/`abs_exp` en la app."""
    if not es_app(request):
        return {}
    abs_exp = datetime.now(timezone.utc) + timedelta(
        days=get_settings().app_sesion_dias
    )
    return {"kind": KIND_APP, "abs_exp": abs_exp}


def tope_access_seg(kind: str) -> int:
    """Vida máxima (segundos) del access y del estado en Redis según la clase de sesión."""
    s = get_settings()
    if kind == KIND_APP:
        return s.app_access_dias * 86400
    return s.access_token_expire_minutes * 60


def dias_refresh(kind: str) -> int:
    """Vida (días) de cada refresh emitido según la clase de sesión."""
    s = get_settings()
    return s.app_sesion_dias if kind == KIND_APP else s.refresh_token_expire_days
