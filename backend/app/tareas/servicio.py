"""Lógica de T-34: crear/asignar, listar (mis / asignadas por mí / mi día), estado, aceptación, comentarios con
@menciones, completar → recurrencia y cadena, escalamiento. Reutiliza app.tasks (tarjeta en la lista del creador,
subtareas task_steps, calendario del asignado)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from app.core.sanitize import strip_html, sanitize_html
from app.tasks.schemas import CardCreate
from app.tasks.service import task_service
from app.tasks.task_calendar_sync import sync_task_to_calendar, remove_task_from_calendar
from app.tareas import avisos
from app.tareas.esquemas import (ESTADOS, PRIORIDADES, RECURRENCIAS, TareaAsignar, TareaEditar, TareaOut)

MENCION = re.compile(r'@([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')
EC = timezone(timedelta(hours=-5))

SELECT = """
SELECT c.*, COALESCE(a.asignados, '{}') AS asignados,
       (SELECT count(*) FROM task_steps s WHERE s.card_id = c.id) AS st_total,
       (SELECT count(*) FROM task_steps s WHERE s.card_id = c.id AND s.completed) AS st_hechas,
       (SELECT count(*) FROM task_comentarios k WHERE k.card_id = c.id) AS n_com,
       (SELECT p.id FROM task_cards p WHERE p.activa_tarea_id = c.id LIMIT 1) AS activa_a
FROM task_cards c
LEFT JOIN (SELECT card_id, array_agg(email ORDER BY asignado_en) AS asignados FROM task_asignados GROUP BY card_id) a
       ON a.card_id = c.id
"""


def _semaforo(row) -> str:
    if row['completed'] or row['estado'] == 'completada':
        return 'gris'
    plazo = row['due_date']
    if not plazo:
        return 'verde'
    ahora = datetime.now(timezone.utc)
    if plazo < ahora:
        return 'rojo'
    if plazo.astimezone(EC).date() <= ahora.astimezone(EC).date():
        return 'rojo'          # vence hoy
    if plazo - ahora <= timedelta(hours=48):
        return 'amarillo'
    return 'verde'


def _lista(v):
    if isinstance(v, str):
        v = json.loads(v)
    return list(v or [])


def a_salida(row) -> TareaOut:
    estado = row['estado']
    if not row['completed'] and estado not in ('espera', 'completada') and row['due_date'] and row['due_date'] < datetime.now(timezone.utc):
        estado = 'vencida'
    correo = row['correo_ref']
    if isinstance(correo, str):
        correo = json.loads(correo)
    return TareaOut(
        id=row['id'], titulo=row['title'], descripcion=row['description'], asignados=list(row['asignados'] or []),
        asignado_por=row['created_by'], plazo=row['due_date'], prioridad=row['priority'],
        etiquetas=_lista(row['etiquetas']) or _lista(row['labels']), estado=estado, semaforo=_semaforo(row),
        aceptacion=row['aceptacion'], motivo_rechazo=row['motivo_rechazo'], recurrencia=row['recurrence'],
        activa_tarea_id=row['activa_a'], activada_por=row['activa_tarea_id'], escalar_a=row['escalar_a'],
        escalado_en=row['escalado_en'], correo=correo, subtareas_total=row['st_total'], subtareas_hechas=row['st_hechas'],
        comentarios=row['n_com'], completada_por=row['completed_by'], completada_en=row['completed_at'],
        creada_en=row['created_at'], actualizada_en=row['updated_at'], url=avisos.url_tarea(row['id']))


class ServicioTareas:
    # ---------- lectura ----------
    async def obtener(self, db, tarea_id, user):
        row = await db.fetchrow(SELECT + ' WHERE c.id = $1 AND c.asignada', tarea_id)
        if not row:
            raise LookupError('Tarea no encontrada')
        if user not in (row['created_by'], *(row['asignados'] or [])) and user != row['escalar_a']:
            raise PermissionError('No participas en esta tarea')
        return row

    async def mis(self, db, user, incluir_completadas=False):
        cond = '' if incluir_completadas else ' AND NOT c.completed'
        rows = await db.fetch(SELECT + f""" WHERE c.asignada AND $1 = ANY(COALESCE(a.asignados, '{{}}')) {cond}
                              ORDER BY c.completed, c.due_date NULLS LAST, c.created_at DESC""", user)
        return [a_salida(r) for r in rows]

    async def asignadas_por_mi(self, db, user, incluir_completadas=False):
        cond = '' if incluir_completadas else ' AND NOT c.completed'
        rows = await db.fetch(SELECT + f""" WHERE c.asignada AND c.created_by = $1 {cond}
                              ORDER BY c.completed, c.due_date NULLS LAST, c.created_at DESC""", user)
        return [a_salida(r) for r in rows]

    async def mi_dia(self, db, user):
        hoy = datetime.now(EC).date()
        rows = await db.fetch(SELECT + """ WHERE c.asignada AND NOT c.completed AND c.estado <> 'espera'
                              AND $1 = ANY(COALESCE(a.asignados, '{}'))
                              AND (c.my_day OR (c.due_date IS NOT NULL AND (c.due_date AT TIME ZONE 'America/Guayaquil')::date <= $2))
                              ORDER BY c.due_date NULLS LAST""", user, hoy)
        return [a_salida(r) for r in rows]

    # ---------- creación ----------
    async def asignar(self, db, redis, user, d: TareaAsignar):
        if d.prioridad not in PRIORIDADES:
            d.prioridad = 'medium'
        if d.recurrencia and d.recurrencia not in RECURRENCIAS:
            raise ValueError('Recurrencia no válida')
        asignados = sorted({a.strip().lower() for a in d.asignados if a and '@' in a}) or [user]
        card = await task_service.create_task(db, user, None, CardCreate(
            title=d.titulo, description=d.descripcion, due_date=d.plazo, priority=d.prioridad,
            labels=d.etiquetas, assigned_to=asignados[0], recurrence=d.recurrencia))
        estado = 'espera' if d.en_espera else 'pendiente'
        await db.execute("""UPDATE task_cards SET asignada = TRUE, estado = $2, etiquetas = $3::jsonb, correo_ref = $4::jsonb,
                            activa_tarea_id = $5, escalar_a = $6 WHERE id = $1""",
                         card.id, estado, json.dumps(d.etiquetas), json.dumps(d.correo.model_dump(by_alias=True)) if d.correo else None,
                         d.activa_tarea_id, (d.escalar_a or '').lower() or None)
        for a in asignados:
            await db.execute('INSERT INTO task_asignados (card_id, email) VALUES ($1,$2) ON CONFLICT DO NOTHING', card.id, a)
        for i, s in enumerate(t for t in d.subtareas if t.strip()):
            await db.execute('INSERT INTO task_steps (card_id, title, position) VALUES ($1,$2,$3)', card.id, strip_html(s)[:300], i)
        row = await self.obtener(db, card.id, user)
        if estado != 'espera':
            await self._calendario(db, redis, row, user)
            plazo = f" · vence {row['due_date'].astimezone(EC):%d/%m %H:%M}" if row['due_date'] else ''
            await avisos.emitir(asignados, f'Nueva tarea de {avisos.nombre(user)}', f'{row["title"]}{plazo}',
                                avisos.url_tarea(card.id), user, {'tarea_id': str(card.id), 'accion': 'asignada'}, db, card.id, 'asignada')
        return a_salida(row)

    async def _calendario(self, db, redis, row, user):
        for a in (row['asignados'] or []):
            try:
                rd = dict(row); rd['assigned_to'] = a
                await sync_task_to_calendar(db, redis, rd, user)
            except Exception:
                pass

    # ---------- edición ----------
    async def editar(self, db, redis, user, tarea_id, d: TareaEditar):
        row = await self.obtener(db, tarea_id, user)
        if user != row['created_by']:
            raise PermissionError('Solo quien asignó la tarea puede editarla')
        sets, vals = [], []
        def s(col, val):
            vals.append(val); sets.append(f'{col} = ${len(vals) + 1}')
        if d.titulo is not None: s('title', strip_html(d.titulo))
        if d.descripcion is not None: s('description', sanitize_html(d.descripcion))
        if d.quitar_plazo: s('due_date', None); s('aviso_24h_en', None); s('aviso_vencida_en', None)
        elif d.plazo is not None: s('due_date', d.plazo); s('aviso_24h_en', None); s('aviso_vencida_en', None); s('escalado_en', None)
        if d.prioridad in PRIORIDADES: s('priority', d.prioridad)
        if d.etiquetas is not None: s('etiquetas', json.dumps(d.etiquetas))
        if d.quitar_recurrencia: s('recurrence', None)
        elif d.recurrencia in RECURRENCIAS: s('recurrence', d.recurrencia)
        if d.activa_tarea_id is not None: s('activa_tarea_id', d.activa_tarea_id)
        if d.escalar_a is not None: s('escalar_a', d.escalar_a.lower() or None)
        if sets:
            sets.append('updated_at = NOW()')
            await db.execute(f'UPDATE task_cards SET {", ".join(sets)} WHERE id = $1', tarea_id, *vals)
        nuevos = []
        if d.asignados is not None:
            quiere = sorted({a.strip().lower() for a in d.asignados if '@' in a})
            actuales = list(row['asignados'] or [])
            for a in actuales:
                if a not in quiere:
                    await db.execute('DELETE FROM task_asignados WHERE card_id = $1 AND email = $2', tarea_id, a)
                    await remove_task_from_calendar(db, dict(row), a)
            for a in quiere:
                if a not in actuales:
                    await db.execute('INSERT INTO task_asignados (card_id, email) VALUES ($1,$2) ON CONFLICT DO NOTHING', tarea_id, a)
                    nuevos.append(a)
            if quiere:
                await db.execute('UPDATE task_cards SET assigned_to = $2, aceptacion = CASE WHEN $3 THEN aceptacion ELSE \'sin_responder\' END WHERE id = $1',
                                 tarea_id, quiere[0], not nuevos)
        row = await self.obtener(db, tarea_id, user)
        if row['estado'] != 'espera':
            await self._calendario(db, redis, row, user)
        if nuevos:
            await avisos.emitir(nuevos, f'Nueva tarea de {avisos.nombre(user)}', row['title'], avisos.url_tarea(tarea_id), user,
                                {'tarea_id': str(tarea_id), 'accion': 'asignada'}, db, tarea_id, 'asignada')
        viejos = [a for a in (row['asignados'] or []) if a not in nuevos]
        if sets and viejos:
            await avisos.emitir(viejos, f'{avisos.nombre(user)} cambió la tarea', row['title'], avisos.url_tarea(tarea_id), user,
                                {'tarea_id': str(tarea_id), 'accion': 'cambiada'}, db, tarea_id, 'cambiada')
        return a_salida(row)

    # ---------- estado / aceptación ----------
    async def cambiar_estado(self, db, redis, user, tarea_id, estado):
        if estado not in ESTADOS or estado == 'vencida':
            raise ValueError('Estado no válido')
        row = await self.obtener(db, tarea_id, user)
        if estado == 'completada':
            return await self.completar(db, redis, user, tarea_id)
        completada_antes = row['completed']
        await db.execute("UPDATE task_cards SET estado = $2, completed = FALSE, completed_by = NULL, completed_at = NULL, updated_at = NOW() WHERE id = $1",
                         tarea_id, estado)
        row = await self.obtener(db, tarea_id, user)
        if completada_antes:
            await self._calendario(db, redis, row, user)
        destino = [row['created_by']] if user != row['created_by'] else list(row['asignados'] or [])
        nombres = {'pendiente': 'pendiente', 'en_curso': 'en curso', 'espera': 'en espera'}
        await avisos.emitir(destino, f'Tarea {nombres.get(estado, estado)}', f'{avisos.nombre(user)}: {row["title"]}',
                            avisos.url_tarea(tarea_id), user, {'tarea_id': str(tarea_id), 'accion': estado}, db, tarea_id, estado)
        return a_salida(row)

    async def aceptar(self, db, user, tarea_id):
        row = await self.obtener(db, tarea_id, user)
        if user not in (row['asignados'] or []):
            raise PermissionError('Solo el asignado puede aceptar')
        await db.execute("UPDATE task_cards SET aceptacion = 'aceptada', motivo_rechazo = '', estado = CASE WHEN estado = 'pendiente' THEN 'en_curso' ELSE estado END, updated_at = NOW() WHERE id = $1", tarea_id)
        row = await self.obtener(db, tarea_id, user)
        await avisos.emitir([row['created_by']], f'{avisos.nombre(user)} aceptó la tarea', row['title'], avisos.url_tarea(tarea_id), user,
                            {'tarea_id': str(tarea_id), 'accion': 'aceptada'}, db, tarea_id, 'aceptada')
        return a_salida(row)

    async def rechazar(self, db, user, tarea_id, motivo):
        row = await self.obtener(db, tarea_id, user)
        if user not in (row['asignados'] or []):
            raise PermissionError('Solo el asignado puede rechazar')
        await db.execute("UPDATE task_cards SET aceptacion = 'rechazada', motivo_rechazo = $2, updated_at = NOW() WHERE id = $1",
                         tarea_id, strip_html(motivo or '')[:500])
        row = await self.obtener(db, tarea_id, user)
        await avisos.emitir([row['created_by']], f'{avisos.nombre(user)} rechazó la tarea', f'{row["title"]} — {motivo or "sin motivo"}',
                            avisos.url_tarea(tarea_id), user, {'tarea_id': str(tarea_id), 'accion': 'rechazada'}, db, tarea_id, 'rechazada')
        return a_salida(row)

    # ---------- completar → recurrencia + cadena ----------
    async def completar(self, db, redis, user, tarea_id):
        row = await self.obtener(db, tarea_id, user)
        await db.execute("""UPDATE task_cards SET completed = TRUE, estado = 'completada', completed_by = $2, completed_at = NOW(),
                            updated_at = NOW() WHERE id = $1""", tarea_id, user)
        for a in (row['asignados'] or []):
            try:
                await remove_task_from_calendar(db, dict(row), a)
            except Exception:
                pass
        row = await self.obtener(db, tarea_id, user)
        destino = [row['created_by']] if user != row['created_by'] else list(row['asignados'] or [])
        await avisos.emitir(destino, f'Tarea completada por {avisos.nombre(user)}', row['title'], avisos.url_tarea(tarea_id), user,
                            {'tarea_id': str(tarea_id), 'accion': 'completada'}, db, tarea_id, 'completada')
        await self._siguiente_recurrencia(db, redis, row)
        await self._activar_cadena(db, redis, row, user)
        return a_salida(row)

    async def _siguiente_recurrencia(self, db, redis, row):
        rec, plazo = row['recurrence'], row['due_date']
        if not rec or not plazo:
            return
        base = max(plazo, datetime.now(timezone.utc)) if plazo < datetime.now(timezone.utc) - timedelta(days=60) else plazo
        if rec == 'daily': nuevo = base + timedelta(days=1)
        elif rec == 'weekdays':
            nuevo = base + timedelta(days=1)
            while nuevo.astimezone(EC).weekday() >= 5: nuevo += timedelta(days=1)
        elif rec == 'weekly': nuevo = base + timedelta(weeks=1)
        elif rec == 'monthly':
            l = base.astimezone(EC); m = l.month % 12 + 1; y = l.year + (l.month == 12)
            import calendar; dia = min(l.day, calendar.monthrange(y, m)[1])
            nuevo = l.replace(year=y, month=m, day=dia).astimezone(timezone.utc)
        elif rec == 'yearly':
            l = base.astimezone(EC)
            try: nuevo = l.replace(year=l.year + 1).astimezone(timezone.utc)
            except ValueError: nuevo = l.replace(year=l.year + 1, day=28).astimezone(timezone.utc)
        else:
            return
        creador = row['created_by']
        d = TareaAsignar(titulo=row['title'], descripcion=row['description'], asignados=list(row['asignados'] or []), plazo=nuevo,
                         prioridad=row['priority'], etiquetas=_lista(row['etiquetas']), recurrencia=rec, escalar_a=row['escalar_a'])
        pasos = await db.fetch('SELECT title FROM task_steps WHERE card_id = $1 ORDER BY position', row['id'])
        d.subtareas = [p['title'] for p in pasos]
        await self.asignar(db, redis, creador, d)

    async def _activar_cadena(self, db, redis, row, user):
        sig = await db.fetch(SELECT + " WHERE c.activa_tarea_id = $1 AND c.estado = 'espera' AND NOT c.completed", row['id'])
        for n in sig:
            await db.execute("UPDATE task_cards SET estado = 'pendiente', updated_at = NOW() WHERE id = $1", n['id'])
            n2 = await db.fetchrow(SELECT + ' WHERE c.id = $1', n['id'])
            await self._calendario(db, redis, n2, n2['created_by'])
            await avisos.emitir(list(n2['asignados'] or []), 'Te toca: tarea activada',
                                f'«{row["title"]}» se completó; ahora sigue «{n2["title"]}»', avisos.url_tarea(n2['id']), user,
                                {'tarea_id': str(n2['id']), 'accion': 'activada'}, db, n2['id'], 'activada')

    # ---------- comentarios ----------
    async def comentar(self, db, user, tarea_id, texto):
        row = await self.obtener(db, tarea_id, user)
        texto = strip_html(texto or '').strip()[:2000]
        if not texto:
            raise ValueError('Comentario vacío')
        menciones = sorted({m.lower() for m in MENCION.findall(texto)})
        c = await db.fetchrow('INSERT INTO task_comentarios (card_id, autor, texto, menciones) VALUES ($1,$2,$3,$4::jsonb) RETURNING *',
                              tarea_id, user, texto, json.dumps(menciones))
        partes = set(row['asignados'] or []) | {row['created_by']} | set(menciones)
        await avisos.emitir(list(partes), f'{avisos.nombre(user)} comentó: {row["title"]}', texto, avisos.url_tarea(tarea_id), user,
                            {'tarea_id': str(tarea_id), 'accion': 'comentario'}, db, tarea_id, 'comentario')
        return c

    async def comentarios(self, db, user, tarea_id):
        await self.obtener(db, tarea_id, user)
        return await db.fetch('SELECT * FROM task_comentarios WHERE card_id = $1 ORDER BY creado_en', tarea_id)

    async def eliminar(self, db, user, tarea_id):
        row = await self.obtener(db, tarea_id, user)
        if user != row['created_by']:
            raise PermissionError('Solo quien la asignó puede eliminarla')
        for a in (row['asignados'] or []):
            try: await remove_task_from_calendar(db, dict(row), a)
            except Exception: pass
        await db.execute('DELETE FROM task_cards WHERE id = $1', tarea_id)
        await avisos.emitir(list(row['asignados'] or []), 'Tarea eliminada', f'{avisos.nombre(user)} eliminó «{row["title"]}»',
                            avisos.URL_TAREAS, user, {'accion': 'eliminada'}, db, None, 'eliminada')

    # ---------- personas y escalamiento ----------
    async def personas(self, db, q, limite=15):
        """Directorio para «Asignar a»: consulta NÓMINA EN VIVO (Raíces, VM 132): solo trabajadores con estado Activo y correo
        institucional; quien ingresa a nómina aparece al instante. Caché de 60 s por proceso; si nómina no responde, se usa
        la copia sincronizada (task_personas). Busca por nombre, correo, cargo o departamento, sin importar tildes."""
        import time
        import asyncpg
        ahora = time.time()
        if not hasattr(self, '_nom_cache') or ahora - self._nom_cache[0] > 60:
            try:
                con = await asyncpg.connect(_nomina_dsn(), timeout=5)
                try:
                    filas = await con.fetch("""
                        SELECT lower(trim(t.email_institucional)) AS email, initcap(t.nombres||' '||t.apellidos) AS nombre,
                               COALESCE(c.nombre,'') AS cargo, COALESCE(d.nombre,'') AS departamento
                        FROM trabajadores t LEFT JOIN cargos c ON c.id = t.cargo_id LEFT JOIN departamentos_empresa d ON d.id = t.departamento_id
                        WHERE t.es_version_actual AND lower(COALESCE(t.estado,'')) = 'activo' AND t.email_institucional ILIKE '%@%'
                        ORDER BY nombre""")
                finally:
                    await con.close()
                self._nom_cache = (ahora, [dict(f) for f in filas])
            except Exception as e:
                import logging; logging.getLogger(__name__).warning('nómina en vivo no disponible, uso la copia: %s', e)
                filas = await db.fetch('SELECT email, nombre, cargo, departamento FROM task_personas ORDER BY nombre')
                self._nom_cache = (ahora - 50, [dict(f) for f in filas])   # reintenta pronto
        import unicodedata
        def plano(x): return unicodedata.normalize('NFKD', (x or '').lower()).encode('ascii', 'ignore').decode()
        qq = plano(q).strip()
        res = [p for p in self._nom_cache[1] if not qq or qq in plano(p['nombre']) or qq in plano(p['email']) or qq in plano(p['cargo']) or qq in plano(p['departamento'])]
        return res[:limite]

    async def escalamiento_listar(self, db):
        return await db.fetch('SELECT * FROM task_escalamiento ORDER BY departamento')

    async def escalamiento_guardar(self, db, user, cfg):
        return await db.fetchrow("""INSERT INTO task_escalamiento (departamento, jefe_email, dias, actualizado_por)
                                    VALUES ($1,$2,$3,$4) ON CONFLICT (departamento) DO UPDATE
                                    SET jefe_email = EXCLUDED.jefe_email, dias = EXCLUDED.dias, actualizado_por = EXCLUDED.actualizado_por,
                                        actualizado_en = NOW() RETURNING *""",
                                 cfg.departamento.strip(), cfg.jefe_email.strip().lower(), max(1, cfg.dias), user)

    async def escalamiento_borrar(self, db, departamento):
        await db.execute('DELETE FROM task_escalamiento WHERE departamento = $1', departamento)


def _nomina_dsn():
    import os
    if os.getenv('NOMINA_DSN'):
        return os.environ['NOMINA_DSN']
    for l in open('/opt/maquita-webmail/backend/.env', encoding='utf-8'):
        if l.startswith('NOMINA_DSN='):
            return l.split('=', 1)[1].strip()
    raise RuntimeError('Falta NOMINA_DSN')


servicio_tareas = ServicioTareas()
