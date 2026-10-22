"""Avisos por correo de las alertas: el mismo mecanismo que los vigilantes del servidor
(deploy/vigilantes/lib-avisos.sh → sendmail). Destinos, por orden: ORG_CORREOS_AVISOS de
/etc/maquita-mail/organizacion.env, el aviso del panel (Protección de salida) y postmaster@dominio.

Escalamiento sencillo: una alerta alta que sigue «abierta» (nadie la reconoció) pasadas
`escalar_tras_horas` horas se vuelve a avisar una sola vez, marcada como ESCALADA, también a
ORG_CORREOS_ESCALAMIENTO si existe.
"""

from __future__ import annotations

import logging
import os
import subprocess

_log = logging.getLogger(__name__)
LIB_AVISOS = os.getenv("SEG_LIB_AVISOS", "/usr/local/lib/maquita-vigilantes/lib-avisos.sh")
ORDEN = {"baja": 0, "media": 1, "alta": 2}
_ENVIO = '. "$1" && vig_enviar "$2" "${3:-$(vig_destinos)}"'


def merece_aviso(severidad: str, minima: str) -> bool:
    return ORDEN.get(severidad, 0) >= ORDEN.get(minima, 2)


def componer_resumen(nuevas, servidor: str, url_panel: str = "") -> tuple:
    """(asunto, cuerpo) del aviso de alertas nuevas. `nuevas`: [(id, Hallazgo)]."""
    altas = sum(1 for _, h in nuevas if h.severidad == "alta")
    asunto = f"[Seguridad] {len(nuevas)} alerta(s) nueva(s)" + (f", {altas} alta(s)" if altas else "") + f" en {servidor}"
    lineas = ["Los tableros de seguridad detectaron:", ""]
    for i, h in nuevas[:20]:
        lineas.append(f"  #{i} [{h.severidad.upper()}] {h.descripcion}")
    if len(nuevas) > 20:
        lineas.append(f"  … y {len(nuevas) - 20} más.")
    lineas += ["", "Revíselas y reconózcalas en el panel: Seguridad → Tableros → Anomalías"
               + (f" ({url_panel})" if url_panel else "") + ".",
               "Si una alta sigue sin reconocer, se volverá a avisar como escalada."]
    return asunto, "\n".join(lineas)


def componer_escalamiento(alertas, horas: int, servidor: str) -> tuple:
    """`alertas`: filas (dict) de seg_alertas abiertas y altas sin escalar."""
    asunto = f"[Seguridad] ESCALADA: {len(alertas)} alerta(s) alta(s) sin reconocer en {servidor}"
    lineas = [f"Estas alertas altas llevan más de {horas} h abiertas y nadie las ha reconocido:", ""]
    for a in alertas[:20]:
        lineas.append(f"  #{a['id']} ({a['creada']:%Y-%m-%d %H:%M}) {a['descripcion']}")
    lineas += ["", "Reconózcalas (o ciérrelas como falso positivo) en Seguridad → Tableros → Anomalías."]
    return asunto, "\n".join(lineas)


def enviar(asunto: str, cuerpo: str, destinos: list, lib: str = LIB_AVISOS) -> bool:
    if not os.path.isfile(lib):
        _log.warning("Sin %s: el aviso «%s» queda solo en el panel", lib, asunto)
        return False
    try:
        r = subprocess.run(["bash", "-c", _ENVIO, "_", lib, asunto, " ".join(destinos)],
                           input=cuerpo, text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        _log.warning("No se pudo enviar el aviso: %s", e)
        return False
    if r.returncode != 0:
        _log.warning("El aviso no salió (código %s): %s", r.returncode, (r.stderr or "")[-300:])
    return r.returncode == 0


def cupo(estado: dict | None, hora_actual: str, maximo: int) -> tuple:
    """Límite de avisos por hora: (se puede enviar, estado nuevo)."""
    e = estado if estado and estado.get("hora") == hora_actual else {"hora": hora_actual, "n": 0}
    if e["n"] >= maximo:
        return False, e
    return True, {"hora": hora_actual, "n": e["n"] + 1}
