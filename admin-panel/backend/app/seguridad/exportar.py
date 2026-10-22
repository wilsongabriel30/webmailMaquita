"""Registro JSON de seguridad para Wazuh (u otro SIEM): /var/log/maquita/seguridad.json.

Una línea JSON por evento: alertas de anomalía, acciones de la auditoría del panel (incluidos los
inicios de sesión y lo de cumplimiento) y la actividad de cumplimiento del webmail. Lo lee el agente
Wazuh (deploy/wazuh/) con su decodificador JSON; las reglas propias están en deploy/wazuh/manager/.

Solo se escribe si hay agente Wazuh (/var/ossec) o SEG_EXPORTAR_JSON=1. Sin contenidos de correo ni
detalles de la auditoría (pueden llevar datos de configuración): quién, qué, sobre qué, cuándo y
desde dónde.
"""

from __future__ import annotations

import json
import os

RUTA = os.getenv("SEG_JSON", "/var/log/maquita/seguridad.json")


def activo() -> bool:
    v = os.getenv("SEG_EXPORTAR_JSON", "")
    if v in ("0", "no", "false"):
        return False
    return v in ("1", "si", "sí", "true") or os.path.isdir("/var/ossec")


def evento_alerta(id_, h) -> dict:
    return {"origen": "maquita", "tipo": "alerta", "fecha": h.momento.isoformat(), "id": id_, "regla": h.regla,
            "severidad": h.severidad, "cuenta": h.cuenta, "ip": h.ip, "pais": h.pais, "servicio": h.servicio,
            "descripcion": h.descripcion}


def evento_panel(fila) -> dict:
    return {"origen": "maquita", "tipo": "auditoria_panel", "fecha": fila["created_at"].isoformat() if fila["created_at"] else "",
            "id": fila["id"], "accion": fila["action"], "administrador": fila["admin_username"] or "",
            "objetivo": (fila["target"] or "")[:255], "ip": fila["ip_address"] or ""}


def evento_webmail(fila) -> dict:
    return {"origen": "maquita", "tipo": "actividad_webmail", "fecha": fila["created_at"].isoformat() if fila["created_at"] else "",
            "id": fila["id"], "accion": fila["action"], "categoria": fila["category"], "cuenta": fila["username"] or "",
            "riesgo": fila["risk_level"] or "", "ip": str(fila["ip_address"] or "")}


def escribir(eventos, ruta: str = RUTA) -> int:
    if not eventos:
        return 0
    os.makedirs(os.path.dirname(ruta), mode=0o750, exist_ok=True)
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
    if nuevo:
        os.chmod(ruta, 0o640)
    return len(eventos)
