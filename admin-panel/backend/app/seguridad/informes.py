"""Informes descargables: CSV (para hojas de cálculo) y HTML imprimible (en el navegador, «Imprimir →
Guardar como PDF»). El proyecto no trae biblioteca de PDF y no se añade una pesada por esto.

Funciones puras: reciben los datos ya consultados y devuelven texto.
"""

from __future__ import annotations

import csv
import html
import io

TIPOS_CSV = ("flujo", "accesos", "ips", "cuentas", "alertas", "cumplimiento")

_COLUMNAS = {
    "flujo": ["t", "recibidos", "enviados", "rebotados", "diferidos", "rechazados", "rechazados_filtro",
              "analizados", "spam_rechazado", "spam_marcado", "spam_aplazado", "en_cola"],
    "accesos": ["t", "servicio", "ok", "fallos"],
    "ips": ["ip", "pais", "fallos", "ok", "cuentas", "servicios", "ultima"],
    "cuentas": ["cuenta", "fallos", "ok", "ips", "paises", "ultima"],
    "alertas": ["id", "creada", "regla", "severidad", "estado", "cuenta", "ip", "pais", "servicio", "descripcion",
                "repeticiones", "reconocida_por", "reconocida_en", "cerrada_por", "cerrada_en", "resolucion", "nota"],
    "cumplimiento": ["created_at", "admin_username", "action", "target", "ip_address"],
}


def _celda(v) -> str:
    if isinstance(v, (list, tuple)):
        v = " ".join(str(x) for x in v)
    t = "" if v is None else str(v)
    # Una celda que empieza por = + - @ la interpreta la hoja de cálculo como fórmula (inyección CSV).
    return "'" + t if t[:1] in ("=", "+", "-", "@", "\t", "\r") else t


def a_csv(tipo: str, filas: list) -> str:
    columnas = _COLUMNAS[tipo]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(columnas)
    for f in filas:
        w.writerow([_celda(f.get(c)) for c in columnas])
    return "﻿" + buf.getvalue()  # BOM: Excel abre bien las tildes


def _tabla(titulo: str, columnas: list, filas: list, nombres: dict | None = None) -> str:
    nombres = nombres or {}
    cab = "".join(f"<th>{html.escape(nombres.get(c, c))}</th>" for c in columnas)
    if not filas:
        cuerpo = f'<tr><td colspan="{len(columnas)}" class="vacio">Sin datos en el periodo.</td></tr>'
    else:
        cuerpo = "".join(
            "<tr>" + "".join(f"<td>{html.escape(_celda(f.get(c)).lstrip(chr(39)))}</td>" for c in columnas) + "</tr>"
            for f in filas)
    return f"<h2>{html.escape(titulo)}</h2><table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>"


_ESTILO = """
body{font:13px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1b1b1b;margin:24px;max-width:1100px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 6px;border-bottom:1px solid #ccc;padding-bottom:3px}
.meta{color:#555;margin-bottom:12px}.kpis{display:flex;flex-wrap:wrap;gap:8px}
.kpi{border:1px solid #ccc;border-radius:4px;padding:6px 10px;min-width:120px}.kpi b{display:block;font-size:17px}
table{border-collapse:collapse;width:100%;margin-top:4px}th,td{border:1px solid #ddd;padding:3px 6px;text-align:left;
vertical-align:top}th{background:#f2f2f2}td.vacio{color:#777;text-align:center}
.imprimir{margin:12px 0}@media print{.imprimir{display:none}body{margin:0}h2{break-after:avoid}tr{break-inside:avoid}}
"""


def a_html(titulo: str, periodo: str, generado: str, kpis: dict, secciones: list) -> str:
    """`secciones`: [(título, tipo_de_columnas, filas)]."""
    nombres = {"t": "Periodo", "ok": "Correctos", "fallos": "Fallidos", "cuentas": "Cuentas", "ultima": "Último",
               "servicio": "Servicio", "pais": "País", "ip": "IP", "cuenta": "Cuenta", "creada": "Creada",
               "regla": "Regla", "severidad": "Severidad", "estado": "Estado", "descripcion": "Descripción",
               "created_at": "Fecha", "admin_username": "Administrador", "action": "Acción", "target": "Objetivo",
               "ip_address": "IP"}
    tarjetas = "".join(f'<div class="kpi">{html.escape(k)}<b>{html.escape(str(v))}</b></div>' for k, v in kpis.items())
    cuerpo = "".join(_tabla(t, _COLUMNAS[tipo], filas, nombres) for t, tipo, filas in secciones)
    return (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(titulo)}</title><style>{_ESTILO}</style></head><body>"
        f"<h1>{html.escape(titulo)}</h1><div class=\"meta\">Periodo: {html.escape(periodo)} · Generado: {html.escape(generado)}</div>"
        "<p class=\"imprimir\">Para obtener el PDF: Imprimir (Ctrl+P) → «Guardar como PDF».</p>"
        f"<div class=\"kpis\">{tarjetas}</div>{cuerpo}</body></html>")
