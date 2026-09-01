#!/opt/maquita-webmail/backend/venv/bin/python3
"""Jefes para el ESCALAMIENTO de tareas (T-34), tomados de NÓMINA (Raíces, BD nomina en VM 132). Cron diario + a mano.
La asignación de tareas es LIBRE (cualquiera a cualquiera); esto solo decide a quién avisar cuando una tarea vence.
Orden por persona (correo institucional): aprobador de vacaciones → quien ocupa el cargo superior (mismo departamento,
correo @maquita) → jefe del departamento. Escribe `task_jefes` y `task_escalamiento` (jefes por departamento, 2 días) y
completa `user_profiles.department` (GAL) cuando está vacío. Registro: /var/log/maquita-tareas.log"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, '/opt/maquita-webmail/backend')
os.chdir('/opt/maquita-webmail/backend')
import asyncpg  # noqa: E402
from app.core.database import create_db_pool  # noqa: E402
from app.tareas import avisos  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('tareas.jefes')
DDL = """CREATE TABLE IF NOT EXISTS task_jefes (
    email TEXT PRIMARY KEY, jefe_email TEXT NOT NULL, jefe_nombre TEXT NOT NULL DEFAULT '', cargo TEXT NOT NULL DEFAULT '',
    departamento TEXT NOT NULL DEFAULT '', origen TEXT NOT NULL DEFAULT '', actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS task_personas (
    email TEXT PRIMARY KEY, nombre TEXT NOT NULL, cargo TEXT NOT NULL DEFAULT '', departamento TEXT NOT NULL DEFAULT '',
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW());"""
INST = '@maquita.'


def _dsn():
    for l in open('.env', encoding='utf-8'):
        if l.startswith('NOMINA_DSN='):
            return l.split('=', 1)[1].strip()
    raise SystemExit('Falta NOMINA_DSN en .env')


async def devolver_tareas_de_salidos(db, activos):
    """Salidas de personal: quien estaba en el directorio y ya no está Activo en nómina. Sus tareas pendientes vuelven
    al asignador (queda como asignado si no había otro), con comentario, etiqueta «salida de personal» y aviso T-03 para
    que las realice, reasigne o elimine. Cada tarea se devuelve una sola vez."""
    salidos = await db.fetch('SELECT email, nombre FROM task_personas WHERE email <> ALL($1::text[])', activos)
    for s in salidos:
        tareas = await db.fetch("""SELECT c.id, c.title, c.created_by, c.estado FROM task_cards c JOIN task_asignados a ON a.card_id = c.id
                                   WHERE a.email = $1 AND c.asignada AND NOT c.completed""", s['email'])
        if not tareas:
            continue
        por_asignador = {}
        for t in tareas:
            await db.execute('DELETE FROM task_asignados WHERE card_id = $1 AND email = $2', t['id'], s['email'])
            quedan = await db.fetchval('SELECT count(*) FROM task_asignados WHERE card_id = $1', t['id'])
            if not quedan:
                await db.execute('INSERT INTO task_asignados (card_id, email) VALUES ($1,$2) ON CONFLICT DO NOTHING', t['id'], t['created_by'])
            await db.execute("""UPDATE task_cards SET assigned_to = (SELECT email FROM task_asignados WHERE card_id = $1 ORDER BY asignado_en LIMIT 1),
                                estado = CASE WHEN estado = 'en_curso' THEN 'pendiente' ELSE estado END, aceptacion = 'sin_responder',
                                etiquetas = CASE WHEN etiquetas::text ILIKE '%salida de personal%' THEN etiquetas ELSE etiquetas || '["salida de personal"]'::jsonb END,
                                updated_at = NOW() WHERE id = $1""", t['id'])
            await db.execute("INSERT INTO task_comentarios (card_id, autor, texto) VALUES ($1, 'sistema', $2)", t['id'],
                             f"{s['nombre']} ya no labora en Maquita (salida registrada en nómina). Esta tarea quedó pendiente y vuelve a quien la asignó: realízala, reasígnala o elimínala.")
            por_asignador.setdefault(t['created_by'], []).append(t['title'])
        for asignador, titulos in por_asignador.items():
            await avisos.emitir([asignador], f"{s['nombre']} ya no labora: {len(titulos)} tarea(s) pendiente(s)",
                                'Quedaron sin hacer: ' + '; '.join(titulos)[:220] + '. Realízalas, reasígnalas o elimínalas.',
                                avisos.URL_TAREAS + '&pestana=por-mi', asignador, {'accion': 'asignado_salio'}, db, None, 'asignado_salio', incluir_originador=True)
        log.info('salida de %s: %s tareas devueltas a %s', s['email'], len(tareas), ', '.join(por_asignador))


async def main():
    nom = await asyncpg.connect(_dsn())
    trab = await nom.fetch("""
        SELECT t.id, t.estado, lower(trim(t.email_institucional)) AS email, t.nombres||' '||t.apellidos AS nombre, t.cargo_id, t.departamento_id,
               t.aprobador_vacaciones_id, c.nombre AS cargo, c.cargo_superior_id, d.nombre AS departamento, d.jefe_departamento_id
        FROM trabajadores t LEFT JOIN cargos c ON c.id = t.cargo_id LEFT JOIN departamentos_empresa d ON d.id = t.departamento_id
        WHERE t.es_version_actual AND lower(coalesce(t.estado,'')) IN ('activo','consultor externo') AND t.email_institucional ILIKE '%@%'""")
    usuarios_raices = await nom.fetch("""SELECT lower(u.email) AS email, u.full_name, u.profile_picture, t.foto_perfil, lower(trim(t.email_institucional)) AS email_inst
        FROM usuarios u LEFT JOIN trabajadores t ON t.id = u.trabajador_id AND t.es_version_actual WHERE u.email ILIKE '%@%' AND COALESCE(u.full_name,'') <> ''""")
    deptos = await nom.fetch("SELECT id, nombre, jefe_departamento_id FROM departamentos_empresa WHERE activo IS DISTINCT FROM FALSE")
    await nom.close()
    por_id = {t['id']: t for t in trab}
    por_cargo = {}
    for t in trab:
        por_cargo.setdefault(t['cargo_id'], []).append(t)

    def inst(t):
        return t and INST in (t['email'] or '')

    def jefe_de(t):
        a = por_id.get(t['aprobador_vacaciones_id'])
        if inst(a) and a['id'] != t['id']:
            return a, 'aprobador_vacaciones'
        cand = [x for x in por_cargo.get(t['cargo_superior_id'], []) if inst(x) and x['id'] != t['id']]
        mismo = [x for x in cand if x['departamento_id'] == t['departamento_id']]
        if mismo or cand:
            return (mismo or cand)[0], 'cargo_superior'
        j = por_id.get(t['jefe_departamento_id'])
        if inst(j) and j['id'] != t['id']:
            return j, 'jefe_departamento'
        return None, ''

    pool = await create_db_pool()
    n = sin = 0
    async with pool.acquire() as db:
        await db.execute(DDL)
        activos = [t['email'] for t in trab if (t['estado'] or '').lower() == 'activo']
        await devolver_tareas_de_salidos(db, activos)
        await db.execute('DELETE FROM task_personas WHERE email <> ALL($1::text[])', [t['email'] for t in trab if (t['estado'] or '').lower() == 'activo'])
        for t in trab:
            if (t['estado'] or '').lower() != 'activo':
                continue   # consultores: pueden ser jefes, pero no salen en el directorio
            await db.execute("""INSERT INTO task_personas (email, nombre, cargo, departamento, actualizado_en) VALUES ($1,$2,$3,$4,NOW())
                                ON CONFLICT (email) DO UPDATE SET nombre=EXCLUDED.nombre, cargo=EXCLUDED.cargo, departamento=EXCLUDED.departamento, actualizado_en=NOW()""",
                             t['email'], (t['nombre'] or '').strip().title(), t['cargo'] or '', t['departamento'] or '')
            await db.execute("""INSERT INTO user_profiles (user_email, display_name, department, title) VALUES ($1,$2,$3,$4)
                                ON CONFLICT (user_email) DO UPDATE SET display_name = CASE WHEN COALESCE(user_profiles.display_name,'')='' OR user_profiles.display_name = split_part(user_profiles.user_email,'@',1) THEN EXCLUDED.display_name ELSE user_profiles.display_name END""",
                             t['email'], (t['nombre'] or '').strip().title(), t['departamento'] or '', t['cargo'] or '')
            j, origen = jefe_de(t)
            if not j:
                sin += 1
                await db.execute('DELETE FROM task_jefes WHERE email = $1', t['email'])
                continue
            await db.execute("""INSERT INTO task_jefes (email, jefe_email, jefe_nombre, cargo, departamento, origen, actualizado_en)
                                VALUES ($1,$2,$3,$4,$5,$6,NOW()) ON CONFLICT (email) DO UPDATE SET jefe_email=EXCLUDED.jefe_email,
                                jefe_nombre=EXCLUDED.jefe_nombre, cargo=EXCLUDED.cargo, departamento=EXCLUDED.departamento,
                                origen=EXCLUDED.origen, actualizado_en=NOW()""",
                             t['email'], j['email'], j['nombre'], t['cargo'] or '', t['departamento'] or '', origen)
            n += 1
            if t['departamento']:
                await db.execute("""INSERT INTO user_profiles (user_email, department, title) VALUES ($1,$2,$3)
                                    ON CONFLICT (user_email) DO UPDATE SET department = CASE WHEN COALESCE(user_profiles.department,'')='' THEN EXCLUDED.department ELSE user_profiles.department END,
                                    title = CASE WHEN COALESCE(user_profiles.title,'')='' THEN EXCLUDED.title ELSE user_profiles.title END""",
                                 t['email'], t['departamento'], t['cargo'] or '')
        # Foto de perfil: la de Raíces (usuarios.profile_picture) o la de nómina (trabajadores.foto_perfil) → GAL del correo
        nf = 0
        for u in usuarios_raices:
            pp = (u['profile_picture'] or '').strip(); fp = (u['foto_perfil'] or '').strip()
            if pp.startswith('http'): url = pp
            elif pp: url = 'https://datos.maquita.com.ec/static/' + (pp if pp.startswith('uploads/') else 'uploads/profiles/' + pp)
            elif fp: url = 'https://datos.maquita.com.ec/static/' + fp
            else: continue
            for correo in {u['email'], u['email_inst']}:
                if correo and '@' in correo:
                    await db.execute("""INSERT INTO user_profiles (user_email, photo_url) VALUES ($1,$2)
                                        ON CONFLICT (user_email) DO UPDATE SET photo_url = EXCLUDED.photo_url WHERE user_profiles.photo_url IS DISTINCT FROM EXCLUDED.photo_url""", correo, url)
                    nf += 1
        nd = 0
        for d in deptos:
            j = por_id.get(d['jefe_departamento_id'])
            if inst(j):
                await db.execute("""INSERT INTO task_escalamiento (departamento, jefe_email, dias, actualizado_por) VALUES ($1,$2,2,'nomina')
                                    ON CONFLICT (departamento) DO UPDATE SET jefe_email = EXCLUDED.jefe_email, actualizado_en = NOW()
                                    WHERE task_escalamiento.actualizado_por = 'nomina'""", d['nombre'], j['email'])
                nd += 1
    await pool.close()
    import json
    json.dump({**{u['email']: u['full_name'].strip().title() for u in usuarios_raices}, **{t['email']: (t['nombre'] or '').strip().title() for t in trab}}, open('/opt/maquita-webmail/backend/app/tareas/nombres.json', 'w', encoding='utf-8'), ensure_ascii=False)
    log.info('nómina: %s personas en el directorio, %s con jefe, %s sin resolver, %s departamentos, %s fotos replicadas', len(trab), n, sin, nd, nf)


if __name__ == '__main__':
    asyncio.run(main())
