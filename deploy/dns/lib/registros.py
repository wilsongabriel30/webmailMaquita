"""Validación y escritura de registros DNS.

Cada registro es {"id", "nombre", "tipo", "valor", "ttl", "prioridad", "sistema"}:
- nombre: relativo a la zona («@» es la propia zona, «www», «_dmarc», «*.blog»).
- valor: según el tipo (IP, nombre de destino, texto, «peso puerto destino» en SRV,
  «etiqueta valor» en CAA).
- sistema: lo creó el asistente; se puede editar, pero el panel avisa.
"""

import ipaddress
import re
import secrets

from comun import ErrorDns

TIPOS = ("A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA", "NS")
RE_ETIQUETA = r"(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?)"
RE_NOMBRE = re.compile(rf"^(?:@|(?:\*\.)?{RE_ETIQUETA}(?:\.{RE_ETIQUETA})*|\*)$")
RE_DESTINO = re.compile(rf"^(?:@|{RE_ETIQUETA}(?:\.{RE_ETIQUETA})*\.?)$")
RE_ZONA = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def zona_valida(zona):
    if not isinstance(zona, str) or not RE_ZONA.match(zona):
        raise ErrorDns("nombre de zona no válido")
    return zona


def _destino(valor, zona):
    """Nombre de destino, siempre con punto final.

    Regla simple y predecible: «@» es la zona; sin ningún punto («mail») es relativo a la zona
    (mail.<zona>); con punto («ghs.google.com» o «mail.otra.org.») es un nombre completo.
    """
    v = valor.strip().lower()
    if not RE_DESTINO.match(v):
        raise ErrorDns(f"destino no válido: {valor}")
    if v == "@":
        return zona + "."
    if "." not in v.rstrip("."):
        return f"{v.rstrip('.')}.{zona}."
    return v if v.endswith(".") else v + "."


def normalizar(reg, zona):
    """Valida y devuelve el registro limpio (lanza ErrorDns si no vale)."""
    tipo = str(reg.get("tipo", "")).upper()
    if tipo not in TIPOS:
        raise ErrorDns(f"tipo de registro no admitido: {tipo}")
    nombre = str(reg.get("nombre", "@")).strip().lower() or "@"
    if nombre.endswith("." + zona):
        nombre = nombre[: -len(zona) - 1]
    if nombre == zona:
        nombre = "@"
    if not RE_NOMBRE.match(nombre):
        raise ErrorDns(f"nombre no válido: {nombre}")
    ttl = int(reg.get("ttl") or 3600)
    if not 60 <= ttl <= 86400:
        raise ErrorDns("el TTL debe estar entre 60 y 86400 segundos")
    valor = str(reg.get("valor", "")).strip()
    prioridad = reg.get("prioridad")
    if tipo == "A":
        try:
            if ipaddress.ip_address(valor).version != 4:
                raise ValueError
        except ValueError:
            raise ErrorDns(f"IPv4 no válida: {valor}")
    elif tipo == "AAAA":
        try:
            if ipaddress.ip_address(valor).version != 6:
                raise ValueError
        except ValueError:
            raise ErrorDns(f"IPv6 no válida: {valor}")
    elif tipo in ("CNAME", "NS"):
        if tipo == "CNAME" and nombre == "@":
            raise ErrorDns("la propia zona (@) no puede ser CNAME")
        valor = _destino(valor, zona)
    elif tipo == "MX":
        valor = _destino(valor, zona)
        prioridad = int(prioridad if prioridad is not None else 10)
        if not 0 <= prioridad <= 65535:
            raise ErrorDns("prioridad MX fuera de rango")
    elif tipo == "TXT":
        if not 1 <= len(valor) <= 2048 or re.search(r"[\x00-\x1f\x7f]", valor):
            raise ErrorDns("el texto debe tener entre 1 y 2048 caracteres imprimibles")
    elif tipo == "SRV":
        partes = valor.split()
        if len(partes) != 3 or not all(p.isdigit() for p in partes[:2]):
            raise ErrorDns("SRV: escriba «peso puerto destino» (p. ej. «1 443 mail»)")
        peso, puerto = int(partes[0]), int(partes[1])
        if not (0 <= peso <= 65535 and 1 <= puerto <= 65535):
            raise ErrorDns("SRV: peso o puerto fuera de rango")
        prioridad = int(prioridad if prioridad is not None else 0)
        valor = f"{peso} {puerto} {_destino(partes[2], zona)}"
    elif tipo == "CAA":
        m = re.match(r'^(?:(0|128)\s+)?(issue|issuewild|iodef)\s+"?([^"\s]{1,200})"?$', valor)
        if not m:
            raise ErrorDns('CAA: escriba «issue letsencrypt.org» (etiqueta y valor)')
        valor = f'{m.group(1) or 0} {m.group(2)} "{m.group(3)}"'
    return {
        "id": reg.get("id") or secrets.token_hex(4),
        "nombre": nombre,
        "tipo": tipo,
        "valor": valor,
        "ttl": ttl,
        "prioridad": prioridad if tipo in ("MX", "SRV") else None,
        "sistema": bool(reg.get("sistema", False)),
    }


def comprobar_conjunto(registros):
    """Reglas entre registros: un CNAME no convive con otros datos del mismo nombre."""
    por_nombre = {}
    for r in registros:
        por_nombre.setdefault(r["nombre"], []).append(r["tipo"])
    for nombre, tipos in por_nombre.items():
        if "CNAME" in tipos and len(tipos) > 1:
            raise ErrorDns(f"«{nombre}» tiene un CNAME y otros registros: un CNAME debe estar solo")


def _txt(valor):
    """Texto en trozos de 255 bytes, con comillas y barras escapadas."""
    limpio = valor.replace("\\", "\\\\").replace('"', '\\"')
    trozos = [limpio[i : i + 250] for i in range(0, len(limpio), 250)]
    return " ".join(f'"{t}"' for t in trozos)


def linea(r):
    """Línea del archivo de zona de BIND."""
    if r["tipo"] == "TXT":
        dato = _txt(r["valor"])
    elif r["tipo"] in ("MX", "SRV"):
        dato = f"{r['prioridad']} {r['valor']}"
    else:
        dato = r["valor"]
    return f"{r['nombre']:<24} {r['ttl']:>6} IN {r['tipo']:<6} {dato}"
