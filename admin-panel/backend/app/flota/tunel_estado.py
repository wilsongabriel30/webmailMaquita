"""Lectura de una apertura de túnel para la auditoría y la cuenta atrás del panel.

Parte de la orden `abrir_tunel_soporte`, de la respuesta del agente (`datos.expira_en`), de la orden de
cierre que la siguió y de la apertura siguiente (abrir otro túnel cierra el anterior).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.flota.tunel_ajustes import MINUTOS_DEF, MINUTOS_MAX

VIVAS = ("pendiente", "entregada", "recibida", "ejecutando")


def _fecha(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else None
    try:
        momento = datetime.fromisoformat(str(valor).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return momento if momento.tzinfo else None


def resumir(fila: dict, ahora: datetime | None = None) -> dict:
    """Añade a la fila: situacion, abierto_en, expira_en, cerrado_en, cierre, duracion_s."""
    ahora = ahora or datetime.now(timezone.utc)
    d = dict(fila)
    parametros = d.get("parametros") if isinstance(d.get("parametros"), dict) else {}
    datos = d.get("datos") if isinstance(d.get("datos"), dict) else {}
    extra = {
        "abierto_en": None,
        "expira_en": None,
        "cerrado_en": None,
        "cierre": None,
        "duracion_s": None,
    }
    cierre_vivo = d.get("cierre_estado") in VIVAS and not d.get("cierre_caducado")
    if d.get("estado") == "ok" and d.get("resultado_en"):
        abierto = d["resultado_en"]
        minutos = (
            parametros.get("minutos")
            if isinstance(parametros.get("minutos"), int)
            else MINUTOS_DEF
        )
        expira = _fecha(datos.get("expira_en"))
        if not expira or not abierto < expira <= abierto + timedelta(
            minutes=MINUTOS_MAX + 5
        ):
            expira = abierto + timedelta(minutes=minutos)
        finales = [(expira, "automático")]
        if d.get("cierre_estado") == "ok" and d.get("cierre_en"):
            finales.append((d["cierre_en"], "orden de cierre"))
        if d.get("reemplazado_en"):
            finales.append((d["reemplazado_en"], "nueva apertura"))
        fin, motivo = min(finales, key=lambda par: par[0])
        extra.update(abierto_en=abierto, expira_en=expira)
        if fin <= ahora:
            extra.update(situacion="cerrado", cerrado_en=fin, cierre=motivo)
        else:
            extra["situacion"] = "cierre_solicitado" if cierre_vivo else "abierto"
        extra["duracion_s"] = max(0, int((min(fin, ahora) - abierto).total_seconds()))
    elif d.get("caducada"):
        extra["situacion"] = "caducada"
    elif d.get("estado") in ("pendiente", "entregada"):
        extra["situacion"] = "solicitado"
    elif d.get("estado") in ("recibida", "ejecutando"):
        extra["situacion"] = "abriendo"
    else:
        extra["situacion"] = "no_abierto"
    d.update(extra)
    return d
