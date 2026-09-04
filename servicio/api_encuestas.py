# -*- coding: utf-8 -*-
"""
API de Formularios del Almacén Maquita (archivos `.forma`).
===========================================================
Un formulario es UN ARCHIVO más del Drive: un `.forma` con la definición en JSON.
Por eso hereda gratis permisos de unidad, compartir, papelera, versiones,
búsqueda y auditoría — igual que un `.drawio` hereda el editor de diagramas.

Aquí vive la parte que necesita sesión iniciada: cargar/guardar la definición,
publicar el enlace y consultar las respuestas. Responder el formulario desde
fuera es otra cosa y vive en `api_encuestas_publico.py`.

La forma del `.forma` y su validación viven en `encuestas_modelo.py`; aquí solo
quedan las rutas.

Rutas (todas bajo el candado maestro de /api/almacen y /archivos-almacen):
  GET  /api/almacen/encuestas/cargar?ruta=
  POST /api/almacen/encuestas/guardar?ruta=
  POST /api/almacen/encuestas/publicar?ruta=      {publicar: true|false}
  POST /api/almacen/encuestas/ajustes?ruta=
  GET  /api/almacen/encuestas/respuestas?ruta=
  POST /api/almacen/encuestas/respuestas/borrar?ruta=  → {id} una, sin id todas
  GET  /api/almacen/encuestas/qr?ruta=            → QR del enlace (png|svg)
  GET/POST /api/almacen/encuestas/preferencias    → ajustes predeterminados
  GET  /api/almacen/encuestas/mios               → los propios (para importar)
  POST /api/almacen/encuestas/calificar?ruta=     → puntos a mano (cuestionario)
  POST /api/almacen/encuestas/recalificar?ruta=   → rehace todas las notas
  POST /api/almacen/encuestas/exportar?ruta=      → .xlsx en la misma carpeta
  POST /api/almacen/encuestas/imagen?ruta=       → sube una imagen
  GET  /api/almacen/encuestas/imagen/<eid>/<iid>  → la sirve (con sesión)
  GET  /archivos-almacen/formulario?ruta=         → editor
  GET  /archivos-almacen/formulario-respuestas?ruta=

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import io
import json
import logging
import os
import uuid

from flask import Blueprint, jsonify, request, send_file

import encuestas_bd as ebd
import encuestas_imagenes as imagenes
import encuestas_ajustes as ajustes_mod
import encuestas_calificar as calificar
import encuestas_correo as correo_mod
import encuestas_qr as qr
import encuestas_excel as excel
import encuestas_hoja as hoja_mod
import encuestas_modelo as modelo
import nucleo_archivos as nucleo
from api_archivos import _permiso_unidad, error, usuario_actual
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.encuestas')

bp_encuestas = Blueprint('almacen_encuestas', __name__)
bp_encuestas_web = Blueprint('almacen_encuestas_web', __name__)

EXT_FORMA = 'forma'

# Se reexportan para quien ya los importaba desde aquí (api_crear, api pública).
formulario_vacio = modelo.formulario_vacio
TIPOS_CON_OPCIONES = modelo.TIPOS_CON_OPCIONES


# ---------------------------------------------------------------------------
# Lectura y escritura del archivo
# ---------------------------------------------------------------------------
def _ruta_pedida(param='ruta'):
    """Ruta virtual normalizada del `.forma`. Lanza RutaInvalida si no sirve."""
    ruta = normalizar_ruta_virtual(request.args.get(param, ''))
    if ruta == '/' or ruta.endswith('/'):
        raise RutaInvalida('Ruta inválida')
    if not ruta.lower().endswith('.' + EXT_FORMA):
        raise RutaInvalida('Esto no es un formulario del Drive')
    return ruta


# Nombre anterior de `leer_definicion`. Se conserva porque
# `api_encuestas_publico` lo importa: al renombrarlo sin más ese import falló y
# con él se cayó el registro entero del Drive —404 en todo /archivos-almacen—
# hasta que se restauró (27/08/2026). Un nombre que otro módulo importa es parte
# del contrato, aunque empiece por guion bajo.
def leer_definicion(usuario, ruta):
    """Devuelve la definición del `.forma`. Un archivo vacío o corrupto no es un
    error para la persona: se le entrega un formulario en blanco para trabajar."""
    fisica = ruta_fisica(usuario, ruta)
    if not os.path.isfile(fisica):
        return None
    try:
        with open(fisica, 'r', encoding='utf-8', errors='replace') as f:
            crudo = f.read()
    except Exception as excepcion:
        log.error('leer %s: %s', ruta, excepcion)
        return None
    if not crudo.strip():
        return formulario_vacio(_titulo_desde_ruta(ruta))
    try:
        definicion = json.loads(crudo)
    except ValueError:
        log.warning('El formulario %s no es JSON válido; se abre en blanco', ruta)
        return formulario_vacio(_titulo_desde_ruta(ruta))
    return definicion if isinstance(definicion, dict) else \
        formulario_vacio(_titulo_desde_ruta(ruta))



_leer_definicion = leer_definicion

def _escribir_definicion(usuario, ruta, definicion):
    """Guarda el `.forma` con nucleo.subir() → versionado y dedup como cualquier
    documento del Drive."""
    contenido = json.dumps(definicion, ensure_ascii=False,
                           indent=2).encode('utf-8')
    carpeta = ruta.rsplit('/', 1)[0] or '/'
    nombre = ruta.rsplit('/', 1)[-1]
    nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido))
    return len(contenido)


def _titulo_desde_ruta(ruta):
    nombre = ruta.rsplit('/', 1)[-1]
    return nombre[:-(len(EXT_FORMA) + 1)] if '.' in nombre else nombre


# ---------------------------------------------------------------------------
# Validación (delegada en el modelo)
# ---------------------------------------------------------------------------
def _limpiar_definicion(bruto, id_previo=None):
    return modelo.limpiar(bruto, id_previo=id_previo)


# ---------------------------------------------------------------------------
# Acceso: el formulario se rige por los permisos del ARCHIVO
# ---------------------------------------------------------------------------
def _abrir(escritura=False):
    """Comprueba permisos y devuelve (usuario, ruta, definicion, fila_bd).

    Devuelve una tupla `(None, respuesta_error)` cuando no se puede continuar,
    para que cada endpoint corte con una sola línea.
    """
    usuario = usuario_actual()
    try:
        ruta = _ruta_pedida()
    except RutaInvalida as excepcion:
        return None, error(str(excepcion), excepcion.codigo)
    if not _permiso_unidad(usuario, ruta.rsplit('/', 1)[0] or '/',
                           escritura=escritura):
        return None, error(
            'No tienes permiso sobre este formulario. Pide acceso a quien '
            'administra la unidad.', 403)
    definicion = leer_definicion(usuario, ruta)
    if definicion is None:
        return None, error('Formulario no encontrado', 404)
    return (usuario, ruta, definicion), None


def _sincronizar_bd(usuario, ruta, definicion):
    """Asegura que el formulario está registrado y devuelve su fila.

    Si el id ya pertenece a otra ruta (un `.forma` copiado), se le asigna uno
    nuevo a esta copia: así una copia empieza con sus propias respuestas en vez
    de escribir sobre las del original.
    """
    # En la BD y en el Excel el título va SIN formato: son sitios que no
    # pintan HTML y mostrarían las etiquetas tal cual.
    fila = ebd.registrar(definicion['id'], usuario, ruta,
                         modelo.plano(definicion['titulo']))
    if fila is None:
        definicion['id'] = str(uuid.uuid4())
        _escribir_definicion(usuario, ruta, definicion)
        fila = ebd.registrar(definicion['id'], usuario, ruta,
                             modelo.plano(definicion['titulo']))
    return fila


def _resumen(fila, definicion):
    """Estado del formulario tal como lo pinta el editor."""
    return {
        'id': definicion['id'],
        'token': fila.get('token') if fila else None,
        # Lo que se comparte: /f/<codigo>, mucho más corto de dictar y de
        # escanear. El token sigue ahí porque los enlaces ya repartidos lo usan.
        'codigo': fila.get('codigo') if fila else None,
        'abierta': bool(fila.get('abierta')) if fila else True,
        'solo_internos': bool(fila.get('solo_internos')) if fila else False,
        'una_por_persona': bool(fila.get('una_por_persona')) if fila else False,
        'respuestas': ebd.contar_respuestas(definicion['id']),
        # Para avisar de a qué lleva el QR antes de imprimirlo.
        'restricciones': qr.restricciones(fila),
        'ajustes': ajustes_mod.limpiar((fila or {}).get('ajustes')),
        # La pantalla no debe ofrecer el envío de copias si el sistema no
        # tiene correo configurado: sería una opción que no se cumple.
        'correo_disponible': correo_mod.disponible(),
        'puntos_totales': calificar.total_posible(definicion),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@bp_encuestas.route('/encuestas/cargar', methods=['GET'])
def cargar():
    """Definición del formulario + su estado de publicación."""
    datos, fallo = _abrir()
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion)
    return jsonify({'success': True, 'formulario': definicion,
                    'estado': _resumen(fila, definicion),
                    'nombre': ruta.rsplit('/', 1)[-1]})


@bp_encuestas.route('/encuestas/guardar', methods=['POST'])
def guardar():
    """Guarda la definición editada."""
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, previa = datos
    cuerpo = request.get_json(silent=True) or {}
    try:
        definicion = _limpiar_definicion(cuerpo.get('formulario'),
                                         id_previo=previa.get('id'))
    except ValueError as excepcion:
        return error(str(excepcion), 400)
    try:
        tamano = _escribir_definicion(usuario, ruta, definicion)
    except Exception as excepcion:
        log.error('guardar %s: %s', ruta, excepcion)
        return error('No se pudo guardar el formulario', 500)
    fila = _sincronizar_bd(usuario, ruta, definicion)

    # Si el formulario tiene hoja vinculada, se rehace unos segundos después:
    # añadir o quitar una pregunta cambia las COLUMNAS del Excel, no solo las
    # filas (27/08/2026). Va con retardo porque el editor guarda solo mientras
    # se escribe.
    try:
        hoja_mod.refrescar_al_editar(fila, definicion)
    except Exception as excepcion:
        log.warning('no se pudo programar el refresco de la hoja de %s: %s',
                    ruta, excepcion)

    # Una imagen que se quitó del formulario no tiene por qué seguir en disco.
    try:
        imagenes.limpiar_huerfanas(definicion['id'], definicion)
    except Exception as excepcion:
        log.warning('No se pudieron limpiar imágenes de %s: %s', ruta, excepcion)
    try:
        registrar_actividad(usuario, 'edito', ruta,
                            nucleo.tamano_humano(tamano))
    except Exception:
        pass
    return jsonify({'success': True, 'estado': _resumen(fila, definicion)})


@bp_encuestas.route('/encuestas/publicar', methods=['POST'])
def publicar():
    """Crea o revoca el enlace público del formulario."""
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion)
    quiere = bool((request.get_json(silent=True) or {}).get('publicar', True))
    if quiere:
        ebd.publicar(definicion['id'])
    else:
        ebd.revocar(definicion['id'])
    fila = ebd.obtener(definicion['id'])
    return jsonify({'success': True, 'estado': _resumen(fila, definicion)})


@bp_encuestas.route('/encuestas/ajustes', methods=['POST'])
def ajustes():
    """Cambia si el formulario recibe respuestas y cómo."""
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion)
    cuerpo = request.get_json(silent=True) or {}

    # Se parte de lo que ya hay: pueden llegar solo algunos campos.
    solo_internos = cuerpo.get('solo_internos')
    # ¿La persona acaba de DESMARCAR «solo para personas de Maquita»? Es
    # distinto de que ese campo simplemente no venga en la petición, y cambia
    # hacia qué lado se resuelve un choque entre opciones: manda su decisión y
    # cede la opción que exigía la sesión, en vez de volver a activarla sola.
    # Sin esto, desmarcarla no servía de nada y el enlace y el QR seguían
    # pidiendo iniciar sesión.
    abriendo = (solo_internos is not None and not solo_internos
                and bool((fila or {}).get('solo_internos')))
    if solo_internos is None:
        solo_internos = bool((fila or {}).get('solo_internos'))
    una_por_persona = cuerpo.get('una_por_persona')
    if una_por_persona is None:
        una_por_persona = bool((fila or {}).get('una_por_persona'))

    # «Una sola respuesta por persona» EXIGE saber quién responde, y eso solo se
    # sabe con la sesión iniciada. Sin ese requisito la opción no se cumple:
    # quien entra sin sesión puede enviar tantas veces como quiera. Antes se
    # dejaban marcar las dos por separado y la opción mentía, así que aquí se
    # fuerza la pareja — también cuando la petición no viene de la pantalla.
    # El resto de opciones de la pestaña «Configuración».
    nuevos = ajustes_mod.limpiar(
        cuerpo.get('ajustes') if isinstance(cuerpo.get('ajustes'), dict)
        else (fila or {}).get('ajustes'))

    # Todas las dependencias entre opciones se resuelven en un solo sitio y
    # SIEMPRE en el servidor: la pantalla puede ayudar, pero no es la que manda.
    # ¿Acaba de poner «No recoger» en el correo? Igual que con «solo personas
    # de Maquita»: es una decisión deliberada, no un guardado parcial, y manda
    # sobre las opciones que dependían de que hubiera correo.
    pedidos = cuerpo.get('ajustes') if isinstance(cuerpo.get('ajustes'), dict) else {}
    antes = ajustes_mod.limpiar((fila or {}).get('ajustes'))
    quitando_correo = (pedidos.get('recopilar_correo') == ajustes_mod.CORREO_NO
                       and antes['recopilar_correo'] != ajustes_mod.CORREO_NO)

    nuevos, solo_internos, una_por_persona, forzados = ajustes_mod.coherentes(
        nuevos, solo_internos, una_por_persona, abriendo=abriendo,
        quitando_correo=quitando_correo)

    ebd.ajustar(definicion['id'],
                abierta=cuerpo.get('abierta'),
                solo_internos=bool(solo_internos),
                una_por_persona=bool(una_por_persona))
    ebd.guardar_ajustes(definicion['id'], nuevos)
    fila = ebd.obtener(definicion['id'])
    return jsonify({'success': True, 'estado': _resumen(fila, definicion),
                    'forzados': forzados})


def quien_respondio(fila, nombres, ajustes):
    """Cómo se llama a quien envió una respuesta, en la lista y en la ficha.

    Tres casos, y cada uno dice la verdad de lo que se sabe (27/08/2026):

      anónima          → «Anónimo». No es que falte el dato: es que se prometió
                         no guardarlo, y el nombre no puede sugerir otra cosa.
      con sesión FARO  → su nombre, que es lo que quien lee el formulario
                         reconoce.
      sin sesión       → el correo con el que respondió.

    Y si no hay ninguna de las tres, «Sin identificar»: antes ponía «Externo»,
    que suena a una categoría de persona cuando en realidad es «no se sabe».
    """
    if ajustes.get('anonimo'):
        return 'Anónimo'
    nombre = nombres.get(fila.get('usuario_id'))
    if nombre:
        return nombre
    correo = (fila.get('correo') or '').strip()
    return correo or 'Sin identificar'


@bp_encuestas.route('/encuestas/respuestas', methods=['GET'])
def respuestas():
    """Respuestas recibidas + el resumen por pregunta que pinta la vista."""
    datos, fallo = _abrir()
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion)
    filas = ebd.listar_respuestas(definicion['id'])
    nombres = ebd.nombres_usuarios([f['usuario_id'] for f in filas])
    ajustes_vivos = ajustes_mod.limpiar((fila or {}).get('ajustes'))
    lista = [{
        'id': f['id'],
        'quien': quien_respondio(f, nombres, ajustes_vivos),
        'correo': f.get('correo') or '',
        'puntos': (float(f['puntos']) if f.get('puntos') is not None else None),
        'puntos_max': (float(f['puntos_max'])
                       if f.get('puntos_max') is not None else None),
        'calificacion': f.get('calificacion'),
        'revisada': bool(f.get('revisada')),
        'enviada_en': f['enviada_en'].isoformat() if f['enviada_en'] else None,
        'datos': f['datos'],
    } for f in filas]
    return jsonify({'success': True, 'formulario': definicion,
                    'estado': _resumen(fila, definicion),
                    'respuestas': lista,
                    'resumen': _resumen_por_pregunta(definicion, filas)})


def _resumen_para_excel(definicion, filas):
    """El resumen de la vista, traducido a lo que necesita la hoja «Resumen».

    Se parte de `_resumen_por_pregunta`, el MISMO cálculo que pinta las barras
    en pantalla: si el Excel contara por su cuenta, tarde o temprano diría una
    cosa distinta de lo que se ve, y no habría forma de saber cuál está bien.
    """
    resumen = _resumen_por_pregunta(definicion, filas)
    bloques = []
    for pregunta in modelo.preguntas(definicion):
        datos = resumen.get(pregunta['id'])
        titulo = modelo.plano(pregunta['titulo'])
        if not datos:
            # Texto libre, fecha, hora: no hay opciones que contar, pero sí
            # interesa cuánta gente la respondió.
            respondidas = sum(
                1 for f in filas
                if str((f['datos'] or {}).get(pregunta['id']) or '').strip())
            bloques.append({'titulo': titulo, 'respondidas': respondidas})
            continue

        conteo = datos.get('conteo') or {}
        total = sum(conteo.values()) or 1
        bloques.append({
            'titulo': titulo,
            'promedio': datos.get('promedio'),
            'conteo': [(etiqueta, veces, veces * 100.0 / total)
                       for etiqueta, veces in conteo.items()],
        })
    return bloques


def _resumen_por_pregunta(definicion, filas):
    """Cuenta de cada opción y promedio de las escalas, para las barras."""
    resumen = {}
    for pregunta in modelo.preguntas(definicion):
        pid = pregunta['id']
        if pregunta['tipo'] in TIPOS_CON_OPCIONES:
            conteo = {opcion: 0 for opcion in pregunta['opciones']}
            # Lo respondido por «Otro» no está en la lista de opciones: se
            # recoge aparte para que el resumen no lo deje fuera de la cuenta.
            otros = []
            for fila in filas:
                valor = (fila['datos'] or {}).get(pid)
                for elegido in (valor if isinstance(valor, list) else [valor]):
                    if elegido in conteo:
                        conteo[elegido] += 1
                    elif elegido not in (None, '') and pregunta.get('otro'):
                        otros.append(elegido)
            resumen[pid] = {'tipo': 'conteo', 'conteo': conteo, 'otros': otros}
        elif pregunta['tipo'] == 'escala':
            valores = []
            for fila in filas:
                try:
                    valores.append(float((fila['datos'] or {}).get(pid)))
                except (TypeError, ValueError):
                    pass

            # Se cuenta cuánta gente eligió cada punto de la escala, no solo el
            # promedio: un promedio de 3 puede ser «todos eligieron 3» o «la
            # mitad 1 y la mitad 5», y son dos resultados muy distintos. Con la
            # distribución el gráfico lo enseña.
            maximo = int(pregunta.get('escala_max') or 5)
            conteo = {str(v): 0 for v in range(1, maximo + 1)}
            for valor in valores:
                clave = str(int(valor))
                if clave in conteo:
                    conteo[clave] += 1

            resumen[pid] = {
                'tipo': 'escala',
                'promedio': round(sum(valores) / len(valores), 2) if valores else None,
                'total': len(valores),
                'conteo': conteo,
                'maximo': maximo,
                'etiqueta_min': pregunta.get('escala_min_etiqueta') or '',
                'etiqueta_max': pregunta.get('escala_max_etiqueta') or '',
            }
    return resumen


@bp_encuestas.route('/encuestas/respuestas/borrar', methods=['POST'])
def borrar_respuestas():
    """Vacía las respuestas. Solo quien puede editar el archivo."""
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    _sincronizar_bd(usuario, ruta, definicion)

    # Con «id» borra SOLO esa respuesta (papelera de la vista Individual);
    # sin él, vacía todas, que es lo que hacía antes de existir esa vista.
    cuerpo = request.get_json(silent=True) or {}
    if cuerpo.get('id') not in (None, ''):
        try:
            respuesta_id = int(cuerpo['id'])
        except (TypeError, ValueError):
            return error('Identificador de respuesta no válido', 400)
        if not ebd.borrar_respuesta(definicion['id'], respuesta_id):
            return error('Esa respuesta ya no existe', 404)
        return jsonify({'success': True, 'borradas': 1})

    ebd.borrar_respuestas(definicion['id'])
    return jsonify({'success': True})


@bp_encuestas.route('/encuestas/preferencias', methods=['GET', 'POST'])
def preferencias():
    """Ajustes predeterminados de quien usa el editor.

    Se aplican a los formularios y preguntas que cree A PARTIR DE AHORA; los que
    ya existen no se tocan, que es como se comporta el ajuste equivalente de
    Google y lo único razonable: cambiar formularios ya repartidos por marcar
    una casilla sería una sorpresa desagradable.
    """
    usuario = usuario_actual()
    if request.method == 'GET':
        return jsonify({'success': True,
                        'preferencias': ajustes_mod.limpiar_preferencias(
                            ebd.preferencias(usuario))})

    cuerpo = request.get_json(silent=True) or {}
    limpias = ajustes_mod.limpiar_preferencias(cuerpo.get('preferencias'))
    ebd.guardar_preferencias(usuario, limpias)
    return jsonify({'success': True, 'preferencias': limpias})


@bp_encuestas.route('/encuestas/mios', methods=['GET'])
def mios():
    """Formularios de quien pregunta, para «Importar preguntas».

    Salen de la tabla, no de recorrer el Drive: ahí están los que esa persona
    creó, con su ruta y su título, y la consulta es una sola.

    Al importar se abre el formulario elegido por su ruta, así que **los
    permisos se comprueban entonces** como en cualquier otra apertura: esta
    lista no da acceso a nada por sí misma.
    """
    usuario = usuario_actual()
    ruta_actual = request.args.get('excepto') or ''
    filas = ebd.listar_por_propietario(usuario)
    return jsonify({'success': True, 'formularios': [
        {'ruta': f['ruta'], 'titulo': f['titulo'] or 'Sin título',
         'respuestas': f.get('respuestas') or 0}
        for f in filas if f['ruta'] != ruta_actual]})


@bp_encuestas.route('/encuestas/qr', methods=['GET'])
def codigo_qr():
    """QR del enlace público. `?formato=png|svg` y `?tamano=` en píxeles.

    Codifica el mismo `/formulario/<token>`, así que arrastra las mismas
    restricciones que el enlace y muere con él si se revoca.
    """
    datos, fallo = _abrir()
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion)

    token = (fila or {}).get('token')
    if not token:
        return error('Este formulario todavía no tiene enlace. Genera uno para '
                     'poder crear su código QR.', 409)

    # Se codifica el enlace CORTO: menos caracteres es un QR con menos módulos,
    # y un QR menos denso se escanea mejor de lejos y aguanta mejor una
    # impresión regular.
    corto = (fila or {}).get('codigo')
    enlace = request.host_url.rstrip('/') + ('/f/' + corto if corto
                                             else '/formulario/' + token)
    formato = (request.args.get('formato') or 'png').lower()
    if formato not in qr.FORMATOS:
        return error('Formato no válido: usa png o svg', 400)

    if formato == 'svg':
        return send_file(qr.svg(enlace), mimetype='image/svg+xml',
                         download_name='qr-formulario.svg')

    try:
        tamano = int(request.args.get('tamano') or qr.TAMANO_DEFECTO)
    except (TypeError, ValueError):
        tamano = qr.TAMANO_DEFECTO
    return send_file(qr.png(enlace, tamano), mimetype='image/png',
                     download_name='qr-formulario.png')


@bp_encuestas.route('/encuestas/exportar', methods=['POST'])
def exportar():
    """Escribe las respuestas como .xlsx EN LA MISMA CARPETA del Drive.

    Es el equivalente a la hoja vinculada de Google: el archivo queda dentro del
    Drive, con los permisos de esa carpeta, listo para abrir con OnlyOffice.
    """
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila_bd = _sincronizar_bd(usuario, ruta, definicion)

    memoria = hoja_mod.construir(fila_bd, definicion)
    if memoria is None:
        return error('La exportación a Excel no está disponible en el servidor '
                     '(falta openpyxl).', 501)

    carpeta = ruta.rsplit('/', 1)[0] or '/'
    nombre = _titulo_desde_ruta(ruta)[:80] + ' (respuestas).xlsx'
    try:
        nucleo.subir(usuario, carpeta, nombre, memoria)
    except Exception as excepcion:
        log.error('exportar %s: %s', ruta, excepcion)
        return error('No se pudo guardar el archivo de respuestas', 500)

    # El `.xlsx` se acaba de reemplazar por fuera del editor. Sin avisar, quien
    # lo abra se encuentra la copia que el Document Server tiene guardada —la
    # exportación anterior— y parece que exportar no hizo nada (27/08/2026).
    destino_xlsx = ('' if carpeta == '/' else carpeta) + '/' + nombre
    # A partir de aquí esta hoja queda VINCULADA al formulario: cada respuesta
    # nueva la rehace sola, sin tener que volver a pulsar «Exportar».
    hoja_mod.vincular(definicion['id'], destino_xlsx)
    try:
        from api_onlyoffice import invalidar_cache
        invalidar_cache(usuario, destino_xlsx)
    except Exception as excepcion:
        log.warning('exportar %s: no se pudo refrescar el editor (%s)',
                    ruta, excepcion)
    return jsonify({'success': True, 'nombre': nombre,
                    'ruta': (('' if carpeta == '/' else carpeta) + '/' + nombre)})


# ---------------------------------------------------------------------------
# Imágenes (encabezado del formulario e imágenes de las preguntas)
# ---------------------------------------------------------------------------
@bp_encuestas.route('/encuestas/imagen', methods=['POST'])
def subir_imagen():
    """Sube una imagen del formulario. Exige poder EDITAR el `.forma`.

    Devuelve la ficha ({id, ancho, alto}) que el editor coloca en la cabecera o
    en la pregunta. El archivo se valida y se recodifica antes de tocar el disco.
    """
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    _sincronizar_bd(usuario, ruta, definicion)

    archivo = request.files.get('imagen')
    if archivo is None:
        return error('No se recibió ninguna imagen', 400)

    try:
        ficha = imagenes.guardar(definicion['id'], archivo)
    except imagenes.ImagenInvalida as excepcion:
        return error(str(excepcion), 400)
    except Exception as excepcion:
        log.error('subiendo imagen a %s: %s', ruta, excepcion)
        return error('No se pudo guardar la imagen', 500)

    return jsonify({'success': True, 'imagen': ficha})


@bp_encuestas.route('/encuestas/imagen/<encuesta_id>/<imagen_id>', methods=['GET'])
def ver_imagen(encuesta_id, imagen_id):
    """Sirve una imagen del formulario a quien lo está editando.

    Basta con tener sesión: el candado de /api/almacen ya la exige y el id de la
    imagen no es adivinable. La versión pública, con más comprobaciones, está en
    `api_encuestas_publico`.
    """
    camino = imagenes.buscar(encuesta_id, imagen_id)
    if not camino:
        return error('Imagen no encontrada', 404)
    respuesta = send_file(camino, mimetype=imagenes.tipo_de(camino))
    respuesta.headers['X-Content-Type-Options'] = 'nosniff'
    respuesta.headers['Cache-Control'] = 'private, max-age=3600'
    return respuesta


# ---------------------------------------------------------------------------
# Páginas (bajo el candado de /archivos-almacen: exigen sesión iniciada)
# ---------------------------------------------------------------------------
def _pagina(nombre_plantilla):
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'plantillas', nombre_plantilla)
    respuesta = send_file(ruta, mimetype='text/html')
    respuesta.headers['Permissions-Policy'] = 'unload=*'
    return respuesta


@bp_encuestas_web.route('/archivos-almacen/formulario')
def editor_formulario():
    """Editor visual del formulario. La ruta del `.forma` viaja en ?ruta=."""
    return _pagina('editor_encuesta.html')


@bp_encuestas_web.route('/archivos-almacen/formulario-respuestas')
def vista_respuestas():
    """Resumen y tabla de respuestas del formulario."""
    return _pagina('encuesta_respuestas.html')
