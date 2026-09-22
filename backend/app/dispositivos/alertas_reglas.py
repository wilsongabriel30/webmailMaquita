"""Reglas de alerta de la telemetría de los teléfonos (se evalúan cada 15 min).

Cada regla devuelve las condiciones que están ocurriendo AHORA como {equipo_id, tipo, detalle}. El
trabajo (`alertas_tarea`) abre una alerta nueva en `disp_alertas` cuando aparece una condición que no
estaba abierta, y cierra (`hasta`) las que dejaron de cumplirse. Así el mismo problema se avisa una vez.

Umbrales: `disp_config.alertas` (editables desde el panel). Solo telemetría del equipo, nunca contenido.
"""

from app.dispositivos import version_publicada

UMBRALES_BASE = {
    "activo": True,
    "sin_reportar_horas": 24,
    "bateria_pct": 15,
    "bateria_horas": 6,
    "almacenamiento_pct": 10,
    "version_atrasada_dias": 7,
    "acuse_horas": 2,
    "correo_ti": "",
    "resumen_diario_para": "",
    "resumen_hora": "07:30",
}

NOMBRES = {
    "sin_reportar": "Sin reportar",
    "bateria_baja": "Batería baja sostenida",
    "almacenamiento_bajo": "Almacenamiento casi lleno",
    "version_atrasada": "App desactualizada",
    "admin_desactivado": "Quitaron a la app como administradora",
    "desinstalacion_intento": "Intento de desinstalar la app",
    "sim_cambiada": "Cambio de SIM",
    "play_protect_apagado": "Play Protect apagado",
    "mensaje_sin_acuse": "Mensaje urgente sin acuse",
}

_ACTIVOS = "estado IN ('activo', 'perdido')"


def _n(v, base):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return base


async def evaluar(db, umbrales: dict) -> list[dict]:
    u = {**UMBRALES_BASE, **(umbrales or {})}
    out: list[dict] = []

    # 1) Sin reportar más de N horas (o nunca).
    horas = _n(u["sin_reportar_horas"], 24)
    for f in await db.fetch(
        f"SELECT id, ultimo_contacto FROM disp_equipos WHERE {_ACTIVOS} AND "
        "(ultimo_contacto IS NULL OR ultimo_contacto < NOW() - make_interval(hours => $1))",
        horas,
    ):
        out.append({"equipo_id": f["id"], "tipo": "sin_reportar",
                    "detalle": {"ultimo_contacto": f["ultimo_contacto"].isoformat() if f["ultimo_contacto"] else None, "horas": horas}})

    # 2) Batería < X % sostenida > N horas sin cargar: ningún latido de la ventana la vio por encima.
    pct, bh = _n(u["bateria_pct"], 15), _n(u["bateria_horas"], 6)
    for f in await db.fetch(
        f"""SELECT e.id, e.bateria FROM disp_equipos e WHERE {_ACTIVOS} AND e.bateria IS NOT NULL AND e.bateria < $1
              AND COALESCE(e.cargando, false) = false
              AND e.ultimo_contacto > NOW() - make_interval(hours => $2)
              AND EXISTS (SELECT 1 FROM disp_latidos l WHERE l.equipo_id = e.id
                          AND l.recibido_en BETWEEN NOW() - make_interval(hours => $2) - interval '20 minutes'
                                                AND NOW() - make_interval(hours => $2) + interval '20 minutes')
              AND NOT EXISTS (SELECT 1 FROM disp_latidos l WHERE l.equipo_id = e.id
                          AND l.recibido_en > NOW() - make_interval(hours => $2)
                          AND ((l.datos->>'bateria')::int >= $1 OR (l.datos->>'cargando')::boolean = true))""",
        pct, bh,
    ):
        out.append({"equipo_id": f["id"], "tipo": "bateria_baja", "detalle": {"bateria": f["bateria"], "horas": bh}})

    # 3) Almacenamiento libre < X %.
    apct = _n(u["almacenamiento_pct"], 10)
    for f in await db.fetch(
        f"""SELECT id, almacenamiento_libre, almacenamiento_total FROM disp_equipos WHERE {_ACTIVOS}
              AND almacenamiento_total > 0 AND almacenamiento_libre IS NOT NULL
              AND almacenamiento_libre * 100.0 / almacenamiento_total < $1""",
        apct,
    ):
        libre = round(f["almacenamiento_libre"] * 100 / f["almacenamiento_total"], 1)
        out.append({"equipo_id": f["id"], "tipo": "almacenamiento_bajo",
                    "detalle": {"libre_pct": libre, "libre_gb": round(f["almacenamiento_libre"] / 1073741824, 1)}})

    # 4) Versión de la app atrasada más de N días desde que se publicó la vigente.
    pub = version_publicada.leer()
    dias = version_publicada.dias_publicada(pub)
    if pub and dias is not None and dias > _n(u["version_atrasada_dias"], 7):
        for f in await db.fetch(f"SELECT id, version_app FROM disp_equipos WHERE {_ACTIVOS} AND version_app IS NOT NULL"):
            if version_publicada.atrasada(f["version_app"], pub):
                out.append({"equipo_id": f["id"], "tipo": "version_atrasada",
                            "detalle": {"tiene": f["version_app"], "publicada": pub["versionName"], "dias": dias}})

    # 5) Eventos de seguridad sin revisar (últimos 7 días): se cierran al marcarlos revisados en el panel.
    for f in await db.fetch(
        f"""SELECT e.id, ev.tipo, array_agg(ev.id ORDER BY ev.recibido_en DESC) AS eventos, max(ev.recibido_en) AS ultimo
              FROM disp_eventos ev JOIN disp_equipos e ON e.id = ev.equipo_id
             WHERE {_ACTIVOS} AND ev.visto_en IS NULL AND ev.recibido_en > NOW() - interval '7 days'
               AND ev.tipo IN ('admin_desactivado', 'desinstalacion_intento', 'sim_cambiada')
             GROUP BY e.id, ev.tipo"""
    ):
        out.append({"equipo_id": f["id"], "tipo": f["tipo"],
                    "detalle": {"eventos": list(f["eventos"])[:20], "ultimo": f["ultimo"].isoformat()}})

    # 6) Play Protect apagado (solo cuando el teléfono lo reporta).
    for f in await db.fetch(f"SELECT id FROM disp_equipos WHERE {_ACTIVOS} AND play_protect = false"):
        out.append({"equipo_id": f["id"], "tipo": "play_protect_apagado", "detalle": {}})

    # 7) Mensaje urgente con acuse pendiente más de N horas (y aún vigente).
    ah = _n(u["acuse_horas"], 2)
    for f in await db.fetch(
        f"""SELECT e.id, array_agg(m.id ORDER BY m.creado_en) AS mensajes, min(m.creado_en) AS primero
              FROM disp_mensajes_equipos me JOIN disp_mensajes m ON m.id = me.mensaje_id
              JOIN disp_equipos e ON e.id = me.equipo_id
             WHERE {_ACTIVOS} AND m.nivel = 'urgente' AND m.requiere_acuse AND me.leido_en IS NULL
               AND m.creado_en < NOW() - make_interval(hours => $1) AND (m.caduca_en IS NULL OR m.caduca_en > NOW())
             GROUP BY e.id""",
        ah,
    ):
        out.append({"equipo_id": f["id"], "tipo": "mensaje_sin_acuse",
                    "detalle": {"mensajes": list(f["mensajes"])[:20], "desde": f["primero"].isoformat(), "horas": ah}})
    return out
