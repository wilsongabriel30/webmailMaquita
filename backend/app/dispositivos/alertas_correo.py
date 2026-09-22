"""Correos de las alertas de telemetría: aviso inmediato a Tecnología y resumen diario a dirección.

Se envía por el relay local de Postfix (127.0.0.1:25, sin autenticación), igual que los recordatorios.
Texto plano y HTML sencillo; sin contenido del teléfono, solo estado del equipo.
"""

import logging
import os
from datetime import datetime
from email.message import EmailMessage
from html import escape

import aiosmtplib

from app.dispositivos.alertas_reglas import NOMBRES

logger = logging.getLogger("dispositivos")
PANEL = os.environ.get("DISP_PANEL_URL", "https://mail.maquita.org:8443/dispositivos")


def _remitente() -> str:
    return f"no-reply@{os.environ.get('MAIL_DOMAIN', 'maquita.org')}"


def _hora(v) -> str:
    if not v:
        return "—"
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            return v
    return v.strftime("%d/%m/%Y %H:%M")


def describir(a: dict) -> str:
    """Una línea en cristiano por alerta (a = fila de disp_alertas con nombre del equipo)."""
    d = a.get("detalle") or {}
    t = a["tipo"]
    if t == "sin_reportar":
        return f"no reporta desde {_hora(d.get('ultimo_contacto'))} (más de {d.get('horas', 24)} h)"
    if t == "bateria_baja":
        return f"batería en {d.get('bateria')} % sin cargar durante más de {d.get('horas', 6)} h"
    if t == "almacenamiento_bajo":
        return f"queda {d.get('libre_pct')} % de almacenamiento ({d.get('libre_gb')} GB)"
    if t == "version_atrasada":
        return f"tiene la app {d.get('tiene')} y la publicada es {d.get('publicada')} (hace {d.get('dias')} días)"
    if t == "mensaje_sin_acuse":
        return f"mensaje urgente sin acuse desde {_hora(d.get('desde'))}"
    if t in ("admin_desactivado", "desinstalacion_intento", "sim_cambiada"):
        return f"evento de seguridad el {_hora(d.get('ultimo'))}, pendiente de revisar en el panel"
    if t == "play_protect_apagado":
        return "Google Play Protect está apagado en el teléfono"
    return t


def _equipo(a: dict) -> str:
    nombre = a.get("nombre") or f"{a.get('fabricante') or ''} {a.get('modelo') or ''}".strip() or f"equipo {a['equipo_id']}"
    cust = a.get("custodio_nombre") or a.get("custodio_email") or "sin custodio"
    return f"{nombre} ({cust})"


async def _enviar(destinos: list[str], asunto: str, texto: str, html: str) -> bool:
    destinos = [d.strip() for d in destinos if d and d.strip()]
    if not destinos:
        logger.warning("alertas_correo_sin_destinatario | asunto=%s", asunto)
        return False
    msg = EmailMessage()
    msg["From"] = _remitente()
    msg["To"] = ", ".join(destinos)
    msg["Subject"] = asunto
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    try:
        await aiosmtplib.send(msg, hostname="127.0.0.1", port=25, timeout=20, start_tls=False)
        logger.info("alertas_correo_enviado | para=%s | asunto=%s", destinos, asunto)
        return True
    except Exception as exc:
        logger.warning("alertas_correo_fallo | para=%s | %s", destinos, exc)
        return False


async def avisar_nuevas(destino: str, alertas: list[dict]) -> bool:
    """Un solo correo con todas las alertas que se abrieron en esta corrida."""
    if not alertas:
        return True
    lineas = [f"- {_equipo(a)}: {NOMBRES.get(a['tipo'], a['tipo'])}: {describir(a)}" for a in alertas]
    texto = ("Alertas nuevas de los teléfonos institucionales:\n\n" + "\n".join(lineas)
             + f"\n\nQué hacer con cada una: pestaña «Telemetría» del panel ({PANEL}) y el runbook de teléfonos."
             + "\nEste aviso se manda una sola vez por alerta; se cierra sola cuando el equipo vuelve a la normalidad.")
    items = "".join(f"<li><b>{escape(_equipo(a))}</b>: {escape(NOMBRES.get(a['tipo'], a['tipo']))} — {escape(describir(a))}</li>" for a in alertas)
    html = (f'<p style="font-size:14px">Alertas nuevas de los teléfonos institucionales:</p><ul style="font-size:14px">{items}</ul>'
            f'<p style="font-size:12px;color:#605e5c">Qué hacer con cada una: <a href="{PANEL}">pestaña «Telemetría» del panel</a> '
            f"y el runbook de teléfonos. Este aviso se manda una sola vez por alerta; se cierra sola cuando el equipo vuelve a la normalidad.</p>")
    n = len(alertas)
    return await _enviar(destino.split(","), f"[Teléfonos] {n} alerta{'s' if n != 1 else ''} nueva{'s' if n != 1 else ''}", texto, html)


async def resumen_diario(destinos: str, totales: dict, abiertas: list[dict]) -> bool:
    lineas = [f"- {_equipo(a)}: {NOMBRES.get(a['tipo'], a['tipo'])}: {describir(a)} (desde {_hora(a['desde'])})" for a in abiertas]
    cab = (f"Equipos: {totales['total']} · reportaron hoy: {totales['hoy']} · en rojo (sin reportar > 24 h): {totales['rojo']} "
           f"· con alertas abiertas: {totales['con_alertas']}")
    texto = "Resumen diario de los teléfonos institucionales\n\n" + cab + "\n\nAlertas abiertas:\n" + ("\n".join(lineas) or "- ninguna") \
        + f"\n\nDetalle: {PANEL} (pestaña «Telemetría»)."
    items = "".join(f"<li><b>{escape(_equipo(a))}</b>: {escape(NOMBRES.get(a['tipo'], a['tipo']))} — {escape(describir(a))} <span style=\"color:#605e5c\">(desde {_hora(a['desde'])})</span></li>" for a in abiertas) or "<li>ninguna</li>"
    html = (f'<p style="font-size:14px"><b>Resumen diario de los teléfonos institucionales</b></p><p style="font-size:14px">{escape(cab)}</p>'
            f'<p style="font-size:14px">Alertas abiertas:</p><ul style="font-size:14px">{items}</ul>'
            f'<p style="font-size:12px;color:#605e5c">Detalle: <a href="{PANEL}">panel, pestaña «Telemetría»</a>.</p>')
    return await _enviar(destinos.split(","), "[Teléfonos] Resumen diario", texto, html)
