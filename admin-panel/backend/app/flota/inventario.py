"""Inventario de Flota Maquita: equipos enrolados + lo que ya reporta la telemetría de la app
(`app_telemetria`, 60 días): última conexión, persona, versión, IP, Windows y estado del SSH de soporte.
También lista los equipos con Teams Maquita que reportan pero NO están enrolados, para darlos de alta.
"""

from __future__ import annotations

from datetime import datetime, timezone

SQL = """
WITH tel AS (
    SELECT DISTINCT ON (upper(equipo)) upper(equipo) AS nombre, recibido AS visto_en, usuario, version, ip
      FROM app_telemetria WHERE equipo <> '' AND recibido > NOW() - interval '60 days'
     ORDER BY upper(equipo), recibido DESC
), win AS (
    SELECT DISTINCT ON (upper(equipo)) upper(equipo) AS nombre, split_part(detalle, ' · ', 1) AS windows_tel
      FROM app_telemetria WHERE evento = 'app_inicio' AND equipo <> '' AND recibido > NOW() - interval '60 days'
     ORDER BY upper(equipo), recibido DESC
), ssh AS (
    SELECT DISTINCT ON (upper(equipo)) upper(equipo) AS nombre, evento AS ssh_estado, detalle AS ssh_detalle,
           recibido AS ssh_en
      FROM app_telemetria WHERE evento LIKE 'ssh_soporte%' AND equipo <> '' AND recibido > NOW() - interval '180 days'
     ORDER BY upper(equipo), recibido DESC
), vivas AS (
    SELECT equipo_id, count(*) AS ordenes_vivas FROM flota_ordenes
     WHERE estado IN ('pendiente', 'entregada', 'recibida', 'ejecutando') AND caduca_en > NOW() GROUP BY equipo_id
)
SELECT e.equipo_id::text AS equipo_id, COALESCE(e.nombre, tel.nombre) AS nombre, e.etiqueta, e.estado,
       e.version_app, e.windows, e.enrolado_en, e.reenrolado_en, e.ultimo_sondeo, e.ultima_ip, e.inventario_en,
       e.retirado_en, e.motivo_retiro,
       tel.visto_en, tel.usuario, tel.version AS version_tel, tel.ip AS ip_tel, win.windows_tel,
       ssh.ssh_estado, ssh.ssh_detalle, ssh.ssh_en, COALESCE(vivas.ordenes_vivas, 0) AS ordenes_vivas
  FROM flota_equipos e
  FULL OUTER JOIN tel ON tel.nombre = upper(e.nombre)
  LEFT JOIN win ON win.nombre = COALESCE(upper(e.nombre), tel.nombre)
  LEFT JOIN ssh ON ssh.nombre = COALESCE(upper(e.nombre), tel.nombre)
  LEFT JOIN vivas ON vivas.equipo_id = e.equipo_id
 ORDER BY (e.equipo_id IS NULL), e.estado NULLS LAST, COALESCE(e.nombre, tel.nombre)
"""


def _semaforo(ultimo) -> str:
    if not ultimo:
        return "gris"
    horas = (datetime.now(timezone.utc) - ultimo).total_seconds() / 3600
    return "verde" if horas < 1 else "amarillo" if horas < 24 else "rojo"


def fila(f) -> dict:
    d = dict(f)
    d["enrolado"] = d["equipo_id"] is not None
    d["semaforo_agente"] = _semaforo(d["ultimo_sondeo"]) if d["enrolado"] else "gris"
    d["semaforo_app"] = _semaforo(d["visto_en"])
    d["ssh"] = {"ssh_soporte_ok": "activo", "ssh_soporte_error": "error"}.get(d.get("ssh_estado") or "", "pendiente" if d.get("ssh_estado") else "sin dato")
    return d


async def listar(db) -> dict:
    filas = [fila(f) for f in await db.fetch(SQL)]
    enrolados = [f for f in filas if f["enrolado"] and f["estado"] == "activo"]
    return {
        "totales": {
            "enrolados": len(enrolados),
            "agente_hoy": sum(1 for f in enrolados if f["semaforo_agente"] in ("verde", "amarillo")),
            "sin_enrolar": sum(1 for f in filas if not f["enrolado"]),
            "retirados": sum(1 for f in filas if f["enrolado"] and f["estado"] == "retirado"),
            "ssh_activo": sum(1 for f in enrolados if f["ssh"] == "activo"),
        },
        "equipos": filas,
    }
