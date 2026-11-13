# -*- coding: utf-8 -*-
"""Identificación amable de la sesión por dispositivo (L-02, 13/11/2026).

A partir del User-Agent, de las cabeceras que envían las apps y de la IP, se calcula el
nombre claro, la clase, la ubicación aproximada y el equipo (para agrupar). Son funciones
puras: NO escriben cookies ni tocan Redis (de eso se encarga el router y sesiones.py).

Cabeceras que las apps pueden enviar al iniciar sesión (opcionales, validadas y recortadas):
  X-Maquita-App          la app ya la envía para recibir sesión de tipo «app»
  X-Maquita-Plataforma   "android" | "escritorio"  (distingue móvil de escritorio)
  X-Maquita-Equipo       nombre del equipo (hostname o modelo)
  X-Maquita-Modelo       modelo del dispositivo
  X-Maquita-App-Version  versión de la app
  X-Maquita-Instalacion  identificador estable de instalación (device_id en el celular)
"""

import hashlib
import ipaddress
import re
import secrets

CAB = {
    "plataforma": "x-maquita-plataforma",
    "equipo": "x-maquita-equipo",
    "modelo": "x-maquita-modelo",
    "app_version": "x-maquita-app-version",
    "instalacion": "x-maquita-instalacion",
}


def _recortar(valor, n=80):
    return (str(valor).strip()[:n]) if valor else ""


def leer_cabeceras_app(request) -> dict:
    """Las cabeceras de la app, validadas y recortadas. Vacías si no vienen."""
    h = getattr(request, "headers", None) or {}
    return {k: _recortar(h.get(cab)) for k, cab in CAB.items()}


def _navegador(ua: str) -> str:
    if not ua:
        return "Navegador"
    if "Edg/" in ua:
        return "Edge"
    if "OPR/" in ua or "Opera" in ua:
        return "Opera"
    if "Firefox/" in ua:
        return "Firefox"
    if "Chrome/" in ua:
        return "Chrome"
    if "Safari/" in ua:
        return "Safari"
    return "Navegador"


def _sistema(ua: str) -> str:
    if not ua:
        return ""
    if "Android" in ua:
        return "Android"
    if "iPhone" in ua or "iPad" in ua or "iOS" in ua:
        return "iOS"
    if "Windows" in ua:
        return "Windows"
    if "Mac OS" in ua or "Macintosh" in ua:
        return "macOS"
    if "Linux" in ua:
        return "Linux"
    return ""


# Señales de que una app es de ESCRITORIO (Teams Maquita) o MÓVIL (Maquita Mail Android/iOS).
_MOVIL_UA = (
    "Android",
    "okhttp",
    "Dalvik",
    "iPhone",
    "iPad",
    "iOS",
    "CFNetwork",
    "Darwin",
)


def clase_de(kind: str, ua: str, plataforma: str) -> str:
    """navegador | app_movil | app_escritorio | otro.

    Para kind="app" hay que distinguir la app de escritorio (Teams Maquita: User-Agent con
    «MaquitaTeams», o login nativo .NET SIN User-Agent) de la app móvil (Maquita Mail Android,
    cuyo cliente HTTP manda «okhttp»/«Dalvik»/«Android»). La cabecera X-Maquita-Plataforma
    manda si viene."""
    ua = ua or ""
    plataforma = (plataforma or "").lower()
    if kind == "app":
        if plataforma == "android" or plataforma == "ios" or plataforma == "movil":
            return "app_movil"
        if plataforma in ("escritorio", "windows") or "MaquitaTeams" in ua:
            return "app_escritorio"
        if ua == "":
            return "app_escritorio"  # login nativo .NET de Teams de escritorio (sin User-Agent)
        if any(t in ua for t in _MOVIL_UA):
            return "app_movil"
        return "app_movil"  # app que no es claramente de escritorio: se asume móvil
    if _navegador(ua) != "Navegador" or _sistema(ua):
        return "navegador"
    return "otro"


def nombre_de(
    clase: str, ua: str, modelo: str, app_version: str, equipo_nombre: str
) -> str:
    """Texto claro para la persona."""
    if clase == "app_movil":
        aparato = modelo or equipo_nombre or "celular"
        version = (" " + app_version) if app_version else ""
        return f"Celular {aparato} · app Maquita Mail{version}".strip()
    if clase == "app_escritorio":
        return "Teams Maquita de escritorio"
    if clase == "navegador":
        so = _sistema(ua)
        return f"{_navegador(ua)} en {so}" if so else _navegador(ua)
    return ua[:40] if ua else "Dispositivo"


def ubicacion_de(ip: str):
    """«Red interna de la organización» o None. Las redes propias salen de la configuración
    (ORG_REDES), igual que en la detección de inicios riesgosos; el país no se adivina aquí.
    """
    if not ip:
        return None
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None
    try:
        from app.risky_login.geoip import is_internal

        return "Red interna de la organización" if is_internal(ip) else None
    except Exception:
        return None


_ANTIGUO = re.compile(r"^nav-[0-9a-f]{16}$")


def es_identificador_antiguo(eid: str) -> bool:
    """Identificadores derivados del User-Agent (los del primer día): compartidos entre equipos."""
    return bool(_ANTIGUO.match(eid or ""))


def nuevo_identificador_de_navegador() -> str:
    return "nav-" + secrets.token_urlsafe(18)


def ip_de(request) -> str:
    """Dirección de quien se conecta. El servidor está detrás de nginx: `request.client.host` es
    siempre 127.0.0.1, y con ella todo ingreso parecía venir de la «Red interna»."""
    if request is None:
        return ""
    h = getattr(request, "headers", None) or {}
    ip = (h.get("x-real-ip") or "").strip() or (h.get("x-forwarded-for") or "").split(
        ","
    )[0].strip()
    if not ip:
        cliente = getattr(request, "client", None)
        ip = getattr(cliente, "host", "") or ""
    return ip[:64]


def equipo_para_navegador(cookie_valor: str, ua: str):
    """(equipo_id, equipo_nombre, aproximado) para un navegador. El id viene de una cookie
    propia de larga duración (la pone el router si falta). Es APROXIMADO por definición.
    """
    # El identificador es ALEATORIO por navegador (13/11/2026). Antes salía del User-Agent: dos equipos
    # con el mismo navegador compartían identificador, así que un intruso con ese navegador contaba como
    # «equipo conocido» y no generaba aviso, y la lista de sesiones mezclaba equipos distintos.
    eid = _recortar(cookie_valor, 64)
    if not eid or es_identificador_antiguo(eid):
        eid = nuevo_identificador_de_navegador()
    so = _sistema(ua)
    nombre = f"Navegador en {so}" if so else "Navegador"
    return eid, nombre, True


def equipo_para_app(cab: dict, ua: str):
    """(equipo_id, equipo_nombre, aproximado) para una app. Si trae identificador de
    instalación, el equipo es EXACTO; si no, se deriva (aproximado)."""
    inst = cab.get("instalacion")
    nombre = cab.get("equipo") or cab.get("modelo") or (_sistema(ua) or "Dispositivo")
    if inst:
        return "app-" + inst, nombre, False
    base = (cab.get("modelo", "") + "|" + (ua or "")).encode()
    return "app-" + hashlib.sha1(base).hexdigest()[:16], nombre, True


def describir(d: dict, kind: str) -> dict:
    """De los campos crudos guardados en la sesión → nombre, clase y ubicación para listar."""
    ua = d.get("ua") or ""
    clase = d.get("clase") or clase_de(kind, ua, d.get("plataforma") or "")
    return {
        "nombre": d.get("nombre")
        or nombre_de(
            clase,
            ua,
            d.get("modelo") or "",
            d.get("app_version") or "",
            d.get("equipo_nombre") or "",
        ),
        "clase": clase,
        "ubicacion": ubicacion_de(d.get("ip") or ""),
    }


# --------------------------------------------------------- preparación en el login
COOKIE_EQUIPO = "maquita_equipo"
EQUIPO_MAX_AGE = 400 * 86400  # ~400 días: identificador estable del navegador


def preparar_dispositivo(request, response, kind: str) -> dict:
    """Resuelve los campos de dispositivo al iniciar sesión. En navegador, si no hay cookie
    de equipo, la pone en la respuesta (identificador aproximado y estable por navegador).
    """
    h = getattr(request, "headers", None) or {}
    ua = (h.get("user-agent") or "")[:200]
    cab = leer_cabeceras_app(request)
    clase = clase_de(kind, ua, cab.get("plataforma") or "")
    if kind == "app":
        eid, enombre, eaprox = equipo_para_app(cab, ua)
    else:
        cookies = getattr(request, "cookies", None) or {}
        valor = cookies.get(COOKIE_EQUIPO)
        eid, enombre, eaprox = equipo_para_navegador(valor, ua)
        if eid != valor and response is not None:
            try:
                from app.auth.cookies import dominio_cookie

                response.set_cookie(
                    COOKIE_EQUIPO,
                    eid,
                    max_age=EQUIPO_MAX_AGE,
                    httponly=True,
                    secure=True,
                    samesite="lax",
                    domain=dominio_cookie(request),
                    path="/",
                )
            except Exception:
                pass
    return {
        "clase": clase,
        "plataforma": cab.get("plataforma", ""),
        "modelo": cab.get("modelo", ""),
        "app_version": cab.get("app_version", ""),
        "equipo_id": eid,
        "equipo_nombre": enombre,
        "equipo_aprox": eaprox,
    }
