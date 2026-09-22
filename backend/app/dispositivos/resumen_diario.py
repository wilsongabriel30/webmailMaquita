"""Resumen diario por equipo (`disp_resumen_diario`) a partir de los latidos.

Los latidos se borran a los 30 días (`retencion_latidos_dias`); el resumen conserva la tendencia de
batería, almacenamiento y versiones 12 meses (400 días) con una fila por equipo y día.
Se recalculan hoy y ayer en cada corrida (idempotente).
"""

RETENCION_DIAS = 400


async def actualizar(db) -> int:
    r = await db.execute(
        """INSERT INTO disp_resumen_diario (equipo_id, dia, latidos, bateria_min, bateria_max, bateria_prom,
                    alm_libre_min, alm_libre_prom, alm_total, version_app, android, latidos_wifi, latidos_movil, actualizado_en)
           SELECT l.equipo_id, (l.recibido_en AT TIME ZONE 'America/Guayaquil')::date AS dia, count(*),
                  min((l.datos->>'bateria')::int), max((l.datos->>'bateria')::int), round(avg((l.datos->>'bateria')::int))::smallint,
                  min((l.datos->>'almacenamiento_libre')::bigint), round(avg((l.datos->>'almacenamiento_libre')::bigint))::bigint,
                  max((l.datos->>'almacenamiento_total')::bigint),
                  (array_agg(l.datos->>'version_app' ORDER BY l.recibido_en DESC) FILTER (WHERE l.datos ? 'version_app'))[1],
                  (array_agg(l.datos->>'android' ORDER BY l.recibido_en DESC) FILTER (WHERE l.datos ? 'android'))[1],
                  count(*) FILTER (WHERE lower(l.datos->>'red') LIKE '%wifi%'),
                  count(*) FILTER (WHERE lower(l.datos->>'red') LIKE '%movil%' OR lower(l.datos->>'red') LIKE '%móvil%' OR lower(l.datos->>'red') LIKE '%datos%'),
                  NOW()
             FROM disp_latidos l
            WHERE l.recibido_en > (date_trunc('day', NOW() AT TIME ZONE 'America/Guayaquil') - interval '1 day') AT TIME ZONE 'America/Guayaquil'
            GROUP BY l.equipo_id, dia
           ON CONFLICT (equipo_id, dia) DO UPDATE SET
                latidos = EXCLUDED.latidos, bateria_min = EXCLUDED.bateria_min, bateria_max = EXCLUDED.bateria_max,
                bateria_prom = EXCLUDED.bateria_prom, alm_libre_min = EXCLUDED.alm_libre_min, alm_libre_prom = EXCLUDED.alm_libre_prom,
                alm_total = EXCLUDED.alm_total, version_app = EXCLUDED.version_app, android = EXCLUDED.android,
                latidos_wifi = EXCLUDED.latidos_wifi, latidos_movil = EXCLUDED.latidos_movil, actualizado_en = NOW()"""
    )
    await db.execute(
        "DELETE FROM disp_resumen_diario WHERE dia < CURRENT_DATE - make_interval(days => $1)", RETENCION_DIAS
    )
    try:
        return int(r.split()[-1])
    except (ValueError, IndexError):
        return 0
