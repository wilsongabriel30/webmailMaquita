"""Visor de los últimos bloqueos (y detecciones) del cortafuegos de aplicación de un sitio.

Lee el final del registro de auditoría del sitio (waf_sitio.registro), en el formato «Serial» nativo de ModSecurity
v3 (secciones ---id---A--, B, F, H, Z) o en JSON (una transacción por línea), y devuelve los últimos sucesos:
fecha, IP, método, ruta, código de respuesta, si se bloqueó o solo se anotó y las reglas de CRS que saltaron
(número y mensaje), para poder añadir una exclusión desde el panel.

No se devuelve la cadena de consulta ni los datos que hicieron saltar la regla: pueden llevar contraseñas o datos
personales de quien visitó el sitio.
"""

import json
import os
import re

from comun import leer_meta

LEER_BYTES = 2 * 1024 * 1024
MAXIMO = 200
RE_SECCION = re.compile(r"^---([A-Za-z0-9]{6,40})---([A-Z])--$")
RE_A = re.compile(r"^\[([^\]]{10,40})\]\s+\S+\s+([0-9a-fA-F:.]{2,45})\s")
RE_PETICION = re.compile(r"^([A-Z]{3,10}) (\S{1,4000}) HTTP/[0-9.]+$")
RE_ESTADO = re.compile(r"^HTTP/[0-9.]+ (\d{3})")
RE_ID = re.compile(r'\[id "(\d{6,7})"\]')
RE_MSG = re.compile(r'\[msg "([^"]{0,300})"\]')
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# Reglas de puntuación y de cierre: dicen «se bloqueó», no por qué. No se ofrecen para excluir.
EVALUACION = re.compile(r"^9(49|59|80)\d{3}$")


def _limpio(texto, maximo=200):
    return _CONTROL.sub("", str(texto or ""))[:maximo]


def _ruta(uri):
    return _limpio(str(uri or "").split("?", 1)[0], 300)


def _suceso(fecha, ip, metodo, uri, codigo, mensajes):
    reglas, bloqueado = [], False
    for linea in mensajes:
        if "Access denied" in linea:
            bloqueado = True
        ident = RE_ID.search(linea)
        if not ident or EVALUACION.fullmatch(ident.group(1)):
            continue
        msg = RE_MSG.search(linea)
        regla = {"id": int(ident.group(1)), "mensaje": _limpio(msg.group(1) if msg else "", 200)}
        if regla not in reglas:
            reglas.append(regla)
    if codigo == 403:
        bloqueado = True
    return {"fecha": _limpio(fecha, 40), "ip": _limpio(ip, 45), "metodo": _limpio(metodo, 10), "ruta": _ruta(uri),
            "codigo": codigo, "accion": "bloqueado" if bloqueado else "detectado", "reglas": reglas[:20]}


def _de_json(linea):
    try:
        t = json.loads(linea).get("transaction") or {}
    except (ValueError, AttributeError):
        return None
    if not isinstance(t, dict):
        return None
    pet = t.get("request") if isinstance(t.get("request"), dict) else {}
    res = t.get("response") if isinstance(t.get("response"), dict) else {}
    mensajes = []
    for m in t.get("messages") or []:
        if isinstance(m, dict):
            d = m.get("details") if isinstance(m.get("details"), dict) else {}
            mensajes.append(f'{m.get("message", "")} [id "{d.get("ruleId", "")}"] [msg "{_limpio(m.get("message"), 200)}"]')
    codigo = res.get("http_code") if isinstance(res.get("http_code"), int) else None
    return _suceso(t.get("time_stamp"), t.get("client_ip"), pet.get("method"), pet.get("uri"), codigo, mensajes)


def analizar(texto):
    """Sucesos del texto (del más antiguo al más reciente). Una transacción cortada al principio se ignora."""
    sucesos, actual, seccion = [], None, None
    for linea in texto.splitlines():
        if linea.startswith("{"):
            s = _de_json(linea)
            if s:
                sucesos.append(s)
            continue
        m = RE_SECCION.match(linea)
        if m:
            seccion = m.group(2)
            if seccion == "A":
                actual = {"fecha": "", "ip": "", "metodo": "", "uri": "", "codigo": None, "mensajes": []}
            elif seccion == "Z" and actual is not None:
                sucesos.append(_suceso(actual["fecha"], actual["ip"], actual["metodo"], actual["uri"],
                                       actual["codigo"], actual["mensajes"]))
                actual = None
            continue
        if actual is None or not linea.strip():
            continue
        if seccion == "A" and not actual["fecha"]:
            a = RE_A.match(linea)
            if a:
                actual["fecha"], actual["ip"] = a.group(1), a.group(2)
        elif seccion == "B" and not actual["metodo"]:
            p = RE_PETICION.match(linea)
            if p:
                actual["metodo"], actual["uri"] = p.group(1), p.group(2)
        elif seccion == "F" and actual["codigo"] is None:
            e = RE_ESTADO.match(linea)
            if e:
                actual["codigo"] = int(e.group(1))
        elif seccion == "H" and len(actual["mensajes"]) < 50:
            actual["mensajes"].append(linea[:4000])
    return sucesos


def _final(ruta, tope=LEER_BYTES):
    try:
        with open(ruta, "rb") as f:
            f.seek(0, os.SEEK_END)
            tam = f.tell()
            f.seek(max(0, tam - tope))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def ultimos(dominio, cuantos=50):
    import waf_sitio

    meta = leer_meta(dominio)
    cuantos = max(1, min(int(cuantos), MAXIMO))
    sucesos = analizar(_final(waf_sitio.registro(meta["dominio"])))
    return {"dominio": dominio, "modo": waf_sitio.ajustes(meta)["modo"], "sucesos": list(reversed(sucesos))[:cuantos]}
