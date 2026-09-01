#!/opt/maquita-webmail/backend/venv/bin/python3
"""Recordatorios y escalamiento de tareas asignadas (T-34). Cron cada 5 min (/etc/cron.d/maquita-tareas).
- 24 h antes del plazo → aviso al asignado (una vez).
- Al vencer sin completar → estado 'vencida' y aviso al asignado Y al asignador (una vez; el anti-olvido).
- Vencida X días (config por departamento en task_escalamiento, o `escalar_a` de la tarea) → aviso al jefe (una vez).
Registro: /var/log/maquita-tareas.log
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '/opt/maquita-webmail/backend')
os.chdir('/opt/maquita-webmail/backend')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('tareas')

from app.core.database import create_db_pool  # noqa: E402
from app.tareas import avisos  # noqa: E402
from app.tareas.servicio import SELECT, EC  # noqa: E402


async def main():
    pool = await create_db_pool()
    ahora = datetime.now(timezone.utc)
    async with pool.acquire() as db:
        # 1) 24 h antes
        rows = await db.fetch(SELECT + """ WHERE c.asignada AND NOT c.completed AND c.estado NOT IN ('espera','completada')
                              AND c.aviso_24h_en IS NULL AND c.due_date IS NOT NULL AND c.due_date > $1 AND c.due_date <= $2""",
                              ahora, ahora + timedelta(hours=24))
        for r in rows:
            await avisos.emitir(list(r['asignados'] or []), 'Vence mañana', f'{r["title"]} · {r["due_date"].astimezone(EC):%d/%m %H:%M}',
                                avisos.url_tarea(r['id']), r['created_by'], {'tarea_id': str(r['id']), 'accion': 'recordatorio'}, db, r['id'], 'recordatorio_24h')
            await db.execute('UPDATE task_cards SET aviso_24h_en = NOW() WHERE id = $1', r['id'])
        n1 = len(rows)
        # 2) vencidas
        rows = await db.fetch(SELECT + """ WHERE c.asignada AND NOT c.completed AND c.estado NOT IN ('espera','completada')
                              AND c.aviso_vencida_en IS NULL AND c.due_date IS NOT NULL AND c.due_date <= $1""", ahora)
        for r in rows:
            await db.execute("UPDATE task_cards SET estado = 'vencida', aviso_vencida_en = NOW(), updated_at = NOW() WHERE id = $1", r['id'])
            asignados = list(r['asignados'] or [])
            await avisos.emitir(asignados, 'Tarea VENCIDA', f'{r["title"]} venció el {r["due_date"].astimezone(EC):%d/%m %H:%M} y sigue sin completarse',
                                avisos.url_tarea(r['id']), r['created_by'], {'tarea_id': str(r['id']), 'accion': 'vencida'}, db, r['id'], 'vencida')
            await avisos.emitir([r['created_by']], 'Tarea vencida sin completar', f'{r["title"]} — asignada a {", ".join(avisos.nombre(a) for a in asignados)}',
                                avisos.url_tarea(r['id']), asignados[0] if asignados else '', {'tarea_id': str(r['id']), 'accion': 'vencida'}, db, r['id'], 'vencida_asignador')
        n2 = len(rows)
        # 3) escalamiento al jefe
        cfg = {c['departamento'].lower(): c for c in await db.fetch('SELECT * FROM task_escalamiento')}
        rows = await db.fetch(SELECT + """ WHERE c.asignada AND NOT c.completed AND c.estado = 'vencida' AND c.escalado_en IS NULL
                              AND c.due_date IS NOT NULL AND c.due_date <= $1""", ahora - timedelta(days=1))
        n3 = 0
        for r in rows:
            # Orden: jefe elegido en la tarea → jefe de la persona según NÓMINA (task_jefes, sincronizado a diario) → jefe del departamento
            jefe, dias = r['escalar_a'], 2
            for a in (r['asignados'] or []):
                dep = (await db.fetchval('SELECT COALESCE(department, \'\') FROM user_profiles WHERE user_email = $1', a) or '').lower()
                if dep in cfg:
                    dias = cfg[dep]['dias']
                if not jefe:
                    jefe = await db.fetchval('SELECT jefe_email FROM task_jefes WHERE email = $1', a)
                if not jefe and dep in cfg:
                    jefe = cfg[dep]['jefe_email']
                if jefe:
                    break
            if not jefe or r['due_date'] > ahora - timedelta(days=dias):
                continue
            asignados = list(r['asignados'] or [])
            await avisos.emitir([jefe, r['created_by']], f'ESCALADA: {dias} días vencida',
                                f'{r["title"]} — asignada a {", ".join(avisos.nombre(a) for a in asignados)} por {avisos.nombre(r["created_by"])}',
                                avisos.url_tarea(r['id']), asignados[0] if asignados else r['created_by'], {'tarea_id': str(r['id']), 'accion': 'escalada'}, db, r['id'], 'escalada')
            await db.execute('UPDATE task_cards SET escalado_en = NOW() WHERE id = $1', r['id'])
            n3 += 1
    await pool.close()
    if n1 or n2 or n3:
        log.info('recordatorios 24h=%s vencidas=%s escaladas=%s', n1, n2, n3)


if __name__ == '__main__':
    asyncio.run(main())
