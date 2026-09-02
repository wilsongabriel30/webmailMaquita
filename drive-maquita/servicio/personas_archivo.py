# -*- coding: utf-8 -*-
"""Quién puede editar un archivo, para poder repartir permisos sobre él.

Responsabilidad ÚNICA: dada una ruta del Drive, decir qué personas tienen
acceso —y quiénes más hay en la nómina— para que quien protege un intervalo
pueda elegir a quién deja editarlo.

Se usa en «Hojas e intervalos protegidos» del editor de hojas: ahí se escoge
quién puede tocar cada trozo, y esa lista tiene que salir de la realidad del
Drive, no escribirse a mano (01/09/2026).
"""

import logging

log = logging.getLogger('almacen.personas_archivo')


def _fichas(ids):
    """Nombre y correo de cada persona, en una sola consulta."""
    if not ids:
        return {}
    try:
        from almacen_bd import consultar
        filas = consultar("""
            SELECT u.id, u.username, u.email,
                   COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username)
                   AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id IN %s
        """, (tuple(int(i) for i in ids),), nomina=True)
        return {f['id']: dict(f) for f in filas}
    except Exception as excepcion:
        log.warning('No se pudieron leer las personas: %s', excepcion)
        return {}


def _de_la_unidad(unidad_id, sub_ruta):
    """(id -> por qué puede) de quien tiene acceso a esa carpeta de la unidad."""
    quienes = {}
    try:
        from almacen_bd import consultar
        for fila in consultar(
                'SELECT usuario_id, rol FROM unidad_miembros WHERE unidad_id = %s',
                (int(unidad_id),)):
            quienes[int(fila['usuario_id'])] = 'En la unidad como ' + fila['rol']
        # Y quien tiene concedida ESTA carpeta, aunque no sea de la unidad.
        for fila in consultar(
                'SELECT usuario_id, rol, ruta FROM unidad_permisos_carpeta '
                'WHERE unidad_id = %s', (int(unidad_id),)):
            ruta = fila['ruta'] or '/'
            sub = '/' + (sub_ruta or '').strip('/')
            if sub == ruta or sub.startswith(ruta.rstrip('/') + '/'):
                quienes[int(fila['usuario_id'])] = 'En esta carpeta como ' + fila['rol']
    except Exception as excepcion:
        log.warning('No se pudo leer la unidad %s: %s', unidad_id, excepcion)
    return quienes


def _compartido_con(propietario_id, ruta):
    """(id -> por qué puede) de a quién se le compartió esa ruta."""
    quienes = {}
    try:
        from almacen_bd import consultar
        filas = consultar(
            'SELECT destinatario, email, ruta, puede_editar FROM compartidos '
            'WHERE propietario_id = %s AND (expira_en IS NULL OR expira_en > NOW()) '
            '  AND (destinatario IS NOT NULL OR email IS NOT NULL)',
            (int(propietario_id),))
        correos, usuarios = {}, {}
        for fila in filas:
            cubre = ruta == fila['ruta'] or ruta.startswith((fila['ruta'] or '').rstrip('/') + '/')
            if not cubre:
                continue
            razon = 'Compartido' + (' (puede editar)' if fila['puede_editar'] else ' (solo ver)')
            if fila['email']:
                correos[(fila['email'] or '').lower()] = razon
            if fila['destinatario']:
                usuarios[fila['destinatario']] = razon
        if correos or usuarios:
            personas = consultar(
                'SELECT id, username, LOWER(email) AS correo FROM usuarios '
                'WHERE LOWER(email) IN %s OR username IN %s',
                (tuple(correos.keys()) or ('',), tuple(usuarios.keys()) or ('',)),
                nomina=True)
            for p in personas:
                quienes[int(p['id'])] = (correos.get(p['correo'])
                                         or usuarios.get(p['username'])
                                         or 'Compartido')
    except Exception as excepcion:
        log.warning('No se pudo leer lo compartido de %s: %s', ruta, excepcion)
    return quienes


def con_acceso(usuario_id, ruta):
    """Personas que pueden entrar en esa ruta, con el motivo. Nunca lanza."""
    try:
        from seguridad_rutas import normalizar_ruta_virtual, unidad_de_ruta
        limpia = normalizar_ruta_virtual(ruta or '/')
        unidad, sub = unidad_de_ruta(limpia)
        if unidad:
            quienes = _de_la_unidad(unidad, sub)
        else:
            dueno = usuario_id
            try:
                from permisos_compartidos import compartido_de_ruta
                de_otro, subruta = compartido_de_ruta(limpia)
                if de_otro:
                    dueno, limpia = int(de_otro), subruta
            except Exception:
                pass
            quienes = _compartido_con(dueno, limpia)
            quienes[int(dueno)] = 'Dueño'
        quienes.setdefault(int(usuario_id), 'Tú')

        fichas = _fichas(quienes.keys())
        salida = []
        for persona_id, motivo in quienes.items():
            ficha = fichas.get(persona_id) or {}
            salida.append({
                'id': persona_id,
                'nombre': ficha.get('nombre') or ficha.get('username') or ('#%d' % persona_id),
                'email': ficha.get('email') or '',
                'motivo': motivo,
            })
        salida.sort(key=lambda p: p['nombre'].upper())
        return salida
    except Exception as excepcion:
        log.warning('No se pudo listar quien accede a %s: %s', ruta, excepcion)
        return []


def buscar_en_nomina(texto, tope=15):
    """Personas de la nómina que coinciden con lo escrito. Para añadir a alguien
    que todavía no tiene acceso."""
    texto = (texto or '').strip()
    if len(texto) < 2:
        return []
    try:
        from almacen_bd import consultar
        patron = '%' + texto.replace('%', '') + '%'
        filas = consultar("""
            SELECT u.id, u.username, u.email,
                   COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username)
                   AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.active IS NOT FALSE
              AND (COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username)
                   ILIKE %s OR u.email ILIKE %s)
            ORDER BY 4 LIMIT %s
        """, (patron, patron, int(tope)), nomina=True)
        return [{'id': f['id'], 'nombre': f['nombre'], 'email': f['email'] or '',
                 'motivo': ''} for f in filas]
    except Exception as excepcion:
        log.warning('No se pudo buscar en la nomina: %s', excepcion)
        return []
