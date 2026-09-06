# -*- coding: utf-8 -*-
"""Dominio de las cookies de sesion, seguro para instancias MULTI-DOMINIO.

Si el webmail sirve buzones de varios dominios padre (cada empresa por su host), un
`domain=` fijo hace que el navegador RECHACE la cookie cuando el Domain no corresponde al
host de la peticion. Aqui se deriva el Domain del HOST contra COOKIE_PARENT_DOMAINS.
Sin esa variable -> host-only (retro-compatible y seguro). Reportado por un equipo externo.
"""

import os

from fastapi import Request

_PARENT_DOMAINS = [
    d.strip().lstrip(".").lower()
    for d in os.getenv("COOKIE_PARENT_DOMAINS", "").split(",")
    if d.strip()
]


def dominio_cookie(request: Request):
    host = (request.headers.get("host") or "").split(":")[0].lower()
    for d in _PARENT_DOMAINS:
        if host == d or host.endswith("." + d):
            return "." + d
    return None  # host desconocido o sin lista -> host-only (comportamiento seguro)
