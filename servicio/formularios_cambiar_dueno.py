# -*- coding: utf-8 -*-
"""
Formularios del Almacén — cambiar de dueño
==========================================
Pasa un formulario del Drive de una persona al de otra SIN que deje de ser el
mismo formulario: conserva su identificador, su enlace público, su código QR,
sus respuestas, su papelera de respuestas y sus imágenes.

Qué se lleva al Drive del nuevo dueño:

  · el `.forma`;
  · su hoja de respuestas (`.xlsx`), si está en el Drive personal;
  · la carpeta «<formulario> (archivos)» con lo que adjuntó quien respondió.

Y qué se actualiza en la base: el registro del formulario (dueño y rutas), las
rutas de los adjuntos dentro de cada respuesta si cambia la carpeta, y lo que
apunta a esos archivos (compartidos, vínculos, copias fieles, publicaciones).

Cómo se hace, y por qué en este orden:

  1. se COPIA al nuevo dueño con `nucleo.subir` (cuota, índice y versiones
     como cualquier archivo suyo);
  2. se cambia el registro en la base. Tiene que ir ANTES de que nadie abra
     la copia: un `.forma` cuyo id consta a nombre de otra persona se toma por
     una copia y recibe un id nuevo, separado de sus respuestas;
  3. se comprueba que el nuevo dueño lee el formulario con el mismo id;
  4. los originales van a la PAPELERA del dueño anterior (recuperables).

Si la copia falla, se retira lo copiado y no se cambia nada.

El editor guarda unos segundos DESPUÉS de cerrarse la última pestaña. Por eso
antes de copiar se espera a que la hoja lleve `ESPERA_CIERRE` segundos cerrada
y sin cambiar; si no, ese guardado final volvía a crear el Excel en el Drive
del dueño anterior (29/09/2026, «prueba_2026»).

No se admite (se avisa y no se toca): formulario creado desde un libro, con su
hoja en la carpeta interna `.formularios`, ni hoja de respuestas abierta en el
editor. En una unidad compartida los archivos son de la unidad: solo cambia
quién consta como responsable del formulario.

`planear` no escribe nada. `aplicar` recibe lo que devuelve `planear`.

Autoría: Equipo de Tecnología Maquita — 2026-09-29
"""
import json
import logging
import os

import almacen_bd as bd
import encuestas_archivos as archivos_mod
import encuestas_bd as ebd
import nucleo_archivos as nucleo
from archivos_internos import en_carpeta_interna
from seguridad_rutas import normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.formularios.cambiar_dueno')

# (tabla, columna de ruta, columna del dueño de esa ruta)
APUNTAN = (
    ('compartidos', 'ruta', 'propietario_id'),
    ('ajustes_compartir', 'ruta', 'propietario_id'),
    ('solicitudes_acceso', 'ruta', 'propietario_id'),
    ('publicaciones_web', 'ruta', 'usuario_id'),
    ('formulario_destinos', 'destino_ruta', 'destino_usuario'),
    ('espejos_hoja', 'origen_ruta', 'origen_usuario'),
    ('espejos_hoja', 'destino_ruta', 'destino_usuario'),
    ('vinculos_datos', 'origen_ruta', 'origen_usuario'),
    ('vinculos_datos', 'destino_ruta', 'destino_usuario'),
)
ROLES_QUE_ESCRIBEN = ('manager', 'editor')
ESPERA_CIERRE = 20


def _unir(carpeta, nombre):
    return ('' if carpeta in ('', '/') else carpeta) + '/' + nombre


def _padre(ruta):
    return ruta.rsplit('/', 1)[0] or '/'


def _nombre(ruta):
    return ruta.rsplit('/', 1)[-1]


def _existe(usuario, ruta):
    return os.path.exists(ruta_fisica(int(usuario), ruta))


def planear(origen, ruta_forma, destino, carpeta=None):
    """Qué habría que hacer, sin hacerlo. Si `bloqueos` trae algo, no se puede."""
    from api_encuestas import leer_definicion
    origen, destino = int(origen), int(destino)
    ruta_forma = normalizar_ruta_virtual(ruta_forma)
    plan = {'origen': origen, 'destino': destino, 'ruta': ruta_forma,
            'piezas': [], 'bloqueos': [], 'avisos': [], 'unidad': False,
            'encuesta_id': None, 'hoja': None, 'adjuntos': None}
    if origen == destino:
        plan['bloqueos'].append('El formulario ya es de esa persona.')
        return plan
    definicion = leer_definicion(origen, ruta_forma)
    if definicion is None or not ruta_forma.lower().endswith('.forma'):
        plan['bloqueos'].append('No hay un formulario en %s.' % ruta_forma)
        return plan
    fila = ebd.obtener(definicion.get('id')) if definicion.get('id') else None
    if fila and (fila['ruta'] != ruta_forma
                 or (not ruta_forma.startswith('/unidades/')
                     and int(fila['propietario']) != origen)):
        plan['bloqueos'].append(
            'Ese archivo es una copia: su identificador pertenece al formulario '
            'de %s (usuario %s).' % (fila['ruta'], fila['propietario']))
        return plan
    plan['encuesta_id'] = fila['id'] if fila else None
    plan['respuestas'] = ebd.contar_respuestas(fila['id']) if fila else 0

    if ruta_forma.startswith('/unidades/'):
        plan['unidad'] = True
        unidad = ruta_forma.split('/')[2]
        rol = bd.consultar('SELECT rol FROM unidad_miembros WHERE unidad_id = %s '
                           'AND usuario_id = %s', (int(unidad), destino))
        if not rol or rol[0]['rol'] not in ROLES_QUE_ESCRIBEN:
            plan['bloqueos'].append(
                'La persona no puede editar en esa unidad compartida (rol: %s).'
                % (rol[0]['rol'] if rol else 'no es miembro'))
        if not fila:
            plan['bloqueos'].append('El formulario aún no está registrado: no hay '
                                    'responsable que cambiar.')
        return plan

    carpeta = normalizar_ruta_virtual(carpeta) if carpeta else _padre(ruta_forma)
    plan['piezas'].append({'que': 'formulario', 'de': ruta_forma,
                           'a': _unir(carpeta, _nombre(ruta_forma)), 'carpeta': False})

    hoja = ((fila or {}).get('hoja_ruta') or '').strip()
    if hoja:
        if en_carpeta_interna(hoja):
            plan['bloqueos'].append(
                'El formulario se creó desde un libro (su hoja está en la carpeta '
                'interna): hay que pasar el libro entero, y eso no lo hace esta función.')
        elif hoja.startswith('/unidades/'):
            plan['avisos'].append('La hoja de respuestas está en una unidad compartida '
                                  'y se queda donde está: %s' % hoja)
        elif _existe(origen, hoja):
            plan['hoja'] = _unir(carpeta, _nombre(hoja))
            plan['piezas'].append({'que': 'hoja de respuestas', 'de': hoja,
                                   'a': plan['hoja'], 'carpeta': False})
            import encuestas_hoja as hoja_mod
            dentro = hoja_mod._sala_ocupada(origen, hoja)
            if dentro is None or dentro:
                plan['bloqueos'].append('La hoja de respuestas está abierta en el '
                                        'editor. Hay que cerrarla antes.')
        else:
            plan['avisos'].append('La hoja de respuestas anotada ya no existe (%s): '
                                  'el formulario queda sin hoja.' % hoja)
            plan['hoja'] = ''

    adjuntos = archivos_mod.carpeta_destino(ruta_forma)
    if os.path.isdir(ruta_fisica(origen, adjuntos)):
        plan['adjuntos'] = (adjuntos, archivos_mod.carpeta_destino(plan['piezas'][0]['a']))
        plan['piezas'].append({'que': 'carpeta de adjuntos', 'de': adjuntos,
                               'a': plan['adjuntos'][1], 'carpeta': True})

    for pieza in plan['piezas']:
        if _existe(destino, pieza['a']):
            plan['bloqueos'].append('En el Drive de destino ya existe %s.' % pieza['a'])
    return plan


def _crear_carpetas(usuario, carpeta):
    acumulada = ''
    for parte in [p for p in carpeta.split('/') if p]:
        if not os.path.isdir(ruta_fisica(usuario, acumulada + '/' + parte, escritura=True)):
            nucleo.crear_carpeta(usuario, acumulada or '/', parte)
        acumulada += '/' + parte


def _copiar(plan):
    """Deja las piezas en el Drive del nuevo dueño. Devuelve lo copiado."""
    origen, destino, copiadas = plan['origen'], plan['destino'], []
    for pieza in plan['piezas']:
        fisica = ruta_fisica(origen, pieza['de'])
        if not pieza['carpeta']:
            _crear_carpetas(destino, _padre(pieza['a']))
            with open(fisica, 'rb') as flujo:
                nucleo.subir(destino, _padre(pieza['a']), _nombre(pieza['a']), flujo)
            copiadas.append(pieza['a'])
            continue
        _crear_carpetas(destino, pieza['a'])
        copiadas.append(pieza['a'])
        for raiz, _carpetas, archivos in os.walk(fisica):
            relativa = os.path.relpath(raiz, fisica)
            dentro = pieza['a'] if relativa == '.' else _unir(pieza['a'], relativa.replace(os.sep, '/'))
            _crear_carpetas(destino, dentro)
            for nombre in archivos:
                with open(os.path.join(raiz, nombre), 'rb') as flujo:
                    nucleo.subir(destino, dentro, nombre, flujo)
    return copiadas


def _reasignar(plan, vieja, nueva):
    """Lo que apuntaba al archivo del dueño anterior pasa a apuntar al nuevo."""
    total = 0
    for tabla, columna, dueno in APUNTAN:
        try:
            filas = bd.consultar(
                'UPDATE {t} SET {d} = %(destino)s, '
                '  {c} = %(nueva)s || substr({c}, length(%(vieja)s) + 1) '
                'WHERE {d} = %(origen)s AND ({c} = %(vieja)s '
                '  OR left({c}, length(%(vieja)s) + 1) = %(vieja)s || \'/\') RETURNING 1'
                .format(t=tabla, c=columna, d=dueno),
                {'vieja': vieja, 'nueva': nueva,
                 'origen': plan['origen'], 'destino': plan['destino']})
            total += len(filas or [])
        except Exception as excepcion:      # la tabla puede no existir todavía
            log.info('cambiar dueño %s.%s: %s', tabla, columna, excepcion)
    return total


def _rutas_de_adjuntos(encuesta_id, vieja, nueva):
    """Las respuestas guardan la ruta de cada adjunto en el Drive del dueño."""
    cambiadas = 0
    for fila in bd.consultar('SELECT id, datos FROM encuesta_respuestas '
                             'WHERE encuesta_id = %s', (encuesta_id,)):
        datos = fila['datos']
        if isinstance(datos, str):
            datos = json.loads(datos or '{}')
        tocada = False
        for valor in (datos or {}).values():
            for ficha in valor if isinstance(valor, list) else []:
                ruta = ficha.get('ruta') if isinstance(ficha, dict) else None
                if ruta and (ruta == vieja or ruta.startswith(vieja + '/')):
                    ficha['ruta'] = nueva + ruta[len(vieja):]
                    tocada = True
        if tocada:
            bd.ejecutar('UPDATE encuesta_respuestas SET datos = %s WHERE id = %s',
                        (json.dumps(datos, ensure_ascii=False), fila['id']))
            cambiadas += 1
    return cambiadas


def _quitar_compartido_propio(plan, usuario_destino):
    """Lo que el dueño anterior le había compartido al nuevo ya no hace falta."""
    if not usuario_destino:
        return
    for pieza in plan['piezas']:
        try:
            bd.ejecutar('DELETE FROM compartidos WHERE propietario_id = %s AND ruta = %s '
                        'AND (destinatario = %s OR lower(email) = lower(%s))',
                        (plan['origen'], pieza['de'], usuario_destino.get('username') or '',
                         usuario_destino.get('email') or ''))
        except Exception as excepcion:
            log.info('cambiar dueño: compartido propio (%s)', excepcion)


def _hoja_en_reposo(plan, espera):
    """La hoja lleva `espera` segundos cerrada y sin que nadie la escriba."""
    import time
    import encuestas_hoja as hoja_mod
    hojas = [p['de'] for p in plan['piezas'] if p['que'] == 'hoja de respuestas']
    if not hojas or not espera:
        return
    fisica = ruta_fisica(plan['origen'], hojas[0])
    antes = os.path.getmtime(fisica)
    time.sleep(espera)
    dentro = hoja_mod._sala_ocupada(plan['origen'], hojas[0])
    if dentro is None or dentro or os.path.getmtime(fisica) != antes:
        raise ValueError('La hoja de respuestas se acaba de cerrar o de guardar. '
                         'Hay que esperar un momento y volver a intentarlo.')


def aplicar(plan, usuario_destino=None, espera=ESPERA_CIERRE):
    """Ejecuta el plan. Devuelve un resumen; lanza si no se pudo completar."""
    if plan['bloqueos']:
        raise ValueError('; '.join(plan['bloqueos']))
    _hoja_en_reposo(plan, espera)
    from api_encuestas import leer_definicion
    origen, destino, encuesta_id = plan['origen'], plan['destino'], plan['encuesta_id']
    if plan['unidad']:
        bd.ejecutar('UPDATE encuestas SET propietario = %s, actualizada_en = NOW() '
                    'WHERE id = %s', (destino, encuesta_id))
        log.info('formulario %s (%s): responsable %s → %s', encuesta_id, plan['ruta'],
                 origen, destino)
        return {'ruta': plan['ruta'], 'copiadas': [], 'reasignadas': 0, 'adjuntos': 0}

    copiadas = []
    try:
        copiadas = _copiar(plan)
    except Exception:
        for ruta in reversed(copiadas):
            try:
                nucleo.enviar_a_papelera(destino, ruta)
            except Exception as excepcion:
                log.warning('cambiar dueño: no se pudo retirar %s (%s)', ruta, excepcion)
        raise

    nueva = plan['piezas'][0]['a']
    if encuesta_id:
        if plan['hoja'] is None:
            bd.ejecutar('UPDATE encuestas SET propietario = %s, ruta = %s, '
                        'actualizada_en = NOW() WHERE id = %s', (destino, nueva, encuesta_id))
        else:
            bd.ejecutar('UPDATE encuestas SET propietario = %s, ruta = %s, hoja_ruta = %s, '
                        'actualizada_en = NOW() WHERE id = %s',
                        (destino, nueva, plan['hoja'] or None, encuesta_id))
    adjuntos = 0
    if encuesta_id and plan['adjuntos'] and plan['adjuntos'][0] != plan['adjuntos'][1]:
        adjuntos = _rutas_de_adjuntos(encuesta_id, *plan['adjuntos'])
    _quitar_compartido_propio(plan, usuario_destino)
    reasignadas = sum(_reasignar(plan, p['de'], p['a']) for p in plan['piezas'])

    leido = leer_definicion(destino, nueva)
    registro = ebd.obtener(encuesta_id) if encuesta_id else None
    if leido is None or (encuesta_id and (leido.get('id') != encuesta_id
                                          or int(registro['propietario']) != destino)):
        raise RuntimeError('El formulario no quedó bien en el Drive de destino; '
                           'los originales NO se han tocado.')

    for pieza in plan['piezas']:
        nucleo.enviar_a_papelera(origen, pieza['de'])
    log.info('formulario %s: %s (usuario %s) → %s (usuario %s); %d rutas reasignadas',
             encuesta_id, plan['ruta'], origen, nueva, destino, reasignadas)
    return {'ruta': nueva, 'copiadas': copiadas, 'reasignadas': reasignadas,
            'adjuntos': adjuntos}
