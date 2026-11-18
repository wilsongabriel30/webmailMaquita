"""Qué se anota cuando una solicitud se rechaza por validación (400 «Solicitud inválida»).

Al cliente se le sigue respondiendo un texto genérico, pero el registro tiene que decir QUÉ
campo falló y POR QUÉ: sin eso no se puede explicar a una persona por qué su correo no salió.

Nunca se anota el valor recibido (puede ser el cuerpo de un correo, una dirección o una clave):
solo el nombre del campo, el tipo de fallo y, si es texto o lista, su longitud.
"""

from __future__ import annotations

import logging

log = logging.getLogger("app.rechazo_validacion")

MAX_FALLOS = 8


def _campo(ubicacion) -> str:
    return ".".join(str(p) for p in (ubicacion or ()) if p != "body")[:80] or "(cuerpo)"


def _medida(valor) -> str:
    if isinstance(valor, (str, bytes, list, tuple, dict)):
        return f" largo={len(valor)}"
    return ""


def resumen(errores) -> str:
    """«campo: tipo (motivo) largo=N; …» de los primeros fallos, sin ningún valor."""
    partes = []
    for e in list(errores or [])[:MAX_FALLOS]:
        tipo = str(e.get("type", "?"))[:40]
        motivo = " ".join(str(e.get("msg", "")).split())[:90]
        partes.append(
            f"{_campo(e.get('loc'))}: {tipo} ({motivo}){_medida(e.get('input'))}"
        )
    extra = len(list(errores or [])) - len(partes)
    if extra > 0:
        partes.append(f"y {extra} más")
    return "; ".join(partes) or "sin detalle"


def anotar(request, exc) -> None:
    """Deja el fallo en el registro. Nunca rompe la respuesta."""
    try:
        usuario = getattr(getattr(request, "state", None), "username", None) or "-"
        log.warning(
            "SOLICITUD_INVALIDA metodo=%s ruta=%s usuario=%s fallos=%s",
            request.method,
            request.url.path,
            usuario,
            resumen(exc.errors()),
        )
    except Exception:  # noqa: BLE001
        pass
