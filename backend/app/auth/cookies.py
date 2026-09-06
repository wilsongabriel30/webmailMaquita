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


def poner_cookies_sesion(response, request, sesion: dict) -> None:
    """Cookies de una sesión recién creada o renovada. `sesion` trae access, refresh_raw y,
    opcionalmente, abs_exp / refresh_expires_at para acotar los max_age (F-04)."""
    from datetime import datetime, timezone

    from app.config import get_settings

    s = get_settings()
    ahora = datetime.now(timezone.utc)
    max_access = s.access_token_expire_minutes * 60
    abs_exp = sesion.get("abs_exp")
    if abs_exp is not None:
        max_access = max(1, min(max_access, int((abs_exp - ahora).total_seconds())))
    max_refresh = s.refresh_token_expire_days * 86400
    rexp = sesion.get("refresh_expires_at")
    if rexp is not None:
        max_refresh = max(1, min(max_refresh, int((rexp - ahora).total_seconds())))
    dom = dominio_cookie(request)
    response.set_cookie(
        key="access_token",
        value=sesion["access"],
        httponly=True,
        secure=True,
        samesite="strict",
        domain=dom,
        max_age=max_access,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=sesion["refresh_raw"],
        httponly=True,
        secure=True,
        samesite="strict",
        domain=dom,
        max_age=max_refresh,
        path="/api/auth/refresh",
    )


def quitar_cookies_sesion(response, request) -> None:
    dom = dominio_cookie(request)
    response.delete_cookie("access_token", domain=dom, path="/")
    response.delete_cookie("refresh_token", domain=dom, path="/api/auth/refresh")
