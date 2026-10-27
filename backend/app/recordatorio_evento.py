"""Contenido del recordatorio de un evento: enlace de la reunión, lugar y horario (27/10/2026).

Antes el recordatorio solo decía «📅 <título> empieza a las HH:MM». Quien lo recibía por correo
no tenía el enlace de la reunión (Meet, Zoom, Teams…), que vive en el lugar o la descripción
del evento, y tenía que ir a buscarlo al calendario.
"""

import html
import re

_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
# Servicios de videollamada: si hay varios enlaces, se prefiere uno de estos.
_REUNION = re.compile(
    r"meet\.google\.com|zoom\.us|teams\.microsoft\.com|teams\.live\.com|//meet\.|"
    r"jitsi|whereby\.com|webex\.com|gotomeeting|meet\.jit\.si",
    re.IGNORECASE,
)
# Enlaces de ayuda o de marcado telefónico que trae la descripción de Google y no sirven para entrar.
_RUIDO = re.compile(
    r"support\.google\.com|tel\.meet|accounts\.google\.com", re.IGNORECASE
)


def enlace_reunion(location: str | None, description: str | None) -> str:
    """El enlace para entrar a la reunión: primero uno de videollamada, si no el primero que haya."""
    urls = [
        u.rstrip(".,;") for u in _URL.findall(f"{location or ''}\n{description or ''}")
    ]
    urls = [u for u in urls if not _RUIDO.search(u)]
    for u in urls:
        if _REUNION.search(u):
            return u
    return urls[0] if urls else ""


def contenido(
    titulo: str,
    hora_inicio: str,
    hora_fin: str,
    location: str | None,
    description: str | None,
) -> tuple[str, str]:
    """(texto, html) del recordatorio. El texto sirve también para el aviso en pantalla."""
    enlace = enlace_reunion(location, description)
    lugar = (location or "").strip()
    horario = f"{hora_inicio}–{hora_fin}" if hora_fin else hora_inicio
    lineas = [f"📅 {titulo} empieza a las {hora_inicio}", f"Horario: {horario}"]
    if enlace:
        lineas.append(f"Entrar a la reunión: {enlace}")
    if lugar and lugar != enlace:
        lineas.append(f"Lugar: {lugar}")
    texto = "\n".join(lineas)

    e = html.escape
    partes = [
        f'<p style="font-size:15px;margin:0 0 8px"><strong>📅 {e(titulo)}</strong></p>',
        f'<p style="margin:0 0 8px">Empieza a las <strong>{e(hora_inicio)}</strong> (horario: {e(horario)}).</p>',
    ]
    if enlace:
        partes.append(
            f'<p style="margin:12px 0"><a href="{e(enlace, quote=True)}" '
            'style="background:#0f6cbd;color:#fff;padding:9px 18px;border-radius:4px;'
            f'text-decoration:none;font-weight:600">Entrar a la reunión</a></p>'
            f'<p style="margin:0 0 8px;font-size:12px;color:#605e5c">{e(enlace)}</p>'
        )
    if lugar and lugar != enlace:
        partes.append(f'<p style="margin:0 0 8px">Lugar: {e(lugar)}</p>')
    return texto, "".join(partes)
