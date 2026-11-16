# -*- coding: utf-8 -*-
"""El service worker del chat (T-116) solo limpia sus propias copias y se sirve sin sesión.

El almacén de cachés es uno por dominio y lo comparte el service worker del correo: cuando el del chat
borraba todo lo que no era suyo, el correo se quedaba sin su copia y no arrancaba sin conexión
(13 al 15/11/2026).
"""
import os

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WEB = os.path.join(_RAIZ, "app", "interfaces", "web")


def _leer(*partes):
    with open(os.path.join(*partes), encoding="utf-8") as f:
        return f.read()


def _sin_comentarios(texto):
    return "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith(("//", "*", "/*", "#")))


def test_la_limpieza_no_toca_las_copias_de_otros():
    sw = _sin_comentarios(_leer(_WEB, "estaticos", "chat-sw.js"))
    activar = sw.split("addEventListener('activate'")[1].split("addEventListener(")[0]
    assert "k.indexOf(PREFIJO_PROPIO) === 0 && k.indexOf(VERSION) !== 0" in activar
    assert "var PREFIJO_PROPIO = 'maquita-chat-';" in sw
    # la versión empieza por el prefijo: si no, nunca limpiaría las suyas
    version = sw.split("var VERSION = '")[1].split("'")[0]
    assert version.startswith("maquita-chat-")


def test_los_envios_no_pasan_por_el_service_worker():
    sw = _sin_comentarios(_leer(_WEB, "estaticos", "chat-sw.js"))
    assert "if (req.method !== 'GET') return;" in sw


def test_se_registra_con_su_alcance_y_la_plantilla_lo_carga():
    registro = _sin_comentarios(_leer(_WEB, "estaticos", "js", "chat-offline.js"))
    assert "register('/chat/sw.js', { scope: '/chat/' })" in registro
    plantilla = _leer(_WEB, "plantillas", "chat", "index.html")
    assert "filename='js/chat-offline.js'" in plantilla


def test_la_ruta_lo_sirve_sin_sesion_y_sin_cache():
    app = _sin_comentarios(_leer(_RAIZ, "app_chat.py"))
    assert '@app.route("/chat/sw.js")' in app
    assert 'send_from_directory(_ESTATICOS, "chat-sw.js")' in app
    assert 'resp.headers["Service-Worker-Allowed"] = "/chat/"' in app
    assert 'resp.headers["Cache-Control"] = "no-cache"' in app
    antes_de_auth = app.split("def _auth():")[1].split("_RUTAS_SERVICIO")[0]
    assert 'if request.path == "/chat/sw.js":' in antes_de_auth
