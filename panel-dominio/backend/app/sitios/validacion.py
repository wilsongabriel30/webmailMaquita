"""Validaciones de forma de lo que llega para los sitios. El intermediario y maquita-sitios
vuelven a validarlo todo; aquí se rechaza pronto y con un texto claro. Sin base de datos."""

import re

from fastapi import HTTPException

RE_APLICACION = re.compile(r"^[a-z0-9-]{2,30}$")  # el intermediario comprueba que esté en el catálogo
RE_CORREO = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_TAREA = re.compile(r"^[0-9a-f]{8}$")
RE_BASE = re.compile(r"^[wx]_[a-z0-9]+(_[0-9a-f]{4})?$")
RE_BASE_ADICIONAL = re.compile(r"^x_[a-z0-9]+_[0-9a-f]{4}$")
RE_VERSION_PHP = re.compile(r"^[578]\.[0-9]$")
RE_VERSION_COPIA = re.compile(r"^\d{8}-\d{6}-\d{3}$")
RE_REGISTRO = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
TIPOS_DNS = ("A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA")


def correo(valor) -> str:
    valor = str(valor or "").strip().lower()
    if not RE_CORREO.match(valor):
        raise HTTPException(400, "Correo no válido")
    return valor


def aplicacion(valor) -> str:
    valor = str(valor or "").strip().lower()
    if not RE_APLICACION.match(valor):
        raise HTTPException(400, "Aplicación no disponible")
    return valor


def titulo(valor) -> str:
    valor = str(valor or "").strip()
    if not 1 <= len(valor) <= 100 or _CONTROL.search(valor) or re.search(r"[<>]", valor):
        raise HTTPException(400, "El nombre del sitio debe tener entre 1 y 100 caracteres, sin < ni >")
    return valor


def con_forma(regex: re.Pattern, valor, mensaje: str) -> str:
    valor = str(valor or "").strip()
    if not regex.match(valor):
        raise HTTPException(400, mensaje)
    return valor


def ruta_archivo(valor) -> str:
    """Ruta relativa dentro de la carpeta del sitio; el intermediario la encierra además."""
    valor = str(valor or "").strip().lstrip("/")
    if not valor or len(valor) > 300 or ".." in valor.split("/") or _CONTROL.search(valor) or "\\" in valor:
        raise HTTPException(400, "Ruta no válida")
    return valor


def trabajos(lista) -> list[dict]:
    if not isinstance(lista, list):
        raise HTTPException(400, "Lista de trabajos no válida")
    if len(lista) > 20:
        raise HTTPException(400, "Se admiten hasta 20 trabajos por sitio")
    limpios = []
    for t in lista:
        if not isinstance(t, dict):
            raise HTTPException(400, "Trabajo no válido")
        horario, orden = str(t.get("horario") or "").strip(), str(t.get("orden") or "").strip()
        if not horario or len(horario) > 100 or _CONTROL.search(horario):
            raise HTTPException(400, "Horario no válido")
        if not orden or len(orden) > 1000 or _CONTROL.search(orden):
            raise HTTPException(400, "La orden debe ocupar una sola línea (máximo 1000 caracteres)")
        ident = t.get("id")
        if ident is not None and not RE_TAREA.match(str(ident)):
            raise HTTPException(400, "Trabajo no válido")
        limpios.append({"id": ident, "horario": horario, "orden": orden,
                        "descripcion": _CONTROL.sub(" ", str(t.get("descripcion") or "")).strip()[:80],
                        "activo": bool(t.get("activo", True))})
    return limpios


def ajustes_php(valor) -> dict:
    if not isinstance(valor, dict) or len(valor) > 40:
        raise HTTPException(400, "Ajustes de PHP no válidos")
    limpios = {}
    for clave, v in valor.items():
        clave, v = str(clave), str(v if v is not None else "").strip()
        if not re.fullmatch(r"[a-z_.]{2,40}", clave) or len(v) > 100 or _CONTROL.search(v):
            raise HTTPException(400, f"Ajuste de PHP no válido: {clave[:40]}")
        limpios[clave] = v
    return limpios


def registro_dns(valor) -> dict:
    """Solo los campos de un registro; los protegidos (correo, NS…) los rechaza el intermediario."""
    if not isinstance(valor, dict):
        raise HTTPException(400, "Registro no válido")
    tipo = str(valor.get("tipo") or "").strip().upper()
    if tipo not in TIPOS_DNS:
        raise HTTPException(400, "Tipo de registro no admitido desde el portal")
    nombre = str(valor.get("nombre") or "@").strip().lower()
    contenido = str(valor.get("valor") or "").strip()
    if len(nombre) > 253 or _CONTROL.search(nombre) or not contenido or len(contenido) > 2048 or _CONTROL.search(contenido):
        raise HTTPException(400, "Nombre o valor del registro no válido")
    try:
        ttl = int(valor.get("ttl") or 3600)
        prioridad = valor.get("prioridad")
        prioridad = None if prioridad in (None, "") else int(prioridad)
    except (TypeError, ValueError):
        raise HTTPException(400, "TTL o prioridad no válidos")
    if not 60 <= ttl <= 86400:
        raise HTTPException(400, "El TTL debe estar entre 60 y 86400 segundos")
    return {"nombre": nombre, "tipo": tipo, "valor": contenido, "ttl": ttl, "prioridad": prioridad}
