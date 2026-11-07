"""Elegir, con la BODYSTRUCTURE, la parte de texto del correo (sin tocar los adjuntos).

Se prefiere el primer text/plain que no sea adjunto; si no hay, el primer text/html. Solo se
pide luego el INICIO de esa parte (`BODY.PEEK[parte]<0.n>`): los adjuntos nunca se descargan.
"""


def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode("utf-8", "replace")
    return str(v)


def _parametros(lista) -> dict:
    if not isinstance(lista, list):
        return {}
    return {
        _txt(lista[i]).lower(): _txt(lista[i + 1]) for i in range(0, len(lista) - 1, 2)
    }


def _es_adjunto(parte: list, params: dict) -> bool:
    if "name" in params:
        return True
    # La disposición va tras los campos básicos (7 para texto + líneas; buscamos la lista).
    for v in parte[7:11]:
        if isinstance(v, list) and v and isinstance(v[0], (str, bytes)):
            if _txt(v[0]).lower() == "attachment":
                return True
            if "filename" in _parametros(v[1] if len(v) > 1 else None):
                return True
    return False


def _hojas(estructura, prefijo: str = ""):
    """Recorre en orden (número de parte IMAP, lista de la parte simple)."""
    if not isinstance(estructura, list) or not estructura:
        return
    if isinstance(estructura[0], list):  # multipart: hijos y luego el subtipo
        n = 0
        for hijo in estructura:
            if not isinstance(hijo, list):
                break
            n += 1
            numero = f"{prefijo}.{n}" if prefijo else str(n)
            yield from _hojas(hijo, numero)
        return
    yield (prefijo or "1", estructura)


def parte_de_texto(estructura) -> dict | None:
    """-> {"parte": "1.1", "subtipo": "plain"|"html", "charset", "codificacion", "tamano"}."""
    html = None
    for numero, p in _hojas(estructura):
        if len(p) < 7:
            continue
        tipo, subtipo = _txt(p[0]).lower(), _txt(p[1]).lower()
        if tipo != "text" or subtipo not in ("plain", "html"):
            continue
        params = _parametros(p[2])
        if _es_adjunto(p, params):
            continue
        try:
            tamano = int(_txt(p[6]) or 0)
        except ValueError:
            tamano = 0
        info = {
            "parte": numero,
            "subtipo": subtipo,
            "charset": params.get("charset", "") or "utf-8",
            "codificacion": _txt(p[5]).lower() or "7bit",
            "tamano": tamano,
        }
        if subtipo == "plain":
            return info
        if html is None:
            html = info
    return html
